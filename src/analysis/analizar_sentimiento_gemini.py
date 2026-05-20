"""
Análisis de sentimiento de comentarios TikTok usando Gemini Flash Lite.
- Filtra comentarios directos (is_reply == 0)
- Procesa en lotes de 50 comentarios por request
- Guarda CSV con columna 'sentimiento' para reutilizar sin repetir el análisis
- Genera las mismas gráficas que analitica_comentarios.py

CAMBIOS v2:
- Modelo: gemini-flash-lite-latest (alias estable, evita 404 de versiones deprecadas)
- BATCH_SIZE: 20 → 50 (menos requests, misma info)
- RETRY_DELAY: 15s → 30s base
- Sleep entre lotes: 1.5s → 2s (menos agresivo con la API)
- Backoff con jitter aleatorio para evitar thundering herd
- Fallback automático a gemini-2.5-flash si flash-lite da 503 persistente
- CHECKPOINT_INTERVAL: 10 → 5 lotes (guarda más frecuente, menos pérdida ante crash)
"""

import os
import csv as _csv
import json
import time
import random
import hashlib
from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
import tkinter as tk
from tkinter import filedialog, simpledialog
from google import genai
from google.genai import types
from dotenv import load_dotenv

# --- CONFIGURACIÓN ---
BASE_DIR        = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CONFIG_DIR      = os.path.join(BASE_DIR, "config")
OUTPUT_BASE     = os.path.join(BASE_DIR, "outputs")
OUTPUT_FOLDER   = OUTPUT_BASE
LOGO_TIKTOK     = os.path.join(BASE_DIR, "assets", "tiktok_logo.jpg")

load_dotenv(os.path.join(CONFIG_DIR, ".env"))  # carga configuración desde config/.env

import sys as _sys
_sys.path.insert(0, BASE_DIR)
from config.viz_style import PALETA, STAT_BOX, apply_estilo_periodistico

TWITTER_DPI    = 100   # 16×9 inches × 100dpi = 1600×900px
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")  # lee del .env
GEMINI_MODEL   = "gemini-flash-lite-latest"   # alias estable — no se depreca sin aviso
FALLBACK_MODEL = "gemini-2.5-flash"           # se activa si flash-lite da 503 repetidos
BATCH_SIZE     = 50   # comentarios por request (era 20)
RETRY_DELAY    = 30   # segundos base entre reintentos (era 15)
SLEEP_BETWEEN  = 2.0  # segundos entre lotes normales (era 1.5)

CHECKPOINT_INTERVAL = 5   # guardar cada N lotes (era 10)
TELEMETRY_CSV = os.path.join(BASE_DIR, "data", "llm_telemetry.csv")
_TELEM_CAMPOS = ["timestamp", "proveedor", "modelo", "n_comentarios",
                 "tokens_in", "tokens_out", "latencia_ms", "finish_reason", "parse_ok"]


def _log_telemetria(**kwargs):
    """Añade una fila al CSV acumulativo de telemetría LLM."""
    fila = {k: kwargs.get(k, "") for k in _TELEM_CAMPOS}
    existe = os.path.exists(TELEMETRY_CSV)
    with open(TELEMETRY_CSV, "a", newline="", encoding="utf-8") as f:
        w = _csv.DictWriter(f, fieldnames=_TELEM_CAMPOS)
        if not existe:
            w.writeheader()
        w.writerow(fila)

SYSTEM_PROMPT = """Eres un clasificador de sentimiento para comentarios de TikTok en español.
Clasifica cada comentario con exactamente una de estas etiquetas:
- POS: opinión positiva, apoyo, halago, humor positivo
- NEG: crítica, insulto, queja, ironía negativa
- NEU: neutro, pregunta, sin carga emocional clara

Devuelve un JSON array con un objeto por comentario, en el mismo orden:
[{{"index": 0, "label": "POS"}}, {{"index": 1, "label": "NEG"}}, ...]

Solo el JSON array, sin texto adicional."""


