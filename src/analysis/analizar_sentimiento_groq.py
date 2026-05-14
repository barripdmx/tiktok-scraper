"""
Análisis de sentimiento de comentarios TikTok usando Groq en modo gratuito.
- API gratuita: https://console.groq.com — crea cuenta y genera API key
- Filtra comentarios directos (is_reply == 0)
- Procesa en lotes pequeños para respetar límites gratuitos
- Guarda CSV con columna 'sentimiento' para reutilizar sin repetir el análisis
- Genera las mismas gráficas que analitica_comentarios.py
- Checkpoint para reanudar si se interrumpe

INSTALACIÓN:
    pip install groq pandas matplotlib python-dotenv

CONFIGURACIÓN GRATUITA CONSERVADORA:
    - Modelo: llama-3.1-8b-instant
    - Lotes de 20 comentarios
    - 60s entre lotes para reducir errores 429 por tokens/minuto
    - Si se agota el límite diario, continúa otro día con el checkpoint
"""

import os
import json
import time
import random
import pandas as pd
import matplotlib.pyplot as plt
import tkinter as tk
from tkinter import filedialog, simpledialog
from groq import Groq
from dotenv import load_dotenv

# Carga variables desde config/.env y, como respaldo, desde .env en la raiz.
BASE_DIR   = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CONFIG_DIR = os.path.join(BASE_DIR, "config")
OUTPUT_BASE = os.path.join(BASE_DIR, "outputs")

load_dotenv(os.path.join(CONFIG_DIR, ".env"))
load_dotenv()

# --- CONFIGURACIÓN ---
OUTPUT_FOLDER = OUTPUT_BASE
GROQ_API_KEY  = os.getenv("GROQ_API_KEY", "")  # lee del .env → variable GROQ_API_KEY
GROQ_MODEL     = "llama-3.1-8b-instant"  # más margen diario en el plan gratuito
FALLBACK_MODEL = GROQ_MODEL              # no cambiar a modelos con límites gratis más bajos
BATCH_SIZE     = 20                      # comentarios por request
RETRY_DELAY    = 20                      # segundos base entre reintentos
SLEEP_BETWEEN  = 60.0                    # segundos entre lotes para respetar tokens/minuto

CHECKPOINT_INTERVAL = 5  # guardar checkpoint cada N lotes

SYSTEM_PROMPT = """Eres un clasificador de sentimiento para comentarios de TikTok en español.
Clasifica cada comentario con exactamente una de estas etiquetas:
- POS: opinión positiva, apoyo, halago, humor positivo
- NEG: crítica, insulto, queja, ironía negativa
- NEU: neutro, pregunta, sin carga emocional clara

Devuelve ÚNICAMENTE un JSON array con un objeto por comentario, en el mismo orden recibido.
Formato exacto: [{"index": 0, "label": "POS"}, {"index": 1, "label": "NEG"}, ...]

Sin texto adicional. Sin explicaciones. Solo el JSON array."""


def create_output_folder(file_id=None):
    global OUTPUT_FOLDER
    if file_id:
        project = file_id.split('_videos')[0] if '_videos' in file_id else file_id
        OUTPUT_FOLDER = os.path.join(OUTPUT_BASE, project, "polaridad_ia")
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)


def save_plot(filename, tight=True):
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    path = os.path.join(OUTPUT_FOLDER, filename)
    plt.savefig(path, bbox_inches='tight' if tight else None)
    print(f"-> Guardado: {filename}")
    plt.close()


