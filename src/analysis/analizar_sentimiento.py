# -*- coding: utf-8 -*-
"""
analizar_sentimiento.py — Pipeline unificado de análisis de sentimiento.

Proveedores disponibles:
  roberta  → pysentimiento (local, sin API key, sin límites)
  groq     → Groq / llama-3.3-70b-versatile  (100K tokens/día gratis)
  mistral  → Mistral / open-mistral-nemo      (1B tokens/mes gratis, 2 req/min)
  gemini   → Google Gemini Flash               (con fallback a 2.5-flash)

Uso desde menú:
    python src/analysis/analizar_sentimiento.py

Uso programático:
    from src.analysis.analizar_sentimiento import analizar_sentimiento
    df_result = analizar_sentimiento(df, csv_path, proveedor_id="roberta")

Salida estándar: columna 'sentiment' con valores POS / NEG / NEU / None.
"""

import os
import sys
import csv as _csv
import json
import time
import hashlib
from datetime import datetime

import pandas as pd
from dotenv import load_dotenv
import tkinter as tk
from tkinter import filedialog

# ─── Paths ──────────────────────────────────────────────────────────────────

BASE_DIR   = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CONFIG_DIR = os.path.join(BASE_DIR, "config")
DATA_DIR   = os.path.join(BASE_DIR, "data")

sys.path.insert(0, BASE_DIR)
load_dotenv(os.path.join(CONFIG_DIR, ".env"))

# ─── Configuración de proveedores ──────────────────────────────────────────

PROVEEDORES = {
    "roberta": {
        "nombre":      "RoBERTa (local)",
        "tipo":        "local",
        "modelo":      "finiteautomata/bertweet-base-sentiment-analysis",
        "sleep":       0,
        "descripcion": "Sin API key · Instantáneo · Sin límites · Mejor calidad",
    },
    "groq": {
        "nombre":      "Groq",
        "tipo":        "openai_compat",
        "modelo":      "llama-3.3-70b-versatile",
        "api_key_env": "GROQ_API_KEY",
        "sleep":       0.5,
        "limite_diario": 100_000,
        "descripcion": "100K tokens/día · Rápido · ~16 días para 46K comentarios",
    },
    "mistral": {
        "nombre":      "Mistral",
        "tipo":        "openai_compat",
        "modelo":      "open-mistral-nemo",
        "api_key_env": "MISTRAL_API_KEY",
        "sleep":       31,
        "limite_diario": 33_000_000,
        "descripcion": "1B tokens/mes · 2 req/min · ~8h seguidas para 46K comentarios",
    },
    "gemini": {
        "nombre":      "Gemini",
        "tipo":        "gemini",
        "modelo":      "gemini-2.0-flash-lite",
        "modelo_fallback": "gemini-2.5-flash",
        "api_key_env": "GEMINI_API_KEY",
        "sleep":       1.0,
        "descripcion": "Google Gemini Flash · Fallback a 2.5-flash en errores 503",
    },
}

BATCH_SIZE    = 50
TELEMETRY_CSV = os.path.join(DATA_DIR, "llm_telemetry.csv")
_TELEM_CAMPOS = [
    "timestamp", "proveedor", "modelo", "n_comentarios",
    "tokens_in", "tokens_out", "latencia_ms", "finish_reason", "parse_ok",
]

SYSTEM_PROMPT = """Eres un clasificador de sentimiento para comentarios de TikTok en español.
Clasifica cada comentario con exactamente una de estas etiquetas:
- POS: opinión positiva, apoyo, halago, humor positivo
- NEG: crítica, insulto, queja, ironía negativa
- NEU: neutro, pregunta, sin carga emocional clara

Devuelve ÚNICAMENTE un JSON array con un objeto por comentario, en el mismo orden:
[{"index": 0, "label": "POS"}, {"index": 1, "label": "NEG"}, ...]

Sin texto adicional, sin markdown, solo el JSON."""


# ─── Excepciones ────────────────────────────────────────────────────────────

