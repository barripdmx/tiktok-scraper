"""
Análisis de sentimiento con Groq - 3-5x más rápido que Gemini
"""

import os
import json
import time
import pandas as pd
from groq import Groq
from dotenv import load_dotenv
import tkinter as tk
from tkinter import filedialog

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CONFIG_DIR = os.path.join(BASE_DIR, "config")
OUTPUT_BASE = os.path.join(BASE_DIR, "outputs")

load_dotenv(os.path.join(CONFIG_DIR, ".env"))

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = "mixtral-8x7b-32768"  # Rápido y preciso
BATCH_SIZE = 50
SLEEP_BETWEEN = 0.5

SYSTEM_PROMPT = """Eres un clasificador de sentimiento para comentarios de TikTok en español.
Clasifica cada comentario con exactamente una de estas etiquetas:
- POS: opinión positiva, apoyo, halago, humor positivo
- NEG: crítica, insulto, queja, ironía negativa
- NEU: neutro, pregunta, sin carga emocional clara

Devuelve un JSON array con un objeto por comentario, en el mismo orden:
[{"index": 0, "label": "POS"}, {"index": 1, "label": "NEG"}, ...]

Solo el JSON array, sin texto adicional."""


def clasificar_lote(client, textos):
    """Envía un lote de textos a Groq."""
    numerados = "\n".join(f"{i}. {t[:300]}" for i, t in enumerate(textos))
    prompt = f"{SYSTEM_PROMPT}\n\nComentarios:\n{numerados}"

    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": "Eres un clasificador de sentimientos experto."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            top_p=0.9,
            max_tokens=500
        )

        respuesta_text = response.choices[0].message.content.strip()

        # Limpiar markdown si lo hay
        if respuesta_text.startswith("```json"):
            respuesta_text = respuesta_text[7:]
        if respuesta_text.startswith("```"):
            respuesta_text = respuesta_text[3:]
        if respuesta_text.endswith("```"):
            respuesta_text = respuesta_text[:-3]

        datos = json.loads(respuesta_text.strip())
        etiquetas = ["NEU"] * len(textos)

        for item in datos:
            idx = item.get("index")
            label = str(item.get("label", "NEU")).upper()
            if idx is not None and 0 <= idx < len(textos):
                if label not in ("POS", "NEG", "NEU"):
                    label = "NEU"
                etiquetas[idx] = label
        return etiquetas

    except Exception as e:
        print(f"   Error: {e}")
        return ["NEU"] * len(textos)


def get_checkpoint_path(csv_file):
    return csv_file.replace(".csv", "_groq_checkpoint.json")


def load_checkpoint(checkpoint_path):
    if os.path.exists(checkpoint_path):
        with open(checkpoint_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"   ✓ Checkpoint: {len(data):,} comentarios ya procesados")
        return data
    return {}


def save_checkpoint(checkpoint_path, etiquetas_dict):
    with open(checkpoint_path, "w", encoding="utf-8") as f:
        json.dump(etiquetas_dict, f)


def detectar_columna_texto(df):
    """Detecta automáticamente qué columna contiene el texto del comentario."""
    candidatos = ['texto', 'comment_text', 'text', 'comentario', 'content', 'body']
    for col in candidatos:
        if col in df.columns:
            return col
    # Fallback: buscar columna con 'text' en el nombre
    for col in df.columns:
        if 'text' in col.lower() or 'texto' in col.lower() or 'comment' in col.lower():
            return col
    return None


def analizar_sentimiento_groq(df, csv_file):
    """Analizar sentimientos con Groq."""
    print("\n--- Analizando sentimiento con Groq ---")
    print(f"   Modelo: {GROQ_MODEL}")
    print(f"   Velocidad: ⚡⚡⚡ (3-5x más rápido que Gemini)")

    if not GROQ_API_KEY:
        print("   ❌ Error: GROQ_API_KEY no configurada en config/.env")
        return None

    # Detectar columna de texto
    col_texto = detectar_columna_texto(df)
    if col_texto is None:
        print(f"   ❌ No se encontró columna de texto. Columnas disponibles: {list(df.columns)}")
        return None
    print(f"   Columna de texto: '{col_texto}'")

    # Filtrar comentarios directos (si la columna existe)
    if 'is_reply' in df.columns:
        df_filtered = df[df['is_reply'] == 0].reset_index(drop=True)
        print(f"   Total comentarios: {len(df)}")
        print(f"   Comentarios directos: {len(df_filtered)}")
    else:
        df_filtered = df.reset_index(drop=True)
        print(f"   Total comentarios: {len(df_filtered)} (columna 'is_reply' no encontrada, se analizan todos)")

    if len(df_filtered) == 0:
        print("   ⚠️ No hay comentarios para analizar")
        return None

    # Checkpoint
    checkpoint_path = get_checkpoint_path(csv_file)
    etiquetas_dict = load_checkpoint(checkpoint_path)

    client = Groq(api_key=GROQ_API_KEY)

    # Procesar comentarios
    indices_por_procesar = [i for i in range(len(df_filtered)) if str(i) not in etiquetas_dict]
    print(f"   Por procesar: {len(indices_por_procesar):,}")

    for lote_num, i in enumerate(range(0, len(indices_por_procesar), BATCH_SIZE)):
        indices_lote = indices_por_procesar[i:i+BATCH_SIZE]
        textos = [str(df_filtered.loc[idx, col_texto])[:300] for idx in indices_lote]

        print(f"   Lote {lote_num+1}: {len(textos)} comentarios...", end=" ")
        etiquetas = clasificar_lote(client, textos)

        for idx, etiqueta in zip(indices_lote, etiquetas):
            etiquetas_dict[str(idx)] = etiqueta

        print(f"✓ (Total: {len(etiquetas_dict):,})")
        time.sleep(SLEEP_BETWEEN)

    save_checkpoint(checkpoint_path, etiquetas_dict)

    # Aplicar etiquetas
    df_filtered['sentiment'] = df_filtered.index.map(
        lambda x: etiquetas_dict.get(str(x), "NEU")
    )

    # Estadísticas
    stats = df_filtered['sentiment'].value_counts()
    print(f"\n   Resultados:")
    for label, count in stats.items():
        pct = 100 * count / len(df_filtered)
        print(f"      {label}: {count:,} ({pct:.1f}%)")

    # Guardar CSV
    output_csv = csv_file.replace(".csv", "_con_sentimientos_groq.csv")
    df_filtered.to_csv(output_csv, index=False, encoding="utf-8")
    print(f"\n   ✓ CSV guardado: {output_csv}")

    return df_filtered


def main():
    print("=" * 60)
    print("ANÁLISIS DE SENTIMIENTO CON GROQ")
    print("=" * 60)

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
        print("Operación cancelada")
        return

    print(f"\nCargando: {csv_file}")
    df = pd.read_csv(csv_file)

    analizar_sentimiento_groq(df, csv_file)
    print("\n✅ Completado")


if __name__ == "__main__":
    main()