def clasificar_lote(client, textos, model=None):
    """Envía un lote de textos a Groq y devuelve lista de etiquetas."""
    if model is None:
        model = GROQ_MODEL

    numerados = "\n".join(f"{i}. {t[:300]}" for i, t in enumerate(textos))
    user_msg  = f"Clasifica estos comentarios:\n\n{numerados}"

    for intento in range(5):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": user_msg}
                ],
                temperature=0.1,
                max_tokens=1024,
            )
            texto = response.choices[0].message.content.strip()

            # Limpiar posibles bloques markdown ```json ... ```
            if "```" in texto:
                texto = texto.split("```")[1]
                if texto.startswith("json"):
                    texto = texto[4:]
                texto = texto.strip()

            datos = json.loads(texto)
            etiquetas = ["NEU"] * len(textos)
            for item in datos:
                idx   = item.get("index")
                label = str(item.get("label", "NEU")).upper()
                if idx is not None and 0 <= idx < len(textos):
                    if label not in ("POS", "NEG", "NEU"):
                        label = "NEU"
                    etiquetas[idx] = label
            return etiquetas

        except Exception as e:
            msg = str(e)

            # Rate limit (429) — esperar y reintentar
            if "429" in msg or "rate" in msg.lower():
                if intento == 4:
                    raise RuntimeError(
                        "Rate limit persistente de Groq. Guardando checkpoint; "
                        "reintenta mas tarde o manana."
                    ) from e
                espera = 60 + random.uniform(0, 10)
                print(f"\n   Rate limit. Esperando {espera:.0f}s...")
                time.sleep(espera)
                continue

            # Errores permanentes — no reintentar
            if any(c in msg for c in ["400", "401", "403", "404"]):
                print(f"\n   Error permanente: {e}")
                raise

            # Otros errores transitorios — backoff con jitter
            base   = RETRY_DELAY * (2 ** intento)
            jitter = random.uniform(0, base * 0.2)
            espera = base + jitter
            print(f"\n   Reintento {intento+1}/5 [{model}]: {e}")
            print(f"   Esperando {espera:.0f}s...")
            time.sleep(espera)

    return ["NEU"] * len(textos)


def get_checkpoint_path(csv_file):
    return csv_file.replace(".csv", "_groq_checkpoint.json")


def load_checkpoint(checkpoint_path):
    if os.path.exists(checkpoint_path):
        with open(checkpoint_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"   Checkpoint encontrado: {len(data):,} comentarios ya procesados. Continuando...")
        return data
    return {}


def save_checkpoint(checkpoint_path, etiquetas_dict):
    with open(checkpoint_path, "w", encoding="utf-8") as f:
        json.dump(etiquetas_dict, f)