class RateLimitDiaria(Exception):
    """Límite de tokens por día agotado."""


# ─── Telemetría ─────────────────────────────────────────────────────────────

def _log_telemetria(**kwargs):
    """Añade una fila al CSV acumulativo de telemetría LLM."""
    fila = {k: kwargs.get(k, "") for k in _TELEM_CAMPOS}
    existe = os.path.exists(TELEMETRY_CSV)
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(TELEMETRY_CSV, "a", newline="", encoding="utf-8") as f:
        w = _csv.DictWriter(f, fieldnames=_TELEM_CAMPOS)
        if not existe:
            w.writeheader()
        w.writerow(fila)


# ─── Utilidades comunes ─────────────────────────────────────────────────────

def detectar_columna_texto(df):
    for col in ['texto', 'comment_text', 'text', 'comentario', 'content', 'body']:
        if col in df.columns:
            return col
    for col in df.columns:
        if any(k in col.lower() for k in ('text', 'texto', 'comment')):
            return col
    return None


def detectar_columna_id(df):
    for col in ['comment_id', 'comentario_id', 'cid', 'id']:
        if col in df.columns:
            return col
    return None


def clave_estable(row, col_id, col_texto):
    if col_id:
        val = row.get(col_id)
        if val is not None and str(val).strip() not in ('', 'nan', 'None'):
            return str(val).strip()
    return hashlib.md5(str(row[col_texto]).encode('utf-8', errors='replace')).hexdigest()[:16]


def _migrar_checkpoint_si_necesario(ckpt_path, ckpt_data, df_len):
    """Detecta checkpoints con claves posicionales (formato antiguo) y los reinicia."""
    if not ckpt_data:
        return ckpt_data
    sample = list(ckpt_data.keys())[:20]
    try:
        nums = [int(k) for k in sample]
        if all(0 <= n < max(df_len * 3, 100_000) for n in nums):
            import shutil
            backup = ckpt_path.replace(".json", "_posicional_backup.json")
            shutil.copy2(ckpt_path, backup)
            print("   ⚠️  Checkpoint en formato antiguo (claves posicionales) detectado.")
            print(f"   ℹ️  Copia guardada en: {os.path.basename(backup)}")
            print("   🔄  Reiniciando con claves estables (ID o hash de texto).")
            return {}
    except (ValueError, TypeError):
        pass
    return ckpt_data


def limpiar_json(texto):
    t = texto.strip()
    for prefix in ("```json", "```"):
        if t.startswith(prefix):
            t = t[len(prefix):]
    if t.endswith("```"):
        t = t[:-3]
    return t.strip()


def get_checkpoint_path(csv_file, proveedor_id):
    return csv_file.replace(".csv", f"_{proveedor_id}_checkpoint.json")


def load_checkpoint(checkpoint_path):
    if os.path.exists(checkpoint_path):
        with open(checkpoint_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"   ✓ Checkpoint encontrado: {len(data):,} comentarios ya clasificados")
        return data
    return {}


def save_checkpoint(checkpoint_path, etiquetas_dict):
    with open(checkpoint_path, "w", encoding="utf-8") as f:
        json.dump(etiquetas_dict, f)


# ─── Proveedor: RoBERTa local ───────────────────────────────────────────────

def clasificar_roberta(df_f, col_texto):
    """
    Clasifica con pysentimiento (RoBERTa). Sin API, sin checkpoint, instantáneo.
    Devuelve lista de etiquetas POS/NEG/NEU (misma longitud que df_f).
    """
    try:
        from pysentimiento import create_analyzer
    except ImportError:
        print("   ❌ pysentimiento no instalado. Ejecuta: pip install pysentimiento")
        return None

    print("   Cargando modelo RoBERTa (primera vez puede tardar ~30s)...")
    analyzer = create_analyzer(task="sentiment", lang="es")

    etiquetas = []
    total = len(df_f)
    for i, texto in enumerate(df_f[col_texto].fillna("")):
        try:
            result = analyzer.predict(str(texto)[:512])
            # pysentimiento devuelve POS / NEG / NEU
            etiquetas.append(result.output.upper())
        except Exception:
            etiquetas.append(None)
        if (i + 1) % 500 == 0 or (i + 1) == total:
            print(f"   Clasificados: {i+1:,}/{total:,}", end="\r")
    print()
    return etiquetas


