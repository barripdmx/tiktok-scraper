# -*- coding: utf-8 -*-
"""
Enriquece un CSV grande de TikTok con la fecha de creación de las cuentas.

Pensado para datasets de comentarios donde existe una columna de handles
(por ejemplo `autor_handle`). Trabaja por cuentas únicas, guarda una tabla
auxiliar incremental y permite reanudar en ejecuciones posteriores.
"""

import os
import time
import random
from typing import Optional

import pandas as pd
import requests

from extraer_fechas_creacion_cuentas import (
    fetch_account_info, normalize_username, RateLimited,
)


def build_output_paths(source_csv: str):
    base_dir = os.path.dirname(source_csv) or os.getcwd()
    base_name = os.path.splitext(os.path.basename(source_csv))[0]
    lookup_csv = os.path.join(base_dir, f"{base_name}_lookup_fechas_creacion.csv")
    enriched_csv = os.path.join(base_dir, f"{base_name}_enriquecido_fechas_creacion.csv")
    return lookup_csv, enriched_csv


def safe_read_csv(path: str, **kwargs):
    encodings = ["utf-8-sig", "utf-8", "latin-1"]
    last_error = None
    for enc in encodings:
        try:
            return pd.read_csv(path, encoding=enc, **kwargs)
        except Exception as e:
            last_error = e
    raise last_error


def extract_unique_handles(source_csv: str, handle_col: str) -> pd.Series:
    df = safe_read_csv(source_csv, usecols=[handle_col])
    handles = df[handle_col].astype(str).map(normalize_username)
    handles = handles[(handles != "") & (handles != "nan") & (handles != "None")]
    handles = handles.drop_duplicates().reset_index(drop=True)
    return handles


def load_existing_lookup(lookup_csv: str) -> pd.DataFrame:
    if not os.path.exists(lookup_csv):
        return pd.DataFrame()

    lookup = safe_read_csv(lookup_csv)
    if "username_consulta" not in lookup.columns:
        raise ValueError(f"Lookup existente inválido: {lookup_csv}")

    lookup["username_consulta"] = lookup["username_consulta"].astype(str).map(normalize_username)
    lookup = lookup.drop_duplicates(subset=["username_consulta"], keep="last")
    return lookup


def save_lookup(lookup_df: pd.DataFrame, lookup_csv: str) -> None:
    lookup_df = lookup_df.drop_duplicates(subset=["username_consulta"], keep="last")
    # Escritura atómica: un crash a mitad de to_csv no debe corromper el lookup
    # incremental (es lo que permite reanudar sin re-consultar miles de cuentas).
    tmp = lookup_csv + ".tmp"
    lookup_df.to_csv(tmp, index=False, encoding="utf-8-sig")
    os.replace(tmp, lookup_csv)


def merge_lookup_into_source(
    source_csv: str,
    handle_col: str,
    lookup_df: pd.DataFrame,
    enriched_csv: str,
) -> str:
    df = safe_read_csv(source_csv)
    df["_handle_norm_tmp"] = df[handle_col].astype(str).map(normalize_username)

    # SEC-03: 'sec_uid' y 'bio' (identificadores/datos personales de los
    # comentaristas) se excluyen del CSV enriquecido, que es el artefacto que
    # más se comparte. Siguen en el lookup interno para reanudar consultas.
    merge_cols = [
        "username_consulta",
        "username_real",
        "fecha_creacion_cuenta",
        "fuente_fecha_creacion",
        "user_id",
        "verified",
        "followers",
        "following",
        "likes",
        "video_count",
        "error",
    ]
    key_col = "username_consulta"
    if key_col not in lookup_df.columns:
        raise ValueError(f"El lookup no contiene la columna clave '{key_col}'")

    # Solo las columnas del lookup que realmente existen: lookups generados por
    # versiones antiguas pueden no tener 'error', 'sec_uid', etc. y seleccionar
    # una columna ausente con lookup_df[merge_cols] lanzaría KeyError.
    cols_presentes = [c for c in merge_cols if c in lookup_df.columns]
    lookup_merge = lookup_df[cols_presentes].copy()

    # Renombrar TODA columna del lookup que colisione con una columna ya
    # existente en el CSV fuente (salvo la clave del merge), para evitar que
    # pandas genere sufijos _x / _y que los consumidores aguas abajo no
    # encuentran (gráficas de patrones quedarían vacías sin error).
    # - "likes" del lookup = likes totales de la cuenta (≠ likes del comentario)
    # - "user_id", "followers", "verified"… pueden venir ya en algunos CSVs
    collision_renames = {
        c: f"{c}_cuenta"
        for c in lookup_merge.columns
        if c != key_col and c in df.columns
    }
    if collision_renames:
        lookup_merge = lookup_merge.rename(columns=collision_renames)

    # Garantizar un único registro por handle antes del merge (evita duplicar
    # filas del source si el lookup tuviera entradas repetidas).
    lookup_merge = lookup_merge.drop_duplicates(subset=[key_col], keep="last")

    out = df.merge(
        lookup_merge,
        left_on="_handle_norm_tmp",
        right_on=key_col,
        how="left",
        sort=False,   # preserva el orden original del CSV fuente
    )
    out = out.drop(columns=["_handle_norm_tmp"])
    out.to_csv(enriched_csv, index=False, encoding="utf-8-sig")
    return enriched_csv


