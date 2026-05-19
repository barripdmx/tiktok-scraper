# -*- coding: utf-8 -*-
"""
Análisis de sentimiento con IA - Groq o Mistral
Selección interactiva de proveedor al iniciar.
"""

import os
import sys
import json
import time
import pandas as pd
from dotenv import load_dotenv
import tkinter as tk
from tkinter import filedialog

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CONFIG_DIR = os.path.join(BASE_DIR, "config")
OUTPUT_BASE = os.path.join(BASE_DIR, "outputs")

load_dotenv(os.path.join(CONFIG_DIR, ".env"))

# --- Configuración de proveedores ---
PROVEEDORES = {
    "groq": {
        "nombre":        "Groq",
        "modelo":        "llama-3.3-70b-versatile",
        "api_key_env":   "GROQ_API_KEY",
        "sleep":         0.5,    # 30 req/min → 0.5s entre lotes
        "limite_diario": 100_000,
        "descripcion":   "Rápido · 100K tokens/día · ~16 días para 46K comentarios",
    },
    "mistral": {
        "nombre":        "Mistral",
        "modelo":        "open-mistral-nemo",
        "api_key_env":   "MISTRAL_API_KEY",
        "sleep":         31,     # 2 req/min → 31s entre lotes
        "limite_diario": 33_000_000,   # ~1B tokens/mes
        "descripcion":   "1B tokens/mes · 2 req/min · ~8h seguidas para 46K comentarios",
    },
}

BATCH_SIZE = 50

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
    pass


# ─── Clientes de API ────────────────────────────────────────────────────────

def crear_cliente(proveedor_id, api_key):
    """Crea el cliente del proveedor seleccionado."""
    if proveedor_id == "groq":
        from groq import Groq
        return Groq(api_key=api_key)
    elif proveedor_id == "mistral":
        try:
            from mistralai import Mistral          # mistralai < 2.x
        except ImportError:
            from mistralai.client import Mistral   # mistralai >= 2.x
        return Mistral(api_key=api_key)
    raise ValueError(f"Proveedor desconocido: {proveedor_id}")