# ─── Proveedor: OpenAI-compatible (Groq / Mistral) ──────────────────────────

def _crear_cliente_openai_compat(proveedor_id, api_key):
    if proveedor_id == "groq":
        from groq import Groq
        return Groq(api_key=api_key)
    elif proveedor_id == "mistral":
        try:
            from mistralai import Mistral
        except ImportError:
            from mistralai.client import Mistral
        return Mistral(api_key=api_key)
    raise ValueError(f"Proveedor desconocido: {proveedor_id}")


def _llamar_api_openai_compat(client, proveedor_id, modelo, mensajes, max_tokens):
    """Llama a la API y devuelve (texto, finish_reason, tok_in, tok_out)."""
    if proveedor_id == "groq":
        resp = client.chat.completions.create(
            model=modelo, messages=mensajes,
            temperature=0.3, top_p=0.9, max_tokens=max_tokens,
        )
        u = resp.usage or {}
        return (resp.choices[0].message.content.strip(),
                resp.choices[0].finish_reason,
                getattr(u, "prompt_tokens", 0),
                getattr(u, "completion_tokens", 0))
    elif proveedor_id == "mistral":
        resp = client.chat.complete(
            model=modelo, messages=mensajes,
            temperature=0.3, max_tokens=max_tokens,
        )
        u = resp.usage or {}
        return (resp.choices[0].message.content.strip(),
                resp.choices[0].finish_reason,
                getattr(u, "prompt_tokens", 0),
                getattr(u, "completion_tokens", 0))


def clasificar_lote_openai_compat(client, proveedor_id, modelo, textos):
    """Clasifica un lote. Devuelve lista de etiquetas o None si error puntual."""
    numerados = "\n".join(f"{i}. {t[:200]}" for i, t in enumerate(textos))
    mensajes = [
        {"role": "system", "content": "Eres un clasificador de sentimientos experto en español."},
        {"role": "user",   "content": f"{SYSTEM_PROMPT}\n\nComentarios:\n{numerados}"},
    ]
    t0 = time.time()
    try:
        texto_resp, finish_reason, tok_in, tok_out = _llamar_api_openai_compat(
            client, proveedor_id, modelo, mensajes, max_tokens=1500)
        latencia_ms = int((time.time() - t0) * 1000)
        texto_resp = limpiar_json(texto_resp)

        if finish_reason == "length":
            print("   ⚠️ Respuesta truncada (finish_reason=length). Lote omitido.")
            _log_telemetria(timestamp=datetime.now().isoformat(), proveedor=proveedor_id,
                            modelo=modelo, n_comentarios=len(textos), tokens_in=tok_in,
                            tokens_out=tok_out, latencia_ms=latencia_ms,
                            finish_reason=finish_reason, parse_ok=False)
            return None

        datos = json.loads(texto_resp)
        etiquetas = ["NEU"] * len(textos)
        for item in datos:
            idx = item.get("index")
            label = str(item.get("label", "NEU")).upper()
            if idx is not None and 0 <= idx < len(textos):
                etiquetas[idx] = label if label in ("POS", "NEG", "NEU") else "NEU"
        _log_telemetria(timestamp=datetime.now().isoformat(), proveedor=proveedor_id,
                        modelo=modelo, n_comentarios=len(textos), tokens_in=tok_in,
                        tokens_out=tok_out, latencia_ms=latencia_ms,
                        finish_reason=finish_reason, parse_ok=True)
        return etiquetas

    except Exception as e:
        err = str(e)
        if "rate_limit_exceeded" in err and any(k in err for k in ("per day", "TPD", "per_day")):
            raise RateLimitDiaria(err)
        if "model_decommissioned" in err or "decommissioned" in err:
            raise RuntimeError(f"\n❌ MODELO DADO DE BAJA: {modelo}")
        print(f"   ⚠️ Error puntual: {err[:150]}")
        return None