def _cuentas_resueltas(lookup_df: pd.DataFrame) -> set:
    """Handles del lookup que NO hay que reintentar.

    Una cuenta está "resuelta" si no tuvo error, o si el error es permanente
    (cuenta inexistente/eliminada). Los errores transitorios (timeout, 429,
    captcha, red) quedan fuera para reintentarse en la siguiente ejecución.
    """
    if lookup_df.empty or "username_consulta" not in lookup_df.columns:
        return set()
    if "error" in lookup_df.columns:
        err = lookup_df["error"].fillna("").astype(str)
    else:
        err = pd.Series([""] * len(lookup_df), index=lookup_df.index)
    permanente = err.str.contains("404|not found|no encontr", case=False,
                                  regex=True, na=False)
    resuelto = (err.str.strip() == "") | permanente
    return set(lookup_df.loc[resuelto, "username_consulta"]
               .astype(str).map(normalize_username))


def process_handles(
    source_csv: str,
    handle_col: str,
    batch_limit: Optional[int] = None,
    pause_seconds: float = 0.35,
):
    lookup_csv, enriched_csv = build_output_paths(source_csv)

    # Evitar re-enriquecer un CSV que ya fue enriquecido: produciría columnas
    # obsoletas/duplicadas y los consumidores leerían las viejas. Lo detectamos
    # leyendo solo la cabecera, antes de gastar una tanda de peticiones.
    try:
        src_cols = list(safe_read_csv(source_csv, nrows=0).columns)
    except Exception:
        src_cols = []
    if "fecha_creacion_cuenta" in src_cols:
        print("⚠️  El CSV fuente ya contiene 'fecha_creacion_cuenta' — parece ya "
              "enriquecido.\n   Usa el CSV de comentarios original, no el enriquecido.")
        return

    unique_handles = extract_unique_handles(source_csv, handle_col)
    lookup_df = load_existing_lookup(lookup_csv)
    done = _cuentas_resueltas(lookup_df)

    pending_all = [h for h in unique_handles.tolist() if h not in done]
    total_unique = len(unique_handles)

    if batch_limit and batch_limit > 0:
        pending = pending_all[:batch_limit]
    else:
        pending = pending_all

    print(f"CSV origen:           {source_csv}")
    print(f"Columna cuentas:      {handle_col}")
    print(f"Cuentas únicas:       {total_unique:,}")
    print(f"Ya resueltas:         {len(done):,}")
    print(f"Pendientes esta tanda:{len(pending):,}")
    print(f"Lookup:               {lookup_csv}")
    print(f"Enriquecido:          {enriched_csv}")

    if not pending:
        print("\nNo hay cuentas pendientes. Rehaciendo merge final...")
        merge_lookup_into_source(source_csv, handle_col, lookup_df, enriched_csv)
        print(f"CSV enriquecido guardado en: {enriched_csv}")
        return

    rows = lookup_df.to_dict("records") if not lookup_df.empty else []
    save_every = 100
    bloqueos_consecutivos = 0

    with requests.Session() as session:
        for i, handle in enumerate(pending, 1):
            global_idx = len(done) + i
            print(f"\n[{i}/{len(pending)} | total {global_idx}/{total_unique}] @{handle}")

            row = None
            for intento in range(3):
                try:
                    row = fetch_account_info(session, handle)
                    bloqueos_consecutivos = 0
                    break
                except RateLimited as e:
                    # Bloqueo global de TikTok → backoff exponencial y reintento.
                    bloqueos_consecutivos += 1
                    espera = min(30 * (2 ** intento), 240)
                    print(f"   ⏳ Bloqueo de TikTok ({str(e)[:50]}); espera {espera}s "
                          f"(intento {intento+1}/3)")
                    time.sleep(espera)
                except Exception as e:
                    # Error por cuenta (no bloqueo global): registrar y continuar.
                    row = {
                        "username_consulta": handle, "username_real": "", "nickname": "",
                        "verified": "", "user_id": "", "sec_uid": "",
                        "fecha_creacion_cuenta": "", "fuente_fecha_creacion": "",
                        "followers": 0, "following": 0, "likes": 0, "video_count": 0,
                        "bio": "", "profile_url": f"https://www.tiktok.com/@{handle}",
                        "error": str(e).strip() or type(e).__name__,
                    }
                    print(f"   ⚠️ {str(e)[:120]}")
                    break

            if row is None:
                # Agotados los reintentos por bloqueo: NO se cachea como error
                # (quedaría pendiente igualmente); se reintentará en otra tanda.
                print("   ↩ Sin resolver por bloqueo persistente; se reintentará luego.")
                if bloqueos_consecutivos >= 5:
                    print("   ⛔ Demasiados bloqueos consecutivos de TikTok; "
                          "abortando esta tanda y guardando lo conseguido.")
                    break
                continue

            rows.append(row)
            if not row.get("error"):
                print(f"   ✅ {row['fecha_creacion_cuenta'] or 'N/D'} "
                      f"| fuente: {row['fuente_fecha_creacion'] or 'sin fuente'}")

            if i % save_every == 0:
                save_lookup(pd.DataFrame(rows), lookup_csv)
                print("   💾 Lookup parcial guardado")

            # Pausa con jitter para evitar un patrón de peticiones regular.
            time.sleep(max(0.0, pause_seconds) + random.uniform(0.0, 0.3))

    save_lookup(pd.DataFrame(rows), lookup_csv)
    print("\n💾 Lookup final guardado")

    # Recargar el lookup deduplicado para contar cuántas cuentas quedan sin
    # resolver (transitorias, abortadas por bloqueo, o no incluidas por batch_limit).
    final_lookup = load_existing_lookup(lookup_csv)
    resueltas = _cuentas_resueltas(final_lookup)
    sin_resolver = [h for h in unique_handles.tolist() if h not in resueltas]

    merge_lookup_into_source(source_csv, handle_col, final_lookup, enriched_csv)

    if sin_resolver:
        print("\n" + "!" * 64)
        print(f"⚠️  ENRIQUECIMIENTO PARCIAL: quedan {len(sin_resolver):,} de "
              f"{total_unique:,} cuentas sin fecha de creación.")
        print("    El CSV enriquecido está INCOMPLETO. Vuelve a ejecutar esta")
        print("    opción para continuar (se reanuda donde lo dejó).")
        print("!" * 64)
    print(f"✅ CSV enriquecido guardado en: {enriched_csv}")