def detectar_columna_id(df):
    """Detecta la columna de ID estable del comentario."""
    for col in ['comment_id', 'comentario_id', 'cid', 'id']:
        if col in df.columns:
            return col
    return None


def clave_estable(row, col_id, col_texto='texto'):
    """Clave estable por comentario: usa ID si existe, MD5 del texto como fallback."""
    if col_id:
        val = row.get(col_id)
        if val is not None and str(val).strip() not in ('', 'nan', 'None'):
            return str(val).strip()
    return hashlib.md5(str(row.get(col_texto, '')).encode('utf-8', errors='replace')).hexdigest()[:16]


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
            print(f"   ⚠️  Checkpoint en formato antiguo (claves posicionales) detectado.")
            print(f"   ℹ️  Copia guardada en: {os.path.basename(backup)}")
            print(f"   🔄  Reiniciando con claves estables (ID o hash de texto).")
            return {}
    except (ValueError, TypeError):
        pass
    return ckpt_data


def create_output_folder(file_id=None):
    global OUTPUT_FOLDER
    if file_id:
        project = file_id.split('_videos')[0] if '_videos' in file_id else file_id
        OUTPUT_FOLDER = os.path.join(OUTPUT_BASE, project, "polaridad_ia")
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)


def save_plot(filename, tight=True):
    path = os.path.join(OUTPUT_FOLDER, filename)
    if tight:
        plt.savefig(path, bbox_inches='tight', dpi=TWITTER_DPI, facecolor='white')
    else:
        plt.savefig(path, dpi=TWITTER_DPI, facecolor='white')
    print(f"-> Guardado: {filename}")
    plt.close()


def clasificar_lote(client, textos, model=None):
    """Envía un lote de textos a Gemini y devuelve lista de etiquetas."""
    if model is None:
        model = GEMINI_MODEL

    numerados = "\n".join(f"{i}. {t[:300]}" for i, t in enumerate(textos))
    prompt = f"{SYSTEM_PROMPT}\n\nComentarios:\n{numerados}"

    for intento in range(5):
        t0 = time.time()
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1
                )
            )
            latencia_ms = int((time.time() - t0) * 1000)
            um = getattr(response, "usage_metadata", None)
            tok_in  = getattr(um, "prompt_token_count",     0) if um else 0
            tok_out = getattr(um, "candidates_token_count", 0) if um else 0

            datos = json.loads(response.text)
            etiquetas = ["NEU"] * len(textos)
            for item in datos:
                idx = item.get("index")
                label = str(item.get("label", "NEU")).upper()
                if idx is not None and 0 <= idx < len(textos):
                    if label not in ("POS", "NEG", "NEU"):
                        label = "NEU"
                    etiquetas[idx] = label
            _log_telemetria(timestamp=datetime.now().isoformat(), proveedor="gemini",
                            modelo=model, n_comentarios=len(textos), tokens_in=tok_in,
                            tokens_out=tok_out, latencia_ms=latencia_ms,
                            finish_reason="stop", parse_ok=True)
            return etiquetas

        except Exception as e:
            msg = str(e)

            # Errores 4xx son permanentes — no reintentar
            if any(f" {c} " in f" {msg} " or f"'{c}'" in msg for c in ["400", "401", "403", "404"]):
                print(f"\n   Error permanente (no reintentable): {e}")
                raise

            # Backoff exponencial con jitter para evitar thundering herd
            base = RETRY_DELAY * (2 ** intento)
            jitter = random.uniform(0, base * 0.2)
            espera = base + jitter
            print(f"\n   Reintento {intento+1}/5 tras error 5xx [{model}]: {e}")
            print(f"   Esperando {espera:.0f}s...")
            time.sleep(espera)

    return None  # error técnico — no contaminar distribución con NEUs falsos


def get_checkpoint_path(csv_file):
    return csv_file.replace(".csv", "_gemini_checkpoint.json")