# ─── Proveedor: Gemini ───────────────────────────────────────────────────────

def clasificar_lote_gemini(client, modelo, textos, modelo_fallback=None):
    """Clasifica un lote con Gemini. Devuelve lista de etiquetas o None si fallo."""
    numerados = "\n".join(f"{i}. {t[:200]}" for i, t in enumerate(textos))
    prompt = f"{SYSTEM_PROMPT}\n\nComentarios:\n{numerados}"

    t0 = time.time()
    for intento in range(3):
        try:
            mod_actual = modelo if intento < 2 else (modelo_fallback or modelo)
            response = client.models.generate_content(
                model=mod_actual,
                contents=prompt,
            )
            latencia_ms = int((time.time() - t0) * 1000)
            texto_resp = limpiar_json(response.text)

            tok_in  = getattr(getattr(response, "usage_metadata", None), "prompt_token_count", 0) or 0
            tok_out = getattr(getattr(response, "usage_metadata", None), "candidates_token_count", 0) or 0

            datos = json.loads(texto_resp)
            etiquetas = ["NEU"] * len(textos)
            for item in datos:
                idx = item.get("index")
                label = str(item.get("label", "NEU")).upper()
                if idx is not None and 0 <= idx < len(textos):
                    etiquetas[idx] = label if label in ("POS", "NEG", "NEU") else "NEU"
            _log_telemetria(timestamp=datetime.now().isoformat(), proveedor="gemini",
                            modelo=mod_actual, n_comentarios=len(textos), tokens_in=tok_in,
                            tokens_out=tok_out, latencia_ms=latencia_ms,
                            finish_reason="stop", parse_ok=True)
            return etiquetas

        except Exception as e:
            err = str(e)
            if "503" in err or "overloaded" in err.lower() or "unavailable" in err.lower():
                wait = 15 * (intento + 1)
                print(f"   ⚠️ Gemini 503 (intento {intento+1}/3), esperando {wait}s…")
                time.sleep(wait)
            else:
                print(f"   ⚠️ Error Gemini: {err[:150]}")
                return None
    print("   ❌ Gemini: reintentos agotados, lote omitido.")
    return None


# ─── Dispatcher principal ────────────────────────────────────────────────────

