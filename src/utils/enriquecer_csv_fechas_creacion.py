# -*- coding: utf-8 -*-
"""
Enriquece un CSV grande de TikTok con la fecha de creación de las cuentas.

Pensado para datasets de comentarios donde existe una columna de handles
(por ejemplo `autor_handle`). Trabaja por cuentas únicas, guarda una tabla
auxiliar incremental y permite reanudar en ejecuciones posteriores.
"""

import os
import time
from typing import Optional

import pandas as pd
import requests

from extraer_fechas_creacion_cuentas import fetch_account_info, normalize_username


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
    lookup_df.to_csv(lookup_csv, index=False, encoding="utf-8-sig")


def merge_lookup_into_source(
    source_csv: str,
    handle_col: str,
    lookup_df: pd.DataFrame,
    enriched_csv: str,
) -> str:
    df = safe_read_csv(source_csv)
    df["_handle_norm_tmp"] = df[handle_col].astype(str).map(normalize_username)

    merge_cols = [
        "username_consulta",
        "username_real",
        "fecha_creacion_cuenta",
        "fuente_fecha_creacion",
        "user_id",
        "sec_uid",
        "verified",
        "followers",
        "following",
        "likes",
        "video_count",
        "error",
    ]
    lookup_merge = lookup_df[merge_cols].copy()

    out = df.merge(
        lookup_merge,
        left_on="_handle_norm_tmp",
        right_on="username_consulta",
        how="left",
    )
    out = out.drop(columns=["_handle_norm_tmp"])
    out.to_csv(enriched_csv, index=False, encoding="utf-8-sig")
    return enriched_csv


def process_handles(
    source_csv: str,
    handle_col: str,
    batch_limit: Optional[int] = None,
    pause_seconds: float = 0.35,
):
    lookup_csv, enriched_csv = build_output_paths(source_csv)

    unique_handles = extract_unique_handles(source_csv, handle_col)
    lookup_df = load_existing_lookup(lookup_csv)
    done = set()
    if not lookup_df.empty:
        done = set(lookup_df["username_consulta"].astype(str).map(normalize_username))

    pending = [h for h in unique_handles.tolist() if h not in done]
    total_unique = len(unique_handles)

    if batch_limit and batch_limit > 0:
        pending = pending[:batch_limit]

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

    with requests.Session() as session:
        for i, handle in enumerate(pending, 1):
            global_idx = len(done) + i
            print(f"\n[{i}/{len(pending)} | total {global_idx}/{total_unique}] @{handle}")
            try:
                row = fetch_account_info(session, handle)
                rows.append(row)
                print(
                    f"   ✅ {row['fecha_creacion_cuenta'] or 'N/D'} "
                    f"| fuente: {row['fuente_fecha_creacion'] or 'sin fuente'}"
                )
            except Exception as e:
                rows.append({
                    "username_consulta": handle,
                    "username_real": "",
                    "nickname": "",
                    "verified": "",
                    "user_id": "",
                    "sec_uid": "",
                    "fecha_creacion_cuenta": "",
                    "fuente_fecha_creacion": "",
                    "followers": 0,
                    "following": 0,
                    "likes": 0,
                    "video_count": 0,
                    "bio": "",
                    "profile_url": f"https://www.tiktok.com/@{handle}",
                    "error": str(e).strip() or type(e).__name__,
                })
                print(f"   ⚠️ {str(e)[:120]}")

            if i % save_every == 0:
                tmp_lookup = pd.DataFrame(rows)
                save_lookup(tmp_lookup, lookup_csv)
                print("   💾 Lookup parcial guardado")

            time.sleep(max(0.0, pause_seconds))

    final_lookup = pd.DataFrame(rows)
    save_lookup(final_lookup, lookup_csv)
    print("\n💾 Lookup final guardado")

    merge_lookup_into_source(source_csv, handle_col, final_lookup, enriched_csv)
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