def main():
    import sys
    import tkinter as tk
    from tkinter import filedialog, simpledialog, messagebox

    # ── Selector de CSV ──────────────────────────────────────────────────────
    # Acepta ruta como argumento (lo pasa el menú cuando hay proyecto activo)
    if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]):
        source_csv = sys.argv[1]
    else:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)

        source_csv = filedialog.askopenfilename(
            title="Selecciona el CSV con cuentas de TikTok a analizar",
            filetypes=[
                ("CSV de comentarios", "*comentarios*.csv"),
                ("Todos los CSV", "*.csv"),
            ],
        )
        root.destroy()

    if not source_csv:
        print("Operación cancelada.")
        return
    if not os.path.isfile(source_csv):
        print("❌ No existe el archivo indicado")
        return

    # ── Columna de handles ───────────────────────────────────────────────────
    root2 = tk.Tk()
    root2.withdraw()
    root2.attributes("-topmost", True)
    handle_col = simpledialog.askstring(
        "Columna de cuentas",
        "¿Nombre de la columna con los handles de usuario?\n(deja en blanco para usar 'autor_handle')",
        initialvalue="autor_handle",
        parent=root2,
    )
    root2.destroy()

    if handle_col is None:
        print("Operación cancelada.")
        return
    handle_col = handle_col.strip() or "autor_handle"

    print("=" * 72)
    print("Enriquecedor CSV -> fecha de creación de cuentas TikTok")
    print("=" * 72)
    print(f"  CSV       : {os.path.basename(source_csv)}")
    print(f"  Columna   : {handle_col}")
    print()

    process_handles(
        source_csv=source_csv,
        handle_col=handle_col,
        batch_limit=2000,
        pause_seconds=0.35,
    )

    # ── Aviso final ──────────────────────────────────────────────────────────
    _, enriched_csv = build_output_paths(source_csv)
    root3 = tk.Tk()
    root3.withdraw()
    if os.path.exists(enriched_csv):
        abrir = messagebox.askyesno(
            "✅ Análisis completado",
            f"CSV enriquecido guardado en:\n{enriched_csv}\n\n¿Abrir la carpeta?"
        )
        root3.destroy()
        if abrir:
            import subprocess
            carpeta = os.path.dirname(enriched_csv)
            if sys.platform == "win32":
                os.startfile(carpeta)
            else:
                subprocess.run(["open" if sys.platform == "darwin" else "xdg-open", carpeta])
    else:
        root3.destroy()


if __name__ == "__main__":
    main()