def analizar_sentimiento(df, csv_file, proveedor_id):
    """
    Analiza sentimiento del DataFrame con el proveedor indicado.

    Parámetros
    ----------
    df          : pd.DataFrame con columna de texto
    csv_file    : ruta al CSV original (para checkpoint y salida)
    proveedor_id: "roberta" | "groq" | "mistral" | "gemini"

    Devuelve
    --------
    pd.DataFrame con columna 'sentiment' (POS/NEG/NEU/None), o None si error.
    """
    cfg = PROVEEDORES.get(proveedor_id)
    if cfg is None:
        print(f"❌ Proveedor desconocido: {proveedor_id}")
        return None

    print(f"\n{'─'*60}")
    print(f"  Proveedor : {cfg['nombre']}")
    print(f"  Tipo      : {cfg['tipo']}")
    if cfg["tipo"] != "local":
        print(f"  Modelo    : {cfg['modelo']}")
    print(f"{'─'*60}")

    # Detectar columna de texto
    col_texto = detectar_columna_texto(df)
    if col_texto is None:
        print(f"❌ Columna de texto no encontrada. Columnas: {list(df.columns)}")
        return None
    print(f"  Columna texto : '{col_texto}'")

    # Filtrar replies
    if 'is_reply' in df.columns:
        df_f = df[df['is_reply'] == 0].reset_index(drop=True)
        print(f"  Comentarios directos: {len(df_f):,} (de {len(df):,} totales)")
    else:
        df_f = df.reset_index(drop=True)
        print(f"  Comentarios: {len(df_f):,}")

    if len(df_f) == 0:
        print("  ⚠️ No hay comentarios para analizar")
        return None

    # ── RoBERTa local (sin API, sin checkpoint) ──────────────────────────────
    if cfg["tipo"] == "local":
        etiquetas_lista = clasificar_roberta(df_f, col_texto)
        if etiquetas_lista is None:
            return None
        df_f['sentiment'] = etiquetas_lista
        _guardar_y_mostrar(df_f, csv_file, proveedor_id)
        return df_f

    # ── APIs externas (Groq / Mistral / Gemini) ──────────────────────────────
    api_key = os.getenv(cfg.get("api_key_env", ""), "")
    if not api_key:
        print(f"  ❌ {cfg.get('api_key_env')} no configurada en config/.env")
        return None

    # Clave estable por comentario
    col_id = detectar_columna_id(df_f)
    claves = [clave_estable(df_f.iloc[i].to_dict(), col_id, col_texto)
              for i in range(len(df_f))]
    fuente = f"columna '{col_id}'" if col_id else "hash MD5 del texto"
    print(f"  Clave checkpoint  : {fuente}")

    # Checkpoint
    ckpt_path = get_checkpoint_path(csv_file, proveedor_id)
    etiquetas = load_checkpoint(ckpt_path)
    etiquetas = _migrar_checkpoint_si_necesario(ckpt_path, etiquetas, len(df_f))

    pendientes = [i for i in range(len(df_f)) if claves[i] not in etiquetas]
    n_pendientes = len(pendientes)
    print(f"  Por procesar      : {n_pendientes:,}")

    # Estimación de tiempo
    if proveedor_id == "groq":
        tokens_est = n_pendientes * 35
        dias_est = tokens_est / cfg["limite_diario"]
        if dias_est > 1:
            print(f"  ⏱️  ~{dias_est:.0f} días con Groq free ({tokens_est:,} tokens / 100K/día)")
    elif proveedor_id == "mistral":
        horas_est = (n_pendientes / BATCH_SIZE) * cfg["sleep"] / 3600
        print(f"  ⏱️  ~{horas_est:.1f}h con Mistral free (2 req/min)")

    # Crear cliente
    try:
        if cfg["tipo"] == "openai_compat":
            client = _crear_cliente_openai_compat(proveedor_id, api_key)
        elif cfg["tipo"] == "gemini":
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            client = genai
        else:
            raise ValueError(f"Tipo de proveedor no soportado: {cfg['tipo']}")
    except ImportError as e:
        pkg_map = {"groq": "groq", "mistral": "mistralai", "gemini": "google-generativeai"}
        print(f"  ❌ Librería no instalada. Ejecuta: pip install {pkg_map.get(proveedor_id, '')}")
        return None

    # Bucle de clasificación
    try:
        for lote_num, i in enumerate(range(0, n_pendientes, BATCH_SIZE)):
            indices_lote = pendientes[i:i + BATCH_SIZE]
            textos = [str(df_f.loc[idx, col_texto])[:200] for idx in indices_lote]

            print(f"  Lote {lote_num+1:>4}: {len(textos)} coment...", end=" ", flush=True)

            if cfg["tipo"] == "openai_compat":
                resultado = clasificar_lote_openai_compat(
                    client, proveedor_id, cfg["modelo"], textos)
            else:  # gemini
                resultado = clasificar_lote_gemini(
                    client, cfg["modelo"], textos,
                    modelo_fallback=cfg.get("modelo_fallback"))

            if resultado is not None:
                for idx, label in zip(indices_lote, resultado):
                    etiquetas[claves[idx]] = label
                print(f"✓  (clasificados: {len(etiquetas):,})")
            else:
                print("⚠️  omitido — error de API, no se escribe NEU")

            if (lote_num + 1) % 10 == 0:
                save_checkpoint(ckpt_path, etiquetas)
                print(f"  💾 Checkpoint guardado ({len(etiquetas):,})")

            time.sleep(cfg["sleep"])

    except RateLimitDiaria:
        print(f"\n⏸️  LÍMITE DIARIO ALCANZADO")
        print(f"   Clasificados: {len(etiquetas):,} / {len(df_f):,}")
        save_checkpoint(ckpt_path, etiquetas)
        print("   ✅ Checkpoint guardado. Vuelve mañana para continuar.")
        return None
    except KeyboardInterrupt:
        print(f"\n⏹️  Interrumpido por el usuario.")
        save_checkpoint(ckpt_path, etiquetas)
        print(f"   ✅ {len(etiquetas):,} comentarios guardados en checkpoint.")
        return None

    save_checkpoint(ckpt_path, etiquetas)

    # Aplicar etiquetas (None para no clasificados)
    df_f['sentiment'] = [etiquetas.get(k, None) for k in claves]
    _guardar_y_mostrar(df_f, csv_file, proveedor_id)
    return df_f