def analizar_sentimiento_groq(df, csv_file):
    print(f"\n--- Analizando sentimiento con Groq [{GROQ_MODEL}] ---")

    api_key = GROQ_API_KEY
    if not api_key:
        root = tk.Tk(); root.withdraw()
        api_key = simpledialog.askstring("API Key", "Introduce tu Groq API Key\n(console.groq.com → API Keys):")
        root.destroy()
    if not api_key:
        print("Sin API key. Abortando.")
        return df

    client = Groq(api_key=api_key)
    checkpoint_path = get_checkpoint_path(csv_file)
    checkpoint = load_checkpoint(checkpoint_path)

    textos = df['texto'].fillna("").astype(str).tolist()
    total  = len(textos)

    model_activo = GROQ_MODEL
    errores_consecutivos = 0
    lotes_desde_ultimo_save = 0

    # Estimación de tiempo
    requests_pendientes = sum(
        1 for i in range(0, total, BATCH_SIZE)
        if not all(str(idx) in checkpoint for idx in range(i, min(i + BATCH_SIZE, total)))
    )
    tiempo_est = requests_pendientes * SLEEP_BETWEEN / 60
    print(f"   {total:,} comentarios | {requests_pendientes:,} lotes pendientes | ~{tiempo_est:.0f} min estimados")

    for i in range(0, total, BATCH_SIZE):
        indices_lote = list(range(i, min(i + BATCH_SIZE, total)))

        # Saltar lotes ya en checkpoint
        if all(str(idx) in checkpoint for idx in indices_lote):
            procesados = min(i + BATCH_SIZE, total)
            print(f"   {procesados:,} / {total:,}  ({procesados/total*100:.1f}%) [cached]", end="\r")
            continue

        lote = [textos[idx] for idx in indices_lote]

        try:
            tags = clasificar_lote(client, lote, model=model_activo)
            errores_consecutivos = 0
        except Exception as e:
            msg = str(e)
            if "Rate limit persistente" in msg or "429" in msg or "rate limit" in msg.lower():
                save_checkpoint(checkpoint_path, checkpoint)
                print("\n   Limite gratuito de Groq alcanzado o demasiado restrictivo ahora.")
                print("   Checkpoint guardado. Los comentarios pendientes no se marcan como neutros.")
                print("   Vuelve a ejecutar el analisis mas tarde o manana para continuar.")
                return None

            errores_consecutivos += 1
            # Cambiar a fallback tras 2 errores consecutivos
            if errores_consecutivos >= 2 and model_activo != FALLBACK_MODEL:
                print(f"\n   ⚠ Cambiando a fallback [{FALLBACK_MODEL}]...")
                model_activo = FALLBACK_MODEL
                errores_consecutivos = 0
            tags = ["NEU"] * len(lote)

        for idx, tag in zip(indices_lote, tags):
            checkpoint[str(idx)] = tag

        lotes_desde_ultimo_save += 1
        if lotes_desde_ultimo_save >= CHECKPOINT_INTERVAL:
            save_checkpoint(checkpoint_path, checkpoint)
            lotes_desde_ultimo_save = 0

        procesados = min(i + BATCH_SIZE, total)
        print(f"   {procesados:,} / {total:,}  ({procesados/total*100:.1f}%) [{model_activo}]", end="\r")
        time.sleep(SLEEP_BETWEEN)

    save_checkpoint(checkpoint_path, checkpoint)

    label_map = {"POS": "positivo", "NEG": "negativo", "NEU": "neutro"}
    df['sentimiento'] = [label_map.get(checkpoint.get(str(i), "NEU"), "neutro") for i in range(total)]

    counts = df['sentimiento'].value_counts()
    print(f"\n-> Distribución:")
    for sent, n in counts.items():
        print(f"   {sent}: {n:,} ({n/total*100:.1f}%)")

    return df


def generar_grafica_sentimiento(df, file_id):
    counts  = df['sentimiento'].value_counts().reindex(["positivo", "neutro", "negativo"], fill_value=0)
    colores = ["#2ecc71", "#95a5a6", "#e74c3c"]
    total   = counts.sum()

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(counts.index, counts.values, color=colores, edgecolor="black", width=0.5)
    for bar, val in zip(bars, counts.values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + total * 0.005,
                f"{val:,}\n({val/total*100:.1f}%)", ha="center", va="bottom", fontsize=11, fontweight="bold")
    ax.set_title(f"Distribución de Sentimiento — Groq / {GROQ_MODEL}\n{file_id}", fontsize=14, fontweight="bold")
    ax.set_ylabel("Número de comentarios", fontsize=12)
    ax.set_ylim(0, counts.max() * 1.15)
    ax.grid(axis="y", linestyle="--", alpha=0.5)
    save_plot(f"{file_id}_sentimiento_distribucion_groq.png")