def llamar_api(client, proveedor_id, modelo, mensajes, max_tokens):
    """Llama a la API del proveedor y devuelve el texto de la respuesta."""
    if proveedor_id == "groq":
        resp = client.chat.completions.create(
            model=modelo,
            messages=mensajes,
            temperature=0.3,
            top_p=0.9,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content.strip(), resp.choices[0].finish_reason

    elif proveedor_id == "mistral":
        resp = client.chat.complete(
            model=modelo,
            messages=mensajes,
            temperature=0.3,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content.strip(), resp.choices[0].finish_reason


# ─── Clasificación ──────────────────────────────────────────────────────────

def limpiar_json(texto):
    """Elimina bloques markdown si el modelo los devuelve."""
    t = texto.strip()
    if t.startswith("```json"):
        t = t[7:]
    if t.startswith("```"):
        t = t[3:]
    if t.endswith("```"):
        t = t[:-3]
    return t.strip()


def clasificar_lote(client, proveedor_id, modelo, textos):
    """
    Clasifica un lote de textos. Devuelve lista de etiquetas o None si fallo puntual.
    Lanza RateLimitDiaria si se agota el cupo diario.
    """
    numerados = "\n".join(f"{i}. {t[:200]}" for i, t in enumerate(textos))
    mensajes = [
        {"role": "system", "content": "Eres un clasificador de sentimientos experto en español."},
        {"role": "user",   "content": f"{SYSTEM_PROMPT}\n\nComentarios:\n{numerados}"},
    ]

    try:
        texto_resp, finish_reason = llamar_api(client, proveedor_id, modelo, mensajes, max_tokens=1500)
        texto_resp = limpiar_json(texto_resp)

        if finish_reason == "length":
            print(f"   ⚠️ Respuesta truncada (finish_reason=length). Lote omitido.")
            return None

        datos = json.loads(texto_resp)
        etiquetas = ["NEU"] * len(textos)
        for item in datos:
            idx = item.get("index")
            label = str(item.get("label", "NEU")).upper()
            if idx is not None and 0 <= idx < len(textos):
                etiquetas[idx] = label if label in ("POS", "NEG", "NEU") else "NEU"
        return etiquetas

    except Exception as e:
        err = str(e)
        # Límite diario de tokens (Groq TPD o Mistral mensual)
        if "rate_limit_exceeded" in err and any(k in err for k in ("per day", "TPD", "tokens per day", "per_day")):
            raise RateLimitDiaria(err)
        # Modelo dado de baja
        if "model_decommissioned" in err or "decommissioned" in err:
            raise RuntimeError(f"\n❌ MODELO DADO DE BAJA: {modelo}")
        print(f"   ⚠️ Error puntual: {err[:150]}")
        return None


# ─── Checkpoint ─────────────────────────────────────────────────────────────

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


# ─── Utilidades ─────────────────────────────────────────────────────────────

def detectar_columna_texto(df):
    """Detecta automáticamente la columna de texto del comentario."""
    for col in ['texto', 'comment_text', 'text', 'comentario', 'content', 'body']:
        if col in df.columns:
            return col
    for col in df.columns:
        if any(k in col.lower() for k in ('text', 'texto', 'comment')):
            return col
    return None


def seleccionar_proveedor():
    """Muestra menú para seleccionar proveedor de IA."""
    print("\n" + "=" * 60)
    print("  ¿Qué proveedor de IA usar?")
    print("=" * 60)
    for i, (pid, cfg) in enumerate(PROVEEDORES.items(), 1):
        api_key = os.getenv(cfg["api_key_env"], "")
        estado = "✅ API key configurada" if api_key else "❌ Sin API key"
        print(f"  {i}. {cfg['nombre']:10s} — {cfg['descripcion']}")
        print(f"             {estado}")
    print("=" * 60)

    while True:
        opcion = input("  Selecciona (1/2): ").strip()
        ids = list(PROVEEDORES.keys())
        if opcion == "1":
            return ids[0]
        elif opcion == "2":
            return ids[1]
        print("  Opción no válida. Introduce 1 o 2.")


# ─── Función principal ──────────────────────────────────────────────────────

def analizar_sentimiento(df, csv_file, proveedor_id):
    """Analiza sentimientos usando el proveedor indicado."""
    cfg = PROVEEDORES[proveedor_id]
    api_key = os.getenv(cfg["api_key_env"], "")

    print(f"\n--- Analizando con {cfg['nombre']} ---")
    print(f"   Modelo : {cfg['modelo']}")
    print(f"   Sleep  : {cfg['sleep']}s entre lotes")

    if not api_key:
        print(f"   ❌ {cfg['api_key_env']} no configurada en config/.env")
        return None

    # Detectar columna de texto
    col_texto = detectar_columna_texto(df)
    if col_texto is None:
        print(f"   ❌ Columna de texto no encontrada. Columnas: {list(df.columns)}")
        return None
    print(f"   Columna de texto: '{col_texto}'")

    # Filtrar replies si existe la columna
    if 'is_reply' in df.columns:
        df_f = df[df['is_reply'] == 0].reset_index(drop=True)
        print(f"   Comentarios directos: {len(df_f):,} (de {len(df):,} totales)")
    else:
        df_f = df.reset_index(drop=True)
        print(f"   Comentarios: {len(df_f):,} (sin columna 'is_reply')")

    if len(df_f) == 0:
        print("   ⚠️ No hay comentarios para analizar")
        return None

    # Checkpoint
    ckpt_path = get_checkpoint_path(csv_file, proveedor_id)
    etiquetas = load_checkpoint(ckpt_path)

    # Estimación de tiempo
    pendientes = [i for i in range(len(df_f)) if str(i) not in etiquetas]
    n_pendientes = len(pendientes)
    print(f"   Por procesar: {n_pendientes:,}")

    tokens_est = n_pendientes * 35
    if proveedor_id == "groq":
        dias_est = tokens_est / cfg["limite_diario"]
        if dias_est > 1:
            print(f"   ⏱️  Groq free: ~{dias_est:.0f} días para completar ({tokens_est:,} tokens / 100K límite diario)")
    elif proveedor_id == "mistral":
        horas_est = (n_pendientes / BATCH_SIZE) * cfg["sleep"] / 3600
        print(f"   ⏱️  Mistral free: ~{horas_est:.1f} horas seguidas (2 req/min)")

    # Crear cliente
    try:
        client = crear_cliente(proveedor_id, api_key)
    except ImportError as e:
        pkg = "groq" if proveedor_id == "groq" else "mistralai"
        print(f"   ❌ Librería no instalada. Ejecuta: pip install {pkg}")
        return None

    # Bucle de clasificación
    try:
        for lote_num, i in enumerate(range(0, n_pendientes, BATCH_SIZE)):
            indices_lote = pendientes[i:i + BATCH_SIZE]
            textos = [str(df_f.loc[idx, col_texto])[:200] for idx in indices_lote]

            print(f"   Lote {lote_num+1:>4}: {len(textos)} comentarios...", end=" ", flush=True)
            resultado = clasificar_lote(client, proveedor_id, cfg["modelo"], textos)

            if resultado is not None:
                for idx, label in zip(indices_lote, resultado):
                    etiquetas[str(idx)] = label
                print(f"✓  (clasificados: {len(etiquetas):,})")
            else:
                print("⚠️  omitido")

            # Checkpoint cada 10 lotes
            if (lote_num + 1) % 10 == 0:
                save_checkpoint(ckpt_path, etiquetas)
                print(f"   💾 Checkpoint guardado ({len(etiquetas):,})")

            time.sleep(cfg["sleep"])

    except RateLimitDiaria:
        print(f"\n⏸️  LÍMITE DIARIO ALCANZADO")
        print(f"   Clasificados: {len(etiquetas):,} / {len(df_f):,}")
        print(f"   Pendientes  : {len(df_f) - len(etiquetas):,}")
        save_checkpoint(ckpt_path, etiquetas)
        print(f"   ✅ Checkpoint guardado. Ejecuta de nuevo mañana para continuar.")
        return None
    except KeyboardInterrupt:
        print(f"\n⏹️  Interrumpido por el usuario.")
        save_checkpoint(ckpt_path, etiquetas)
        print(f"   ✅ {len(etiquetas):,} comentarios guardados en checkpoint.")
        return None

    save_checkpoint(ckpt_path, etiquetas)

    # Aplicar etiquetas al DataFrame
    df_f['sentiment'] = df_f.index.map(lambda x: etiquetas.get(str(x), "NEU"))

    # Estadísticas
    stats = df_f['sentiment'].value_counts()
    total = len(df_f)
    print(f"\n   Resultados finales:")
    for label, count in stats.items():
        bar = "█" * int(count / total * 30)
        print(f"      {label}: {count:>7,} ({count/total*100:.1f}%) {bar}")

    # Guardar CSV
    output_csv = csv_file.replace(".csv", f"_con_sentimientos_{proveedor_id}.csv")
    df_f.to_csv(output_csv, index=False, encoding="utf-8")
    print(f"\n   ✅ CSV guardado: {os.path.basename(output_csv)}")

    return df_f


# ─── Main ───────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  ANÁLISIS DE SENTIMIENTO CON IA")
    print("  Groq · Mistral")
    print("=" * 60)

    # Seleccionar CSV
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    csv_file = filedialog.askopenfilename(
        title="Selecciona CSV de comentarios",
        filetypes=[("CSV Files", "*.csv")],
        initialdir=os.path.join(BASE_DIR, "data")
    )
    root.destroy()

    if not csv_file:
        print("Operación cancelada.")
        return

    print(f"\nArchivo: {os.path.basename(csv_file)}")
    df = pd.read_csv(csv_file)
    print(f"Filas  : {len(df):,}")

    # Seleccionar proveedor
    proveedor_id = seleccionar_proveedor()

    # Analizar
    analizar_sentimiento(df, csv_file, proveedor_id)
    print("\n✅ Proceso finalizado.")


if __name__ == "__main__":
    main()