def _guardar_y_mostrar(df_f, csv_file, proveedor_id):
    """Muestra estadísticas y guarda el CSV resultado."""
    total = len(df_f)
    clasificados = df_f['sentiment'].notna().sum()
    sin_clasificar = total - clasificados
    stats = df_f['sentiment'].value_counts(dropna=True)

    print(f"\n  Resultados ({clasificados:,} clasificados / {total:,} total):")
    for label, count in stats.items():
        bar = "█" * int(count / total * 30)
        print(f"    {label}: {count:>7,} ({count/total*100:.1f}%) {bar}")
    if sin_clasificar > 0:
        print(f"    ⚠️  Sin clasificar: {sin_clasificar:,} ({sin_clasificar/total*100:.1f}%)"
              " — errores de API, vuelve a ejecutar para reintentar")

    sufijo = "roberta" if proveedor_id == "roberta" else proveedor_id
    output_csv = csv_file.replace(".csv", f"_con_sentimiento_{sufijo}.csv")
    df_f.to_csv(output_csv, index=False, encoding="utf-8")
    print(f"\n  ✅ CSV guardado: {os.path.basename(output_csv)}")


# ─── Menú interactivo ────────────────────────────────────────────────────────

def seleccionar_proveedor():
    print("\n" + "=" * 60)
    print("  ¿Qué proveedor de IA usar para el análisis de sentimiento?")
    print("=" * 60)
    ids = list(PROVEEDORES.keys())
    for i, pid in enumerate(ids, 1):
        cfg = PROVEEDORES[pid]
        if cfg["tipo"] == "local":
            estado = "✅ Sin API key necesaria"
        else:
            api_key = os.getenv(cfg.get("api_key_env", ""), "")
            estado = "✅ API key configurada" if api_key else "❌ Sin API key"
        print(f"  {i}. {cfg['nombre']:20s} — {cfg['descripcion']}")
        print(f"       {estado}")
    print("=" * 60)

    while True:
        opcion = input(f"  Selecciona (1-{len(ids)}): ").strip()
        try:
            idx = int(opcion) - 1
            if 0 <= idx < len(ids):
                return ids[idx]
        except ValueError:
            pass
        print(f"  Opción no válida. Introduce un número del 1 al {len(ids)}.")


def main():
    print("=" * 60)
    print("  ANÁLISIS DE SENTIMIENTO CON IA")
    print("  RoBERTa · Groq · Mistral · Gemini")
    print("=" * 60)

    # Seleccionar CSV
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    csv_file = filedialog.askopenfilename(
        title="Selecciona CSV de comentarios",
        filetypes=[("CSV Files", "*.csv")],
        initialdir=DATA_DIR,
    )
    root.destroy()

    if not csv_file:
        print("Operación cancelada.")
        return

    print(f"\n  Archivo: {os.path.basename(csv_file)}")
    df = pd.read_csv(csv_file)
    print(f"  Filas  : {len(df):,}")

    proveedor_id = seleccionar_proveedor()
    analizar_sentimiento(df, csv_file, proveedor_id)
    print("\n✅ Proceso finalizado.")


if __name__ == "__main__":
    main()