def load_checkpoint(checkpoint_path):
    if os.path.exists(checkpoint_path):
        with open(checkpoint_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"   Checkpoint encontrado: {len(data):,} comentarios ya procesados. Continuando...")
        return data  # dict {str(index): etiqueta}
    return {}


def save_checkpoint(checkpoint_path, etiquetas_dict):
    with open(checkpoint_path, "w", encoding="utf-8") as f:
        json.dump(etiquetas_dict, f)


def analizar_sentimiento_gemini(df, csv_file):
    print("\n--- Analizando sentimiento con Gemini ---")

    api_key = GEMINI_API_KEY
    if not api_key:
        root = tk.Tk(); root.withdraw()
        api_key = simpledialog.askstring("API Key", "Introduce tu Gemini API Key:")
        root.destroy()
    if not api_key:
        print("Sin API key. Abortando.")
        return df

    client = genai.Client(api_key=api_key)
    checkpoint_path = get_checkpoint_path(csv_file)
    checkpoint = load_checkpoint(checkpoint_path)

    # Clave estable por comentario (ID o hash del texto)
    col_id = detectar_columna_id(df)
    fuente_clave = f"columna '{col_id}'" if col_id else "hash MD5 del texto"
    print(f"   Clave de checkpoint: {fuente_clave}")
    claves = [clave_estable(df.iloc[i].to_dict(), col_id, 'texto') for i in range(len(df))]

    checkpoint = _migrar_checkpoint_si_necesario(checkpoint_path, checkpoint, len(df))

    textos = df['texto'].fillna("").astype(str).tolist()
    total  = len(textos)

    model_activo = GEMINI_MODEL
    errores_503_consecutivos = 0
    lotes_desde_ultimo_save = 0

    print(f"   {total:,} comentarios en lotes de {BATCH_SIZE} usando [{model_activo}]...")

    for i in range(0, total, BATCH_SIZE):
        indices_lote = list(range(i, min(i + BATCH_SIZE, total)))
        claves_lote  = [claves[idx] for idx in indices_lote]

        # Saltar lotes ya completamente procesados
        if all(k in checkpoint for k in claves_lote):
            procesados = min(i + BATCH_SIZE, total)
            print(f"   {procesados:,} / {total:,}  ({procesados/total*100:.1f}%) [cached]", end="\r")
            continue

        lote = [textos[idx] for idx in indices_lote]

        try:
            tags = clasificar_lote(client, lote, model=model_activo)
            errores_503_consecutivos = 0  # reset al tener éxito
        except Exception as e:
            msg = str(e)
            if "503" in msg and model_activo != FALLBACK_MODEL:
                errores_503_consecutivos += 1
                if errores_503_consecutivos >= 2:
                    print(f"\n   ⚠ Demasiados 503 en [{model_activo}]. Cambiando a [{FALLBACK_MODEL}]...")
                    model_activo = FALLBACK_MODEL
                    errores_503_consecutivos = 0
            tags = None  # error técnico — no guardar NEU falsos

        if tags is not None:
            for k, tag in zip(claves_lote, tags):
                checkpoint[k] = tag   # clave estable, no posición

        lotes_desde_ultimo_save += 1
        if lotes_desde_ultimo_save >= CHECKPOINT_INTERVAL:
            save_checkpoint(checkpoint_path, checkpoint)
            lotes_desde_ultimo_save = 0

        procesados = min(i + BATCH_SIZE, total)
        estado = "⚠ omitido" if tags is None else f"[{model_activo}]"
        print(f"   {procesados:,} / {total:,}  ({procesados/total*100:.1f}%) {estado}", end="\r")
        time.sleep(SLEEP_BETWEEN)

    # Guardar checkpoint final
    save_checkpoint(checkpoint_path, checkpoint)

    # Aplicar etiquetas — None para errores de API (no NEU falso)
    label_map = {"POS": "positivo", "NEG": "negativo", "NEU": "neutro"}
    df['sentimiento'] = [label_map.get(checkpoint.get(k), None) for k in claves]

    # Estadísticas separando errores de API del NEU real
    clasificados = df['sentimiento'].notna().sum()
    sin_clasificar = total - clasificados
    counts = df['sentimiento'].value_counts(dropna=True)
    print(f"\n-> Distribución ({clasificados:,} clasificados / {total:,} total):")
    for sent, n in counts.items():
        print(f"   {sent}: {n:,} ({n/total*100:.1f}%)")
    if sin_clasificar > 0:
        print(f"   ⚠️  Sin clasificar: {sin_clasificar:,} ({sin_clasificar/total*100:.1f}%)"
              f" — errores de API, vuelve a ejecutar para reintentar")

    return df