def generar_evolucion_mensual(df, file_id):
    """Comentarios por mes (absolutos) para cada sentimiento — NO acumulado."""
    if 'fecha' not in df.columns:
        print("-> Sin columna 'fecha'. Omitiendo evolución mensual.")
        return

    df = df.copy()
    df['fecha_dt'] = pd.to_datetime(df['fecha'], errors='coerce')
    df.dropna(subset=['fecha_dt'], inplace=True)
    df['año_mes'] = df['fecha_dt'].dt.to_period('M')

    todos_meses = df['año_mes'].sort_values().unique()
    pos = df[df['sentimiento'] == 'positivo'].groupby('año_mes').size().reindex(todos_meses, fill_value=0)
    neg = df[df['sentimiento'] == 'negativo'].groupby('año_mes').size().reindex(todos_meses, fill_value=0)
    neu = df[df['sentimiento'] == 'neutro'].groupby('año_mes').size().reindex(todos_meses, fill_value=0)
    etiquetas = [str(m) for m in todos_meses]
    x = list(range(len(etiquetas)))

    fig, ax = plt.subplots(figsize=(18, 7))
    ax.plot(x, pos.values, color='#2ecc71', linewidth=2.5, marker='o', markersize=4, label='Positivos')
    ax.fill_between(x, pos.values, alpha=0.12, color='#2ecc71')
    ax.plot(x, neg.values, color='#e74c3c', linewidth=2.5, marker='o', markersize=4, label='Negativos')
    ax.fill_between(x, neg.values, alpha=0.12, color='#e74c3c')
    ax.plot(x, neu.values, color='#95a5a6', linewidth=1.8, marker='o', markersize=3, label='Neutros', alpha=0.7)
    ax.fill_between(x, neu.values, alpha=0.07, color='#95a5a6')

    # Anotar máximos de pos y neg
    idx_max_pos = int(pos.values.argmax())
    idx_max_neg = int(neg.values.argmax())
    ax.annotate(f"Pico: {pos.values[idx_max_pos]:,}", xy=(idx_max_pos, pos.values[idx_max_pos]),
                xytext=(0, 10), textcoords='offset points', ha='center',
                color='#27ae60', fontweight='bold', fontsize=9,
                arrowprops=dict(arrowstyle='->', color='#27ae60', lw=1.2))
    ax.annotate(f"Pico: {neg.values[idx_max_neg]:,}", xy=(idx_max_neg, neg.values[idx_max_neg]),
                xytext=(0, 10), textcoords='offset points', ha='center',
                color='#c0392b', fontweight='bold', fontsize=9,
                arrowprops=dict(arrowstyle='->', color='#c0392b', lw=1.2))

    # Reducir etiquetas si hay muchos meses (mostrar cada N)
    step = max(1, len(etiquetas) // 24)
    ticks_x = x[::step]
    ticks_labels = etiquetas[::step]
    ax.set_xticks(ticks_x)
    ax.set_xticklabels(ticks_labels, rotation=45, ha='right', fontsize=9)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{int(v):,}"))
    ax.set_title(f"Evolución mensual del sentimiento\n{file_id}", fontsize=14, fontweight='bold')
    ax.set_ylabel("Comentarios por mes", fontsize=12)
    ax.set_xlabel("Mes", fontsize=12)
    ax.legend(fontsize=11)
    ax.grid(axis='y', linestyle='--', alpha=0.5)
    plt.tight_layout()
    save_plot(f"{file_id}_sentimiento_mensual_groq.png")


def _detectar_columna_usuario(df):
    """Detecta automáticamente la columna de usuario en el DataFrame."""
    candidatas = ['autor_handle', 'author', 'nickname', 'username', 'user', 'author_id', 'user_id']
    for col in candidatas:
        if col in df.columns:
            return col
    # Búsqueda flexible (case-insensitive, parcial)
    for col in df.columns:
        if any(c in col.lower() for c in ['autor', 'author', 'nick', 'user', 'handle']):
            return col
    return None


def generar_top_usuarios(df, file_id):
    """Top 5 usuarios con más comentarios positivos y negativos, con fecha de primer comentario."""
    col_usuario = _detectar_columna_usuario(df)
    if col_usuario is None:
        print("-> No se encontró columna de usuario. Omitiendo top usuarios.")
        print(f"   Columnas disponibles: {list(df.columns)}")
        return

    print(f"   Columna de usuario detectada: '{col_usuario}'")

    df = df.copy()
    tiene_fecha = 'fecha' in df.columns
    if tiene_fecha:
        df['fecha_dt'] = pd.to_datetime(df['fecha'], errors='coerce')

    TOP_N = 5
    colores_pos = ['#1a9850', '#66bd63', '#a6d96a', '#d9ef8b', '#ffffbf']
    colores_neg = ['#d73027', '#f46d43', '#fdae61', '#fee08b', '#ffffbf']

    fig, axes = plt.subplots(1, 2, figsize=(16, 6))
    fig.suptitle(f"Top {TOP_N} usuarios por sentimiento\n{file_id}", fontsize=14, fontweight='bold')

    for ax, sentimiento, colores, titulo in [
        (axes[0], 'positivo', colores_pos, f'Top {TOP_N} — más comentarios POSITIVOS'),
        (axes[1], 'negativo', colores_neg, f'Top {TOP_N} — más comentarios NEGATIVOS'),
    ]:
        sub = df[df['sentimiento'] == sentimiento]
        top = sub.groupby(col_usuario).size().nlargest(TOP_N).reset_index()
        top.columns = ['usuario', 'count']

        # Añadir fecha del primer comentario si hay fecha
        if tiene_fecha:
            fechas = (
                sub.dropna(subset=['fecha_dt'])
                .groupby(col_usuario)['fecha_dt']
                .min()
                .reset_index()
            )
            fechas.columns = ['usuario', 'primer_comentario']
            top = top.merge(fechas, on='usuario', how='left')
            labels = [
                f"{row['usuario']}\n(desde {row['primer_comentario'].strftime('%b %Y') if pd.notna(row['primer_comentario']) else '??'})"
                for _, row in top.iterrows()
            ]
        else:
            labels = top['usuario'].tolist()

        bars = ax.barh(labels[::-1], top['count'].values[::-1],
                       color=colores[:len(top)], edgecolor='black')
        for bar, val in zip(bars, top['count'].values[::-1]):
            ax.text(bar.get_width() + top['count'].max() * 0.01, bar.get_y() + bar.get_height() / 2,
                    f"{val:,}", va='center', fontsize=10, fontweight='bold')
        ax.set_title(titulo, fontsize=12, fontweight='bold')
        ax.set_xlabel("Comentarios", fontsize=10)
        ax.set_xlim(0, top['count'].max() * 1.2)
        ax.grid(axis='x', linestyle='--', alpha=0.4)

    plt.tight_layout()
    save_plot(f"{file_id}_top_usuarios_groq.png")


def main():
    root = tk.Tk(); root.withdraw()
    csv_file = filedialog.askopenfilename(
        title="Selecciona el CSV de comentarios TikTok",
        filetypes=[("CSV Files", "*.csv")]
    )
    root.destroy()
    if not csv_file:
        print("Cancelado.")
        return

    file_id = os.path.splitext(os.path.basename(csv_file))[0]
    create_output_folder(file_id)
    print(f"\nProcesando: {file_id}")

    df = pd.read_csv(csv_file, low_memory=False)
    print(f"Cargados {len(df):,} comentarios.")

    if 'is_reply' in df.columns:
        n_total = len(df)
        df = df[df['is_reply'] == 0].copy()
        print(f"Filtrando directos: {len(df):,} ({len(df)/n_total*100:.1f}%) — {n_total-len(df):,} replies excluidas")

    df = analizar_sentimiento_groq(df, csv_file)
    if df is None:
        print("\nAnalisis pausado por limite gratuito de Groq. Reejecuta este menu mas tarde para continuar.")
        return

    csv_out = csv_file.replace(".csv", "_con_sentimiento_groq.csv")
    df.to_csv(csv_out, index=False, encoding='utf-8-sig')
    print(f"\n-> CSV con sentimiento guardado: {os.path.basename(csv_out)}")

    generar_grafica_sentimiento(df, file_id)
    generar_evolucion_mensual(df, file_id)
    generar_top_usuarios(df, file_id)

    print(f"\n¡Completado! Revisa '{OUTPUT_FOLDER}/'")


if __name__ == "__main__":
    main()