def _get_account(file_id):
    name = file_id.split('_videos')[0] if '_videos' in file_id else file_id
    if name.startswith('user_'):
        return f"@{name[5:]}"
    return name

_STAT_BOX = STAT_BOX   # alias — definido en config.viz_style

def _add_watermark(ax):
    if not os.path.exists(LOGO_TIKTOK):
        return
    try:
        img = mpimg.imread(LOGO_TIKTOK)
        imagebox = OffsetImage(img, zoom=0.05, alpha=0.2)
        ab = AnnotationBbox(imagebox, (0.985, 0.025),
                            xycoords='axes fraction', frameon=False,
                            box_alignment=(1.0, 0.0))
        ax.add_artist(ab)
    except Exception:
        pass


_apply_estilo_periodistico = apply_estilo_periodistico  # importada de config.viz_style


def generar_grafica_sentimiento(df, file_id):
    counts  = df['sentimiento'].value_counts().reindex(["positivo", "neutro", "negativo"], fill_value=0)
    colores = ["#A93226", "#95a5a6", "#4A4A4A"]
    total   = counts.sum()

    sentimiento_pico = counts.idxmax()
    pct_pico = counts.max() / total * 100

    fig, ax = plt.subplots(figsize=(16, 9))
    fig.patch.set_facecolor('#FFFFFF')
    bars = ax.bar(counts.index, counts.values, color=colores, edgecolor='none', width=0.5)
    for bar, val in zip(bars, counts.values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + counts.max() * 0.01,
                f"{val:,}\n({val/total*100:.1f}%)", ha="center", va="bottom", fontsize=11, fontweight="bold",
                color='#222222')
    ax.set_title(f"distribución de sentimiento (Gemini) en comentarios de {_get_account(file_id)}",
                 fontsize=14, color='#444444', pad=12)
    ax.text(0.02, 0.97, f"el {pct_pico:.1f}% de los comentarios son {sentimiento_pico}s",
            transform=ax.transAxes, fontsize=12, fontweight='bold',
            va='top', ha='left', color='#222222', bbox=_STAT_BOX)
    ax.set_ylabel("Número de comentarios", fontsize=11)
    ax.set_ylim(0, counts.max() * 1.18)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{int(v):,}"))
    _apply_estilo_periodistico(ax)
    _add_watermark(ax)
    plt.tight_layout()
    save_plot(f"{file_id}_sentimiento_distribucion_gemini.png")


def generar_evolucion_acumulada(df, file_id):
    if 'fecha' not in df.columns:
        print("-> Sin columna 'fecha'. Omitiendo evolución.")
        return

    df = df.copy()
    df['fecha_dt'] = pd.to_datetime(df['fecha'], errors='coerce')
    df.dropna(subset=['fecha_dt'], inplace=True)
    df['año_mes'] = df['fecha_dt'].dt.to_period('M')

    todos_meses = df['año_mes'].sort_values().unique()
    pos = df[df['sentimiento'] == 'positivo'].groupby('año_mes').size().reindex(todos_meses, fill_value=0).cumsum()
    neg = df[df['sentimiento'] == 'negativo'].groupby('año_mes').size().reindex(todos_meses, fill_value=0).cumsum()
    etiquetas = [str(m) for m in todos_meses]
    x = list(range(len(etiquetas)))

    fig, ax = plt.subplots(figsize=(16, 9))
    fig.patch.set_facecolor('#FFFFFF')
    ax.plot(x, pos.values, color='#A93226', linewidth=2.5, marker='o', markersize=4)
    ax.plot(x, neg.values, color='#4A4A4A', linewidth=2.5, marker='o', markersize=4)

    bbox_style = dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.9,
                      edgecolor='#CCCCCC', linewidth=0.5)
    ax.annotate(f"Positivos\n{pos.values[-1]:,}", xy=(x[-1], pos.values[-1]),
                xytext=(12, 0), textcoords='offset points', color='#A93226',
                fontweight='bold', fontsize=10, va='center', bbox=bbox_style)
    ax.annotate(f"Negativos\n{neg.values[-1]:,}", xy=(x[-1], neg.values[-1]),
                xytext=(12, 0), textcoords='offset points', color='#4A4A4A',
                fontweight='bold', fontsize=10, va='center', bbox=bbox_style)

    ax.set_xticks(x)
    ax.set_xticklabels(etiquetas, rotation=45, ha='right', fontsize=9)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{int(v):,}"))
    ratio = pos.values[-1] / max(neg.values[-1], 1)
    ax.set_title(f"evolución acumulada de sentimiento (Gemini) en comentarios de {_get_account(file_id)}",
                 fontsize=14, color='#444444', pad=12)
    ax.text(0.02, 0.97, f"los comentarios positivos superan a los negativos en {ratio:.1f}x",
            transform=ax.transAxes, fontsize=12, fontweight='bold',
            va='top', ha='left', color='#222222', bbox=_STAT_BOX)
    ax.set_ylabel("Comentarios acumulados", fontsize=11)
    _apply_estilo_periodistico(ax)
    _add_watermark(ax)
    plt.tight_layout()
    save_plot(f"{file_id}_sentimiento_acumulado_gemini.png")


def generar_top_comentarios_sentimiento(df, file_id):
    """Top 5 comentarios más repetidos positivos y negativos (sin emojis puros)."""
    import re

    def tiene_texto(t):
        return len(re.findall(r'[a-záéíóúüñA-ZÁÉÍÓÚÜÑ]', str(t))) >= 3

    colores = {'positivo': '#A93226', 'negativo': '#4A4A4A'}
    fig, axes = plt.subplots(1, 2, figsize=(16, 9))
    fig.patch.set_facecolor('#FFFFFF')

    for ax, sentimiento in zip(axes, ['positivo', 'negativo']):
        sub = df[(df['sentimiento'] == sentimiento) & df['texto'].notna()].copy()
        sub['texto'] = sub['texto'].astype(str).str.strip()
        sub = sub[sub['texto'].apply(tiene_texto)]
        top = sub['texto'].value_counts().head(5)

        if top.empty:
            ax.text(0.5, 0.5, 'Sin datos', ha='center', va='center', transform=ax.transAxes)
            ax.set_title(f"top comentarios {sentimiento}s", fontsize=13, color='#444444')
            continue

        labels = [t[:45] + '…' if len(t) > 45 else t for t in top.index]
        color = colores[sentimiento]

        bars = ax.barh(range(len(top)), top.values, color=color, edgecolor='none', height=0.55)
        ax.set_yticks(range(len(top)))
        ax.set_yticklabels(labels, fontsize=10)
        ax.invert_yaxis()

        for bar, val in zip(bars, top.values):
            ax.text(bar.get_width() + top.values.max() * 0.01, bar.get_y() + bar.get_height() / 2,
                    f"{val:,}", va='center', ha='left', fontsize=10, fontweight='bold', color='#222222')

        ax.set_xlim(0, top.values.max() * 1.2)
        ax.set_title(f"top 5 comentarios {sentimiento}s", fontsize=13, color='#444444', pad=10)
        ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{int(v):,}"))
        ax.set_facecolor('#FFFFFF')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_visible(False)
        ax.spines['bottom'].set_color('#CCCCCC')
        ax.grid(axis='x', color='#EBEBEB', linewidth=0.5)
        ax.set_axisbelow(True)
        ax.tick_params(colors='#555555', labelsize=9)

    fig.suptitle(f"comentarios más repetidos por sentimiento en {_get_account(file_id)}",
                 fontsize=14, color='#444444', y=1.01)
    _add_watermark(axes[1])
    plt.tight_layout()
    save_plot(f"{file_id}_top_comentarios_sentimiento_gemini.png")


def generar_top_usuarios_sentimiento(df, file_id):
    """Top 5 usuarios con más comentarios positivos y negativos (is_reply=0 ya filtrado)."""
    colores = {'positivo': '#A93226', 'negativo': '#4A4A4A'}
    fig, axes = plt.subplots(1, 2, figsize=(16, 9))
    fig.patch.set_facecolor('#FFFFFF')

    for ax, sentimiento in zip(axes, ['positivo', 'negativo']):
        sub = df[df['sentimiento'] == sentimiento]
        top = sub['autor_handle'].value_counts().head(5)

        if top.empty:
            ax.text(0.5, 0.5, 'Sin datos', ha='center', va='center', transform=ax.transAxes)
            ax.set_title(f"usuarios más {sentimiento}s", fontsize=13, color='#444444')
            continue

        color = colores[sentimiento]
        bars = ax.barh(range(len(top)), top.values, color=color, edgecolor='none', height=0.55)
        ax.set_yticks(range(len(top)))
        ax.set_yticklabels([f"@{u}" for u in top.index], fontsize=11)
        ax.invert_yaxis()

        for bar, val in zip(bars, top.values):
            ax.text(bar.get_width() + top.values.max() * 0.01, bar.get_y() + bar.get_height() / 2,
                    f"{val:,}", va='center', ha='left', fontsize=10, fontweight='bold', color='#222222')

        ax.set_xlim(0, top.values.max() * 1.2)
        ax.set_title(f"top 5 usuarios con más comentarios {sentimiento}s", fontsize=13, color='#444444', pad=10)
        ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{int(v):,}"))
        ax.set_facecolor('#FFFFFF')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_visible(False)
        ax.spines['bottom'].set_color('#CCCCCC')
        ax.grid(axis='x', color='#EBEBEB', linewidth=0.5)
        ax.set_axisbelow(True)
        ax.tick_params(colors='#555555', labelsize=9)

    fig.suptitle(f"usuarios más activos por sentimiento en comentarios de {_get_account(file_id)}",
                 fontsize=14, color='#444444', y=1.01)
    _add_watermark(axes[1])
    plt.tight_layout()
    save_plot(f"{file_id}_top_usuarios_sentimiento_gemini.png")


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
    print(f"\nProcesando: {file_id}")
    create_output_folder(file_id)

    df = pd.read_csv(csv_file, low_memory=False)
    print(f"Cargados {len(df):,} comentarios.")

    if 'is_reply' in df.columns:
        n_total = len(df)
        df = df[df['is_reply'] == 0].copy()
        print(f"Filtrando directos: {len(df):,} ({len(df)/n_total*100:.1f}%) — {n_total-len(df):,} replies excluidas")

    df = analizar_sentimiento_gemini(df, csv_file)

    # Guardar CSV con sentimiento para reutilizar
    csv_out = csv_file.replace(".csv", "_con_sentimiento_gemini.csv")
    df.to_csv(csv_out, index=False, encoding='utf-8-sig')
    print(f"\n-> CSV con sentimiento guardado: {os.path.basename(csv_out)}")

    generar_grafica_sentimiento(df, file_id)
    generar_evolucion_acumulada(df, file_id)
    generar_top_comentarios_sentimiento(df, file_id)
    generar_top_usuarios_sentimiento(df, file_id)

    print(f"\n¡Completado! Revisa '{OUTPUT_FOLDER}/'")


if __name__ == "__main__":
    main()