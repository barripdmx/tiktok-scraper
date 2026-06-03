
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
from wordcloud import WordCloud, STOPWORDS
import tkinter as tk
from tkinter import filedialog, simpledialog
import os
import re
import unicodedata
import emoji
from matplotlib.colors import to_rgb
import random
from collections import Counter
from pysentimiento import create_analyzer

# --- CONFIGURACIÓN ---
# Rutas relativas a la raíz del proyecto (dos niveles arriba de src/analysis)
import sys as _sys
BASE_DIR        = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUTPUT_BASE     = os.path.join(BASE_DIR, "outputs")
OUTPUT_FOLDER   = OUTPUT_BASE
POLARIDAD_FOLDER = OUTPUT_BASE
LOGO_TIKTOK     = os.path.join(BASE_DIR, "assets", "tiktok_logo.jpg")

_sys.path.insert(0, BASE_DIR)
from config.viz_style import (
    PALETA, PALETA_CAT, COLOR_MARCA, STAT_BOX, apply_estilo_periodistico
)
from config.rutas import derivar_proyecto, dir_graficas_comentarios, dir_polaridad
PROFESSIONAL_PALETTE = PALETA_CAT  # alias para compatibilidad

# Diccionario Maestro de Colores (Traducción + Branding)
COLOR_TRANSLATOR = {
    # --- Colores Básicos ---
    'rojo': 'red', 'azul': 'blue', 'verde': 'green', 'amarillo': 'yellow', 'negro': 'black',
    'blanco': 'white', 'naranja': 'orange', 'rosa': 'pink', 'morado': 'purple', 'gris': 'gray', 'cian': 'cyan',
    # --- Colores Corporativos ---
    'vodafone': '#E60000', 'orange': '#FF7900', 'yoigo': '#831C94', 'masmovil': '#FFD700',
    'pepephone': '#E30613', 'lowi': '#000000', 'simyo': '#FF9900',
    # --- Azules ---
    'movistar': '#00254D', 'digi': '#009BDE', 'o2': '#0019A8'
}

# --- LISTAS DE SENTIMIENTO (centralizadas en config/lexicon_sentimiento.py) ---
from config.lexicon_sentimiento import (
    PALABRAS_POSITIVAS, PALABRAS_NEGATIVAS,
    EMOJIS_POSITIVOS, EMOJIS_NEGATIVOS,
)


# --- FUNCIONES AUXILIARES ---

def create_output_folder(file_id=None):
    global OUTPUT_FOLDER, POLARIDAD_FOLDER
    if file_id:
        project = derivar_proyecto(file_id)
        OUTPUT_FOLDER    = dir_graficas_comentarios(project)
        POLARIDAD_FOLDER = dir_polaridad(project)
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    os.makedirs(POLARIDAD_FOLDER, exist_ok=True)
    print(f"Carpeta comentarios: {OUTPUT_FOLDER}")
    print(f"Carpeta polaridad:   {POLARIDAD_FOLDER}")

TWITTER_DPI = 100   # 16x9 inches × 100dpi = 1600×900px

def save_plot(filename, tight=True, folder=None):
    dest = folder if folder else OUTPUT_FOLDER
    path = os.path.join(dest, filename)
    if tight:
        plt.savefig(path, bbox_inches='tight', dpi=TWITTER_DPI, facecolor='white')
    else:
        plt.savefig(path, dpi=TWITTER_DPI, facecolor='white')
    print(f"-> Guardado: {filename}")
    plt.close()

def get_file_path():
    """Abre un diálogo para seleccionar el CSV de comentarios."""
    root = tk.Tk()
    root.withdraw()  # Oculta la ventana principal
    root.attributes('-topmost', True)  # Pone el diálogo en primer plano

    # Abre el diálogo de selección
    file_path = filedialog.askopenfilename(
        title="Selecciona el archivo CSV de COMENTARIOS de TikTok",
        filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
        initialdir=os.path.join(BASE_DIR, "data")  # Abre en la carpeta data/
    )

    root.destroy()  # Destruye la ventana después de seleccionar
    return file_path

def validate_color(color_input, default='black'):
    if not color_input: return default
    clean_input = color_input.lower().strip()
    return COLOR_TRANSLATOR.get(clean_input, clean_input)

def make_color_func(target_color):
    try:
        rgb = to_rgb(target_color)
    except ValueError:
        print(f"Advertencia: Color '{target_color}' no reconocido. Usando negro por defecto.")
        return lambda *args, **kwargs: "black"
    
    def color_func(word, font_size, position, orientation, random_state=None, **kwargs):
        r, g, b = rgb
        factor = random_state.uniform(0.6, 1.0) if random_state else 0.8
        return (int(r * factor * 255), int(g * factor * 255), int(b * factor * 255))
    return color_func

def clean_text(text):
    if not isinstance(text, str): return ""
    text = re.sub(r'http\S+', '', text)
    text = emoji.replace_emoji(text, replace='')
    text = text.lower()
    text = unicodedata.normalize('NFD', text)
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    return text

def extract_emojis(text):
    if not isinstance(text, str): return ""
    return ''.join(c for c in text if c in emoji.EMOJI_DATA)

# --- FUNCIONES DE ANÁLISIS ---

def generar_ranking_palabras(df, file_id, bar_color):
    """Top-20 palabras más frecuentes como ranking horizontal ordenado.
    Más preciso que la nube: escala lineal, comparación directa entre palabras.
    """
    print("\n--- 1a. Generando Ranking de Palabras (Top 20) ---")

    sw = set(STOPWORDS)
    sw.update([
        'de', 'la', 'que', 'el', 'en', 'y', 'a', 'los', 'del', 'se', 'las', 'por',
        'un', 'para', 'con', 'no', 'una', 'su', 'al', 'lo', 'como', 'más', 'pero',
        'es', 'son', 'hay', 'me', 'le', 'te', 'si', 'ya', 'también', 'bien', 'solo',
        'cuando', 'todo', 'mi', 'ti', 'nos', 'les', 'esto', 'esta', 'ese', 'esa',
    ])

    all_text = " ".join(df['texto'].dropna().astype(str))
    all_text = clean_text(all_text)
    words = [w for w in all_text.split() if len(w) > 2 and w not in sw]
    freq = Counter(words).most_common(20)

    if not freq:
        print("   -> Sin palabras suficientes para el ranking.")
        return

    palabras = [w for w, _ in reversed(freq)]
    conteos  = [c for _, c in reversed(freq)]

    fig, ax = plt.subplots(figsize=(16, 9))
    fig.patch.set_facecolor('#FFFFFF')
    bars = ax.barh(range(len(palabras)), conteos, color=bar_color, edgecolor='none', alpha=0.85)
    ax.set_yticks(range(len(palabras)))
    ax.set_yticklabels(palabras, fontsize=11)
    for bar, val in zip(bars, conteos):
        ax.text(bar.get_width() + max(conteos) * 0.005,
                bar.get_y() + bar.get_height() / 2,
                f'{val:,}', va='center', fontsize=9, color='#222222')
    ax.set_title(f"top 20 palabras en comentarios de {_get_account(file_id)}",
                 fontsize=14, color='#444444', pad=12)
    ax.set_xlabel("Frecuencia de aparición", fontsize=11)
    ax.set_xlim(0, max(conteos) * 1.18)
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{int(v):,}"))
    _apply_estilo_periodistico(ax)
    ax.grid(axis='x', color='#EBEBEB', linewidth=0.5)
    ax.grid(axis='y', visible=False)
    ax.spines['left'].set_visible(False)
    _add_watermark(ax)
    plt.tight_layout()
    save_plot(f"{file_id}_ranking_palabras.png")


def generar_nubes(df, file_id, final_color_text, final_color_emoji):
    """Genera nube de palabras y de emoticonos."""
    print("\n--- 1. Generando Nubes de Contenido General ---")

    all_text = " ".join(df['texto'].dropna().astype(str))
    if all_text.strip():
        sw = set(STOPWORDS)
        sw.update(['de', 'la', 'que', 'el', 'en', 'y', 'a', 'los', 'del', 'se', 'las', 'por', 'un', 'para', 'con', 'no', 'una', 'su', 'al', 'lo', 'como', 'más', 'pero', 'es', 'son'])
        wc_text = WordCloud(stopwords=sw, background_color='white', color_func=make_color_func(final_color_text),
                            width=1600, height=900, max_words=200, collocations=False).generate(clean_text(all_text))
        fig, ax = plt.subplots(figsize=(16, 9))
        fig.patch.set_facecolor('#FFFFFF')
        ax.imshow(wc_text, interpolation='bilinear')
        ax.axis('off')
        ax.set_title(f"palabras más frecuentes en comentarios de {_get_account(file_id)}",
                     fontsize=14, color='#444444', pad=12)
        _add_watermark(ax)
        save_plot(f"{file_id}_nube_palabras_general.png", tight=False)
    else:
        print("-> No hay texto en comentarios para generar nube de palabras.")

    emojis_found = extract_emojis(all_text)
    if emojis_found:
        try:
            font = "C:/Windows/Fonts/seguiemj.ttf"
            wc_emoji = WordCloud(background_color='white', color_func=make_color_func(final_color_emoji),
                                 font_path=font, width=1600, height=900, regexp=r"\S").generate(" ".join(emojis_found))
        except OSError:
            wc_emoji = WordCloud(background_color='white', color_func=make_color_func(final_color_emoji),
                                 width=1600, height=900, regexp=r"\S").generate(" ".join(emojis_found))
        fig, ax = plt.subplots(figsize=(16, 9))
        fig.patch.set_facecolor('#FFFFFF')
        ax.imshow(wc_emoji, interpolation='bilinear')
        ax.axis('off')
        ax.set_title(f"emoticonos más frecuentes en comentarios de {_get_account(file_id)}",
                     fontsize=14, color='#444444', pad=12)
        _add_watermark(ax)
        save_plot(f"{file_id}_nube_emoticonos_general.png", tight=False)
    else:
        print("-> No se encontraron emoticonos.")


def generar_analisis_comunidad(df, file_id, bar_color):
    """Genera gráficos sobre los usuarios que comentan."""
    print("\n--- 2. Generando Análisis de Comunidad ---")

    df = df.copy()
    df['_autor_handle_norm'] = (
        df['autor_handle']
        .fillna('')
        .astype(str)
        .str.strip()
        .str.lstrip('@')
    )
    df = df[
        df['_autor_handle_norm'].ne('')
        & df['_autor_handle_norm'].str.lower().ne('nan')
        & df['_autor_handle_norm'].str.lower().ne('none')
    ].copy()

    if df.empty:
        print("-> No hay cuentas válidas en 'autor_handle'.")
        return

    comentarios_por_cuenta = df['_autor_handle_norm'].value_counts()
    total_cuentas = len(comentarios_por_cuenta)
    total_comentarios = int(comentarios_por_cuenta.sum())

    top_commenters = comentarios_por_cuenta.nlargest(20).sort_values()
    if not top_commenters.empty:
        fig, ax = plt.subplots(figsize=(16, 9))
        fig.patch.set_facecolor('#FFFFFF')
        ax.barh(range(len(top_commenters)), top_commenters.values, color=bar_color, edgecolor='none', alpha=0.85)
        ax.set_yticks(range(len(top_commenters)))
        ax.set_yticklabels(top_commenters.index, fontsize=9)
        for i, v in enumerate(top_commenters.values):
            ax.text(v + top_commenters.max() * 0.005, i, f' {v:,}', va='center', fontsize=9, color='#222222')
        ax.set_title(f"usuarios más activos en comentarios de {_get_account(file_id)}",
                     fontsize=14, color='#444444', pad=12)
        ax.text(0.98, 0.02, f"top: @{top_commenters.index[-1]} con {top_commenters.values[-1]:,} comentarios",
                transform=ax.transAxes, fontsize=10, fontweight='bold',
                va='bottom', ha='right', color='#222222', bbox=_STAT_BOX)
        ax.set_xlabel("Número de comentarios", fontsize=11)
        ax.set_xlim(0, top_commenters.max() * 1.15)
        _apply_estilo_periodistico(ax)
        ax.grid(axis='x', color='#EBEBEB', linewidth=0.5)
        ax.grid(axis='y', visible=False)
        _add_watermark(ax)
        plt.tight_layout()
        save_plot(f"{file_id}_top_comentaristas_activos.png")

    likes_per_user = df.groupby('_autor_handle_norm')['likes'].sum().nlargest(20).sort_values()
    if not likes_per_user.empty:
        fig, ax = plt.subplots(figsize=(16, 9))
        fig.patch.set_facecolor('#FFFFFF')
        ax.barh(range(len(likes_per_user)), likes_per_user.values, color=bar_color, edgecolor='none', alpha=0.85)
        ax.set_yticks(range(len(likes_per_user)))
        ax.set_yticklabels(likes_per_user.index, fontsize=9)
        for i, v in enumerate(likes_per_user.values):
            ax.text(v + likes_per_user.max() * 0.005, i, f' {v:,}', va='center', fontsize=9, color='#222222')
        ax.set_title(f"usuarios con más likes en comentarios de {_get_account(file_id)}",
                     fontsize=14, color='#444444', pad=12)
        ax.text(0.98, 0.02, f"top: @{likes_per_user.index[-1]} con {likes_per_user.values[-1]:,} likes",
                transform=ax.transAxes, fontsize=10, fontweight='bold',
                va='bottom', ha='right', color='#222222', bbox=_STAT_BOX)
        ax.set_xlabel("Suma de likes", fontsize=11)
        ax.set_xlim(0, likes_per_user.max() * 1.15)
        _apply_estilo_periodistico(ax)
        ax.grid(axis='x', color='#EBEBEB', linewidth=0.5)
        ax.grid(axis='y', visible=False)
        _add_watermark(ax)
        plt.tight_layout()
        save_plot(f"{file_id}_top_comentaristas_likes.png")

    top_comments = df.sort_values('likes', ascending=False).head(10)
    if not top_comments.empty:
        txt_filename = f"{file_id}_mejores_comentarios.txt"
        with open(os.path.join(OUTPUT_FOLDER, txt_filename), "w", encoding="utf-8") as f:
            f.write(f"--- REPORTE DE MEJORES COMENTARIOS: {file_id} ---\n\n")
            for i, row in top_comments.iterrows():
                f.write(f"#{i+1} - {row['likes']:,} LIKES por @{row['_autor_handle_norm']}\n")
                f.write(f"   Comentario: \"{row['texto']}\"\n")
                f.write(f"   En Video: {row['video_url']}\n\n")
        print(f"-> Reporte de mejores comentarios generado: {txt_filename}")

    # Distribución de comentarios por cuenta (tramos)
    tramos = [
        ("1", comentarios_por_cuenta == 1),
        ("2", comentarios_por_cuenta == 2),
        ("3-5", comentarios_por_cuenta.between(3, 5)),
        ("6-10", comentarios_por_cuenta.between(6, 10)),
        ("11-20", comentarios_por_cuenta.between(11, 20)),
        ("21-50", comentarios_por_cuenta.between(21, 50)),
        ("51+", comentarios_por_cuenta >= 51),
    ]

    filas_dist = []
    for etiqueta, mascara in tramos:
        cuentas_tramo = comentarios_por_cuenta[mascara]
        filas_dist.append({
            "tramo_comentarios": etiqueta,
            "cuentas": int(len(cuentas_tramo)),
            "pct_cuentas": (len(cuentas_tramo) / total_cuentas * 100) if total_cuentas else 0,
            "comentarios": int(cuentas_tramo.sum()),
            "pct_comentarios": (cuentas_tramo.sum() / total_comentarios * 100) if total_comentarios else 0,
        })

    dist_df = pd.DataFrame(filas_dist)
    dist_csv = os.path.join(OUTPUT_FOLDER, f"{file_id}_distribucion_cuentas.csv")
    dist_df.to_csv(dist_csv, index=False, encoding='utf-8-sig')
    print(f"-> Distribución por cuentas guardada: {os.path.basename(dist_csv)}")

    fig, ax = plt.subplots(figsize=(16, 9))
    fig.patch.set_facecolor('#FFFFFF')
    bars = ax.bar(
        dist_df['tramo_comentarios'],
        dist_df['cuentas'],
        color=bar_color,
        edgecolor='none',
        alpha=0.88,
        width=0.58,
    )

    for bar, cuentas, pct_cuentas, pct_comments in zip(
        bars, dist_df['cuentas'], dist_df['pct_cuentas'], dist_df['pct_comentarios']
    ):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + max(dist_df['cuentas'].max() * 0.012, 1),
            f"{cuentas:,}\n({pct_cuentas:.1f}% cuentas)\n{pct_comments:.1f}% comentarios",
            ha='center',
            va='bottom',
            fontsize=9,
            fontweight='bold',
            color='#222222'
        )

    pct_una_vez = dist_df.loc[dist_df['tramo_comentarios'] == '1', 'pct_cuentas'].iloc[0]
    ax.set_title(f"distribución de cuentas por número de comentarios en {_get_account(file_id)}",
                 fontsize=14, color='#444444', pad=12)
    ax.text(
        0.02, 0.97,
        f"el {pct_una_vez:.0f}% de las cuentas comenta solo una vez",
        transform=ax.transAxes, fontsize=12, fontweight='bold',
        va='top', ha='left', color='#222222', bbox=_STAT_BOX
    )
    ax.set_xlabel("Comentarios por cuenta", fontsize=11)
    ax.set_ylabel("Número de cuentas", fontsize=11)
    ax.set_ylim(0, dist_df['cuentas'].max() * 1.22 if not dist_df.empty else 1)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{int(v):,}"))
    _apply_estilo_periodistico(ax)
    _add_watermark(ax)
    plt.tight_layout()
    save_plot(f"{file_id}_distribucion_cuentas_comentarios.png")

    # Curva de concentración (Pareto/Lorenz simplificada)
    comentarios_ordenados = comentarios_por_cuenta.sort_values(ascending=False).reset_index(drop=True)
    x_pct = [i / total_cuentas * 100 for i in range(1, total_cuentas + 1)]
    y_pct = (comentarios_ordenados.cumsum() / total_comentarios * 100).tolist()

    top_1_n = max(1, int(total_cuentas * 0.01))
    top_10_n = max(1, int(total_cuentas * 0.10))
    top_1_share = comentarios_ordenados.iloc[:top_1_n].sum() / total_comentarios * 100
    top_10_share = comentarios_ordenados.iloc[:top_10_n].sum() / total_comentarios * 100

    fig, ax = plt.subplots(figsize=(16, 9))
    fig.patch.set_facecolor('#FFFFFF')
    ax.plot(x_pct, y_pct, color=bar_color, linewidth=2.8, zorder=3)

    ax.plot([0, 100], [0, 100], color='#BBBBBB', linewidth=1.2, linestyle='--', zorder=1)

    ax.scatter([1, 10], [top_1_share, top_10_share], color='#222222', s=35, zorder=4)
    ax.annotate(f"Top 1% -> {top_1_share:.1f}%",
                xy=(1, top_1_share), xytext=(10, 8),
                textcoords='offset points', fontsize=9, fontweight='bold',
                color='#222222', bbox=dict(boxstyle='round,pad=0.25', facecolor='white', edgecolor='#CCCCCC', alpha=0.9))
    ax.annotate(f"Top 10% -> {top_10_share:.1f}%",
                xy=(10, top_10_share), xytext=(10, -18),
                textcoords='offset points', fontsize=9, fontweight='bold',
                color='#222222', bbox=dict(boxstyle='round,pad=0.25', facecolor='white', edgecolor='#CCCCCC', alpha=0.9))

    ax.set_title(f"concentración de comentarios por cuentas en {_get_account(file_id)}",
                 fontsize=14, color='#444444', pad=12)
    ax.text(
        0.02, 0.97,
        f"el 10% de las cuentas concentra el {top_10_share:.0f}% de los comentarios",
        transform=ax.transAxes, fontsize=12, fontweight='bold',
        va='top', ha='left', color='#222222', bbox=_STAT_BOX
    )
    ax.set_xlabel("% acumulado de cuentas", fontsize=11)
    ax.set_ylabel("% acumulado de comentarios", fontsize=11)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{int(v)}%"))
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{int(v)}%"))
    _apply_estilo_periodistico(ax)
    _add_watermark(ax)
    plt.tight_layout()
    save_plot(f"{file_id}_concentracion_comentarios_cuentas.png")


def generar_analisis_temporal(df, file_id, bar_color):
    """Genera gráficos de actividad a lo largo del tiempo."""
    if 'fecha' not in df.columns:
        return
    print("\n--- 3. Generando Análisis Temporal ---")
    try:
        df = df.copy()
        df['fecha_dt'] = pd.to_datetime(df['fecha'], errors='coerce')
        df.dropna(subset=['fecha_dt'], inplace=True)
        if df.empty:
            print("-> No se pudieron parsear las fechas. Omitiendo análisis temporal.")
            return
        df = df.sort_values('fecha_dt')

        # Comentarios por mes
        df['año_mes'] = df['fecha_dt'].dt.to_period('M')
        pub_por_mes = df.groupby('año_mes').size()
        mes_pico = pub_por_mes.idxmax()

        fig, ax = plt.subplots(figsize=(16, 9))
        fig.patch.set_facecolor('#FFFFFF')
        x = range(len(pub_por_mes))
        colores = [bar_color if i == pub_por_mes.argmax() else bar_color + '99' for i in range(len(pub_por_mes))]
        ax.bar(x, pub_por_mes.values, color=colores, edgecolor='none', alpha=0.85)
        for i, v in enumerate(pub_por_mes.values):
            ax.text(i, v + pub_por_mes.max() * 0.01, f'{v:,}', ha='center', va='bottom', fontsize=8, color='#222222')
        ax.set_title(f"comentarios por mes de {_get_account(file_id)}",
                     fontsize=14, color='#444444', pad=12)
        ax.text(0.02, 0.97, f"mes más activo: {mes_pico} con {pub_por_mes.max():,} comentarios",
                transform=ax.transAxes, fontsize=12, fontweight='bold',
                va='top', ha='left', color='#222222', bbox=_STAT_BOX)
        ax.set_ylabel("Número de comentarios", fontsize=11)
        ax.set_xticks(list(x))
        ax.set_xticklabels([str(m) for m in pub_por_mes.index], rotation=45, ha='right', fontsize=8)
        ax.set_ylim(0, pub_por_mes.max() * 1.15)
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{int(v):,}"))
        _apply_estilo_periodistico(ax)
        _add_watermark(ax)
        plt.tight_layout()
        save_plot(f"{file_id}_comentarios_por_mes.png")

        # Heatmap
        dias_semana = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
        df['dia_semana'] = df['fecha_dt'].dt.dayofweek
        df['hora'] = df['fecha_dt'].dt.hour
        heatmap_data = df.groupby(['dia_semana', 'hora']).size().unstack(fill_value=0).reindex(
            index=range(7), columns=range(24), fill_value=0)
        fig, ax = plt.subplots(figsize=(16, 9))
        fig.patch.set_facecolor('#FFFFFF')
        im = ax.imshow(heatmap_data.values, cmap='Reds', aspect='auto')
        plt.colorbar(im, ax=ax, label='Comentarios', shrink=0.8)
        ax.set_title(f"mapa de calor de actividad de comentarios de {_get_account(file_id)}",
                     fontsize=14, color='#444444', pad=12)
        ax.set_xlabel("Hora del día", fontsize=11)
        ax.set_ylabel("Día de la semana", fontsize=11)
        ax.set_xticks(range(24))
        ax.set_xticklabels([f"{h:02d}" for h in range(24)], fontsize=8)
        ax.set_yticks(range(7))
        ax.set_yticklabels(dias_semana, fontsize=9)
        ax.tick_params(colors='#555555')
        ax.spines[:].set_visible(False)
        _add_watermark(ax)
        plt.tight_layout()
        save_plot(f"{file_id}_heatmap_actividad_comentarios.png", tight=False)

    except Exception as e:
        print(f"-> Error generando gráficas temporales: {e}")

def analizar_sentimiento_ia(df):
    """Clasifica el sentimiento con RoBERTa (pysentimiento) entrenado en español."""
    print("\n--- 4. Analizando Sentimiento con IA (RoBERTa en español) ---")
    print("   Cargando modelo... (solo la primera vez tarda más)")

    analyzer = create_analyzer(task="sentiment", lang="es")

    textos = df['texto'].fillna("").astype(str).tolist()
    total = len(textos)
    print(f"   Procesando {total:,} comentarios directos en lotes...")

    BATCH = 64
    etiquetas = []
    for i in range(0, total, BATCH):
        lote = textos[i:i + BATCH]
        resultados = analyzer.predict(lote)
        etiquetas.extend(r.output for r in resultados)
        if (i // BATCH) % 20 == 0:
            print(f"   {min(i + BATCH, total):,} / {total:,}", end="\r")

    label_map = {"POS": "positivo", "NEG": "negativo", "NEU": "neutro"}
    df['sentimiento'] = [label_map.get(e, "neutro") for e in etiquetas]

    counts = df['sentimiento'].value_counts()
    print("\n-> Distribución de sentimiento:")
    for sent, n in counts.items():
        print(f"   {sent}: {n:,} ({n/total*100:.1f}%)")

    return df


# apply_estilo_periodistico importada desde config.viz_style (ver arriba)
_apply_estilo_periodistico = apply_estilo_periodistico  # alias interno


def _get_account(file_id):
    name = file_id.split('_videos')[0] if '_videos' in file_id else file_id
    if name.startswith('user_'):
        return f"@{name[5:]}"
    return name

_STAT_BOX = STAT_BOX  # alias — definido en config.viz_style

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


def generar_grafica_sentimiento(df, file_id, bar_color):
    """Gráfica de barras con distribución de sentimiento — estilo periodístico."""
    print("\n--- 5. Generando gráfica de distribución de sentimiento ---")

    counts = df['sentimiento'].value_counts().reindex(["positivo", "neutro", "negativo"], fill_value=0)
    colores = ["#A93226", "#95a5a6", "#4A4A4A"]
    total = counts.sum()

    # Título declarativo con el dato más relevante
    dom = counts.idxmax()
    dom_pct = counts[dom] / total * 100
    titulo = f"EL {dom_pct:.0f}% DE LOS COMENTARIOS SON {dom.upper()}"

    fig, ax = plt.subplots(figsize=(16, 9))
    fig.patch.set_facecolor('#FFFFFF')
    bars = ax.bar(counts.index, counts.values, color=colores, edgecolor='none', width=0.5)

    for bar, val in zip(bars, counts.values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + total * 0.008,
                f"{val:,}\n({val/total*100:.1f}%)",
                ha="center", va="bottom", fontsize=11, fontweight="bold", color='#222222')

    ax.set_title(f"distribución de sentimiento en comentarios de {_get_account(file_id)}",
                 fontsize=14, color='#444444', pad=12)
    ax.text(0.02, 0.97, titulo.lower(),
            transform=ax.transAxes, fontsize=12, fontweight='bold',
            va='top', ha='left', color='#222222', bbox=_STAT_BOX)
    ax.set_ylabel("Número de comentarios", fontsize=11, color='#222222')
    ax.set_ylim(0, counts.max() * 1.22)
    _apply_estilo_periodistico(ax)
    _add_watermark(ax)
    plt.tight_layout()
    save_plot(f"{file_id}_sentimiento_distribucion.png", folder=POLARIDAD_FOLDER)


def generar_top_emojis(df, file_id):
    """Barras horizontales con los emojis más frecuentes — estilo periodístico."""
    print("\n--- 6. Generando top emojis por sentimiento ---")

    def top_emojis_df(subset, n=20):
        todos = "".join(subset['texto'].dropna().astype(str))
        conteo = Counter(c for c in todos if c in emoji.EMOJI_DATA)
        return pd.Series(conteo).nlargest(n)

    font_emoji = "C:/Windows/Fonts/seguiemj.ttf"

    for sentimiento, color, label in [
        ("positivo", "#A93226", "POSITIVOS"),
        ("negativo", "#4A4A4A", "NEGATIVOS"),
    ]:
        subset = df[df['sentimiento'] == sentimiento]
        if subset.empty:
            continue
        top = top_emojis_df(subset)
        if top.empty:
            continue

        top_s = top.sort_values()
        fig, ax = plt.subplots(figsize=(16, 9))
        fig.patch.set_facecolor('#FFFFFF')

        bars = ax.barh(range(len(top_s)), top_s.values, color=color, edgecolor='none', alpha=0.85)

        # Etiquetas de emoji con fuente emoji si disponible
        for i, (val, lbl) in enumerate(zip(top_s.values, top_s.index)):
            try:
                ax.text(-top_s.values.max() * 0.01, i, lbl,
                        va='center', ha='right', fontsize=14,
                        fontproperties=plt.matplotlib.font_manager.FontProperties(fname=font_emoji))
            except Exception:
                ax.text(-top_s.values.max() * 0.01, i, lbl, va='center', ha='right', fontsize=12)
            ax.text(val + top_s.values.max() * 0.01, i, f"{val:,}",
                    va='center', ha='left', fontsize=9, color='#555555')

        ax.set_yticks([])
        ax.set_xlabel("Frecuencia", fontsize=11, color='#222222')
        ax.set_title(f"emojis más usados en comentarios {label.lower()} de {_get_account(file_id)}",
                     fontsize=14, color='#444444', pad=12)
        ax.set_xlim(0, top_s.values.max() * 1.15)

        # Grid vertical sutil
        ax.set_facecolor('#FFFFFF')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_visible(False)
        ax.spines['bottom'].set_color('#CCCCCC')
        ax.spines['bottom'].set_linewidth(0.8)
        ax.grid(axis='x', color='#EBEBEB', linewidth=0.5, linestyle='-')
        ax.set_axisbelow(True)
        ax.tick_params(colors='#555555', labelsize=9)

        _add_watermark(ax)
        plt.tight_layout()
        save_plot(f"{file_id}_top_emojis_{sentimiento}.png", folder=POLARIDAD_FOLDER)


def exportar_cuentas_por_sentimiento(df, file_id):
    """Exporta cuentas únicas a CSVs separados por sentimiento.

    Una misma cuenta puede aparecer en varios CSVs si ha publicado comentarios
    de distintos sentimientos.
    """
    print("\n--- 7. Exportando cuentas por sentimiento ---")

    if 'sentimiento' not in df.columns or 'autor_handle' not in df.columns:
        print("-> Faltan columnas 'sentimiento' o 'autor_handle'. Omitiendo exportación.")
        return

    work = df.copy()
    work['autor_handle_norm'] = (
        work['autor_handle']
        .fillna('')
        .astype(str)
        .str.strip()
        .str.lstrip('@')
    )
    if 'autor_nombre' in work.columns:
        work['autor_nombre_clean'] = work['autor_nombre'].fillna('').astype(str).str.strip()
    else:
        work['autor_nombre_clean'] = ''
    work = work[
        work['autor_handle_norm'].ne('')
        & work['autor_handle_norm'].str.lower().ne('nan')
        & work['autor_handle_norm'].str.lower().ne('none')
    ].copy()

    if work.empty:
        print("-> No hay cuentas válidas para exportar.")
        return

    if 'fecha' in work.columns:
        work['fecha_dt'] = pd.to_datetime(work['fecha'], errors='coerce')
    else:
        work['fecha_dt'] = pd.NaT

    totales_cuenta = (
        work.groupby('autor_handle_norm')
        .agg(
            comentarios_totales_cuenta=('autor_handle_norm', 'size'),
            likes_totales_cuenta=('likes', 'sum'),
        )
        .reset_index()
    )

    def _nombre_representativo(series):
        vals = [v for v in series if isinstance(v, str) and v.strip()]
        if not vals:
            return ""
        return pd.Series(vals).value_counts().idxmax()

    for sentimiento in ['positivo', 'neutro', 'negativo']:
        sub = work[work['sentimiento'] == sentimiento].copy()
        if sub.empty:
            print(f"-> No hay comentarios {sentimiento}s.")
            continue

        agg = (
            sub.groupby('autor_handle_norm')
            .agg(
                autor_nombre=('autor_nombre_clean', _nombre_representativo),
                comentarios_sentimiento=('autor_handle_norm', 'size'),
                likes_sentimiento=('likes', 'sum'),
                likes_media_sentimiento=('likes', 'mean'),
                primer_comentario_sentimiento=('fecha_dt', 'min'),
                ultimo_comentario_sentimiento=('fecha_dt', 'max'),
            )
            .reset_index()
        )

        agg = agg.merge(totales_cuenta, on='autor_handle_norm', how='left')
        agg['pct_sentimiento_en_cuenta'] = (
            agg['comentarios_sentimiento'] / agg['comentarios_totales_cuenta'] * 100
        ).round(2)
        agg['likes_media_sentimiento'] = agg['likes_media_sentimiento'].round(2)

        for col in ['primer_comentario_sentimiento', 'ultimo_comentario_sentimiento']:
            agg[col] = agg[col].dt.strftime('%Y-%m-%d %H:%M:%S')
            agg[col] = agg[col].fillna('')

        agg = agg.rename(columns={'autor_handle_norm': 'autor_handle'})
        agg = agg.sort_values(
            by=['comentarios_sentimiento', 'likes_sentimiento', 'autor_handle'],
            ascending=[False, False, True]
        )

        out_path = os.path.join(POLARIDAD_FOLDER, f"{file_id}_cuentas_{sentimiento}.csv")
        agg.to_csv(out_path, index=False, encoding='utf-8-sig')
        print(f"-> CSV {sentimiento}: {os.path.basename(out_path)} ({len(agg):,} cuentas)")


def exportar_cuentas_sentimiento_dominante(df, file_id):
    """Clasifica cada cuenta en un único sentimiento dominante.

    Regla:
    - Se asigna el sentimiento con más comentarios.
    - Si hay empate en el máximo, la cuenta va a `empate`.
    """
    print("\n--- 8. Exportando sentimiento dominante por cuenta ---")

    if 'sentimiento' not in df.columns or 'autor_handle' not in df.columns:
        print("-> Faltan columnas 'sentimiento' o 'autor_handle'. Omitiendo dominante.")
        return

    work = df.copy()
    work['autor_handle_norm'] = (
        work['autor_handle']
        .fillna('')
        .astype(str)
        .str.strip()
        .str.lstrip('@')
    )
    if 'autor_nombre' in work.columns:
        work['autor_nombre_clean'] = work['autor_nombre'].fillna('').astype(str).str.strip()
    else:
        work['autor_nombre_clean'] = ''

    work = work[
        work['autor_handle_norm'].ne('')
        & work['autor_handle_norm'].str.lower().ne('nan')
        & work['autor_handle_norm'].str.lower().ne('none')
    ].copy()

    if work.empty:
        print("-> No hay cuentas válidas para dominante.")
        return

    if 'fecha' in work.columns:
        work['fecha_dt'] = pd.to_datetime(work['fecha'], errors='coerce')
    else:
        work['fecha_dt'] = pd.NaT

    def _nombre_representativo(series):
        vals = [v for v in series if isinstance(v, str) and v.strip()]
        if not vals:
            return ""
        return pd.Series(vals).value_counts().idxmax()

    base = (
        work.groupby('autor_handle_norm')
        .agg(
            autor_nombre=('autor_nombre_clean', _nombre_representativo),
            comentarios_totales=('autor_handle_norm', 'size'),
            likes_totales=('likes', 'sum'),
            primer_comentario=('fecha_dt', 'min'),
            ultimo_comentario=('fecha_dt', 'max'),
        )
        .reset_index()
    )

    counts = (
        work.groupby(['autor_handle_norm', 'sentimiento'])
        .size()
        .unstack(fill_value=0)
        .reindex(columns=['positivo', 'neutro', 'negativo'], fill_value=0)
        .reset_index()
    )

    out = base.merge(counts, on='autor_handle_norm', how='left')
    out[['positivo', 'neutro', 'negativo']] = out[['positivo', 'neutro', 'negativo']].fillna(0).astype(int)

    out['pct_positivo'] = (out['positivo'] / out['comentarios_totales'] * 100).round(2)
    out['pct_neutro'] = (out['neutro'] / out['comentarios_totales'] * 100).round(2)
    out['pct_negativo'] = (out['negativo'] / out['comentarios_totales'] * 100).round(2)

    sent_cols = ['positivo', 'neutro', 'negativo']
    out['max_sentimiento'] = out[sent_cols].max(axis=1)
    out['n_sentimientos_max'] = out[sent_cols].eq(out['max_sentimiento'], axis=0).sum(axis=1)
    out['sentimiento_dominante'] = out[sent_cols].idxmax(axis=1)
    out.loc[out['n_sentimientos_max'] > 1, 'sentimiento_dominante'] = 'empate'
    out['es_empate'] = out['n_sentimientos_max'] > 1

    valores_ordenados = out[sent_cols].apply(lambda row: sorted(row.tolist(), reverse=True), axis=1)
    out['margen_dominancia'] = valores_ordenados.map(lambda vals: vals[0] - vals[1] if len(vals) > 1 else vals[0])

    for col in ['primer_comentario', 'ultimo_comentario']:
        out[col] = out[col].dt.strftime('%Y-%m-%d %H:%M:%S')
        out[col] = out[col].fillna('')

    out = out.rename(columns={'autor_handle_norm': 'autor_handle'})
    out = out.drop(columns=['max_sentimiento', 'n_sentimientos_max'])
    out = out.sort_values(
        by=['sentimiento_dominante', 'comentarios_totales', 'margen_dominancia', 'autor_handle'],
        ascending=[True, False, False, True]
    )

    master_path = os.path.join(POLARIDAD_FOLDER, f"{file_id}_cuentas_sentimiento_dominante.csv")
    out.to_csv(master_path, index=False, encoding='utf-8-sig')
    print(f"-> CSV maestro dominante: {os.path.basename(master_path)} ({len(out):,} cuentas)")

    for categoria in ['positivo', 'neutro', 'negativo', 'empate']:
        sub = out[out['sentimiento_dominante'] == categoria].copy()
        if sub.empty:
            print(f"-> Dominante {categoria}: 0 cuentas")
            continue
        sub_path = os.path.join(POLARIDAD_FOLDER, f"{file_id}_cuentas_dominante_{categoria}.csv")
        sub.to_csv(sub_path, index=False, encoding='utf-8-sig')
        print(f"-> CSV dominante {categoria}: {os.path.basename(sub_path)} ({len(sub):,} cuentas)")


def generar_evolucion_sentimiento_acumulada(df, file_id):
    """Líneas acumuladas mes a mes — estilo periodístico."""
    print("\n--- Generando evolución acumulada de sentimiento ---")

    if 'fecha' not in df.columns or 'sentimiento' not in df.columns:
        print("-> Faltan columnas 'fecha' o 'sentimiento'. Omitiendo.")
        return

    try:
        df = df.copy()
        df['fecha_dt'] = pd.to_datetime(df['fecha'], errors='coerce')
        df.dropna(subset=['fecha_dt'], inplace=True)
        df['año_mes'] = df['fecha_dt'].dt.to_period('M')

        todos_meses = df['año_mes'].sort_values().unique()
        pos_acum = df[df['sentimiento'] == 'positivo'].groupby('año_mes').size().reindex(todos_meses, fill_value=0).cumsum()
        neg_acum = df[df['sentimiento'] == 'negativo'].groupby('año_mes').size().reindex(todos_meses, fill_value=0).cumsum()

        etiquetas = [str(m) for m in todos_meses]
        x = list(range(len(etiquetas)))

        fig, ax = plt.subplots(figsize=(16, 9))
        fig.patch.set_facecolor('#FFFFFF')

        # Líneas acumuladas (sin fill_between — Tufte: data-ink ratio)
        ax.plot(x, pos_acum.values, color='#A93226', linewidth=2.5, marker='o', markersize=3, zorder=3)
        ax.plot(x, neg_acum.values, color='#4A4A4A', linewidth=2.5, marker='o', markersize=3, zorder=3)

        # Etiquetas directas al final de cada línea (sin leyenda separada)
        bbox_style = dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.9, edgecolor='#CCCCCC', linewidth=0.5)
        ax.annotate(f"Positivos\n{pos_acum.values[-1]:,}",
                    xy=(x[-1], pos_acum.values[-1]), xytext=(12, 0),
                    textcoords='offset points', color='#A93226', fontweight='bold', fontsize=10,
                    va='center', bbox=bbox_style)
        ax.annotate(f"Negativos\n{neg_acum.values[-1]:,}",
                    xy=(x[-1], neg_acum.values[-1]), xytext=(12, 0),
                    textcoords='offset points', color='#4A4A4A', fontweight='bold', fontsize=10,
                    va='center', bbox=bbox_style)

        # Título declarativo
        ratio = pos_acum.values[-1] / max(neg_acum.values[-1], 1)
        titulo = f"los comentarios positivos superan a los negativos en {ratio:.1f}x"
        ax.set_title(f"evolución acumulada de sentimiento en comentarios de {_get_account(file_id)}",
                     fontsize=14, color='#444444', pad=12)
        ax.text(0.02, 0.97, titulo,
                transform=ax.transAxes, fontsize=12, fontweight='bold',
                va='top', ha='left', color='#222222', bbox=_STAT_BOX)

        ax.set_xticks(x)
        ax.set_xticklabels(etiquetas, rotation=45, ha='right', fontsize=9)
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{int(v):,}"))
        ax.set_ylabel("Comentarios acumulados", fontsize=11, color='#222222')
        ax.set_xlim(-0.5, len(x) - 0.5)
        _apply_estilo_periodistico(ax)
        _add_watermark(ax)
        plt.tight_layout()
        save_plot(f"{file_id}_sentimiento_acumulado.png", folder=POLARIDAD_FOLDER)

    except Exception as e:
        print(f"-> Error generando evolución acumulada: {e}")


def generar_nubes_sentimiento(df, file_id):
    """Nubes de palabras y emojis por sentimiento — estilo periodístico."""
    print("\n--- 5. Generando Nubes de Sentimiento ---")

    df_pos = df[df['sentimiento'] == 'positivo']
    df_neg = df[df['sentimiento'] == 'negativo']

    from matplotlib.gridspec import GridSpec

    def _nube_con_titulo(fig, gs_title, gs_cloud, texto, color, wc_img):
        """Panel: fila de título + fila de nube sin solapamiento."""
        ax_t = fig.add_subplot(gs_title)
        ax_t.set_facecolor(color)
        ax_t.text(0.5, 0.5, texto, transform=ax_t.transAxes,
                  ha='center', va='center', fontsize=13, fontweight='bold', color='white')
        ax_t.axis('off')

        ax_c = fig.add_subplot(gs_cloud)
        if wc_img is not None:
            ax_c.imshow(wc_img, interpolation='bilinear')
        ax_c.axis('off')
        return ax_c

    WC_W, WC_H = 780, 780

    # --- NUBE DE TEXTO ---
    if not df_pos.empty or not df_neg.empty:
        fig = plt.figure(figsize=(16, 9))
        fig.patch.set_facecolor('#FFFFFF')
        gs = GridSpec(3, 2, figure=fig,
                      height_ratios=[0.06, 0.88, 0.06],
                      hspace=0.0, wspace=0.01,
                      left=0.0, right=1.0, top=0.93, bottom=0.0)

        texto_pos = " ".join(df_pos['texto'].dropna().astype(str))
        palabras_pos = [w for w in texto_pos.lower().split() if w in PALABRAS_POSITIVAS]
        wc_pos = None
        if palabras_pos:
            wc_pos = WordCloud(background_color="white", colormap='Reds',
                               width=WC_W, height=WC_H, max_words=200, collocations=False
                               ).generate(" ".join(palabras_pos)).to_array()

        texto_neg = " ".join(df_neg['texto'].dropna().astype(str))
        palabras_neg = [w for w in texto_neg.lower().split() if w in PALABRAS_NEGATIVAS]
        wc_neg = None
        if palabras_neg:
            wc_neg = WordCloud(background_color="white", colormap='Greys',
                               width=WC_W, height=WC_H, max_words=200, collocations=False
                               ).generate(" ".join(palabras_neg)).to_array()

        _nube_con_titulo(fig, gs[0, 0], gs[1, 0], 'PALABRAS DE APOYO / POSITIVAS', '#A93226', wc_pos)
        ax_wm = _nube_con_titulo(fig, gs[0, 1], gs[1, 1], 'PALABRAS DE CRÍTICA / NEGATIVAS', '#4A4A4A', wc_neg)
        fig.suptitle(f"palabras de apoyo y crítica en comentarios de {_get_account(file_id)}",
                     fontsize=13, color='#444444', y=0.98)
        _add_watermark(ax_wm)
        save_plot(f"{file_id}_nube_palabras_sentimiento.png", tight=False, folder=POLARIDAD_FOLDER)

    # --- NUBE DE EMOJIS ---
    if not df_pos.empty or not df_neg.empty:
        fig = plt.figure(figsize=(16, 9))
        fig.patch.set_facecolor('#FFFFFF')
        gs = GridSpec(3, 2, figure=fig,
                      height_ratios=[0.06, 0.88, 0.06],
                      hspace=0.0, wspace=0.01,
                      left=0.0, right=1.0, top=0.93, bottom=0.0)
        font = "C:/Windows/Fonts/seguiemj.ttf"

        wc_pos = None
        emojis_pos = ''.join(c for c in "".join(df_pos['texto'].dropna()) if c in EMOJIS_POSITIVOS)
        if emojis_pos:
            try:
                wc_pos = WordCloud(font_path=font, background_color='white', colormap='Reds',
                                   width=WC_W, height=WC_H, regexp=r"\S"
                                   ).generate(" ".join(emojis_pos)).to_array()
            except OSError:
                print("-> Fuente emoji no encontrada para positivos.")

        wc_neg = None
        emojis_neg = ''.join(c for c in "".join(df_neg['texto'].dropna()) if c in EMOJIS_NEGATIVOS)
        if emojis_neg:
            try:
                wc_neg = WordCloud(font_path=font, background_color='white', colormap='Greys',
                                   width=WC_W, height=WC_H, regexp=r"\S"
                                   ).generate(" ".join(emojis_neg)).to_array()
            except OSError:
                print("-> Fuente emoji no encontrada para negativos.")

        _nube_con_titulo(fig, gs[0, 0], gs[1, 0], 'EMOJIS DE APOYO / POSITIVOS', '#A93226', wc_pos)
        ax_wm = _nube_con_titulo(fig, gs[0, 1], gs[1, 1], 'EMOJIS DE CRÍTICA / NEGATIVOS', '#4A4A4A', wc_neg)
        fig.suptitle(f"emojis de apoyo y crítica en comentarios de {_get_account(file_id)}",
                     fontsize=13, color='#444444', y=0.98)
        _add_watermark(ax_wm)
        save_plot(f"{file_id}_nube_emojis_sentimiento.png", tight=False, folder=POLARIDAD_FOLDER)


# --- FUNCIÓN PRINCIPAL ---

def find_latest_csv(data_dirs=None):
    """Busca el CSV de comentarios más reciente en las carpetas de datos.
    Busca en: data/, data_tiktok/ y outputs/"""
    if data_dirs is None:
        data_dirs = [
            os.path.join(BASE_DIR, "data"),
            os.path.join(BASE_DIR, "data_tiktok"),
        ]

    csv_files = []
    for data_dir in data_dirs:
        if not os.path.exists(data_dir):
            continue

        for root, dirs, files in os.walk(data_dir):
            for file in files:
                if file.endswith("_comentarios.csv") or file.endswith("_comentarios_api.csv"):
                    full_path = os.path.join(root, file)
                    try:
                        mtime = os.path.getmtime(full_path)
                        csv_files.append((mtime, full_path))
                    except:
                        pass

    if csv_files:
        csv_files.sort(reverse=True)
        print(f"📋 CSVs de comentarios encontrados:")
        for _, path in csv_files[:5]:  # Muestra los 5 más recientes
            size = os.path.getsize(path) / 1024  # KB
            print(f"   • {os.path.basename(path)} ({size:.1f} KB)")
        return csv_files[0][1]  # Retorna la ruta del más reciente
    return None

def main(csv_file_arg=None):
    print("--- INICIANDO ANALÍTICA DE COMENTARIOS TIKTOK ---\n")

    # Si se proporciona como argumento, usarlo
    csv_file = csv_file_arg

    # Si no, intenta abrir el diálogo de selección
    if not csv_file:
        print("📂 Abriendo diálogo para seleccionar archivo...")
        print("   (si no se abre automáticamente, revisa tu escritorio)\n")
        try:
            csv_file = get_file_path()
            if csv_file:
                print(f"✅ Archivo seleccionado: {os.path.basename(csv_file)}\n")
        except Exception as e:
            print(f"⚠️ Error en diálogo gráfico: {e}\n")

    # Si no seleccionó archivo, busca automáticamente
    if not csv_file:
        print("🔍 Buscando CSV de comentarios más reciente...")
        csv_file = find_latest_csv()

        if csv_file:
            print(f"✅ Encontrado: {csv_file}")
        else:
            print("\n❌ ERROR: No se encontró ningún CSV de comentarios.")
            print("\n📋 Pasos a seguir:")
            print("  1. Ejecuta la opción 1 o 2 del menú para descargar videos")
            print("  2. Luego ejecuta la opción 3 para descargar comentarios")
            print("  3. Después ejecuta esta opción nuevamente")
            input("\nPresiona Enter para volver al menú...")
            return

    base_name = os.path.basename(csv_file)
    file_id = os.path.splitext(base_name)[0]
    print(f"\nProcesando archivo: {file_id}")
    create_output_folder(file_id)

    try:
        df = pd.read_csv(csv_file)
        required_cols = ['texto', 'autor_handle', 'likes', 'fecha']
        if not all(col in df.columns for col in required_cols):
            print(f"Error: El CSV debe contener las columnas: {', '.join(required_cols)}")
            missing = [col for col in required_cols if col not in df.columns]
            print(f"Columnas faltantes: {', '.join(missing)}")
            return
        print(f"Cargados {len(df):,} comentarios en total.")
    except Exception as e:
        print(f"Error crítico al leer el CSV: {e}")
        return

    # Filtrar solo comentarios directos (no replies)
    if 'is_reply' in df.columns:
        n_total = len(df)
        df = df[df['is_reply'] == 0].copy()
        n_replies = n_total - len(df)
        print(f"Filtrando comentarios directos: {len(df):,} ({len(df)/n_total*100:.1f}%) — {n_replies:,} replies excluidas")
    else:
        print("Columna 'is_reply' no encontrada — se analizan todos los comentarios.")

    # --- Interfaz de Colores (con fallback a valores por defecto) ---
    final_color_text = '#A93226'  # Color por defecto (rojo TikTok)
    final_color_bars = 'steelblue'  # Color por defecto (azul)

    try:
        root = tk.Tk()
        root.withdraw()
        root.after(100, root.quit)  # Timeout después de 100ms si no hay respuesta

        try:
            color_input_text = simpledialog.askstring("Personalización", f"Color para NUBES DE PALABRAS de '{file_id}'\n(Ej: movistar, digi, rojo, azul):", initialvalue='rojo')
            if color_input_text:
                final_color_text = validate_color(color_input_text)
        except:
            pass

        try:
            color_input_bars = simpledialog.askstring("Personalización", f"Color para GRÁFICAS DE BARRAS de '{file_id}'\n(Ej: cian, gris, orange):", initialvalue='steelblue')
            if color_input_bars:
                final_color_bars = validate_color(color_input_bars, default='steelblue')
        except:
            pass

        root.destroy()
    except Exception as e:
        print(f"⚠️ Diálogos de color deshabilitados. Usando colores por defecto.")
        print(f"   (Detalles: {e})")

    print(f"\n🎨 Colores: Nubes={final_color_text}, Barras={final_color_bars}")

    # --- Generar Análisis ---
    generar_ranking_palabras(df, file_id, final_color_bars)   # ranking antes de nube
    generar_nubes(df, file_id, final_color_text, final_color_text)
    generar_analisis_comunidad(df, file_id, final_color_bars)
    generar_analisis_temporal(df, file_id, final_color_bars)

    # --- Análisis de Sentimiento con IA ---
    df_sentimiento = analizar_sentimiento_ia(df)
    generar_grafica_sentimiento(df_sentimiento, file_id, final_color_bars)
    generar_evolucion_sentimiento_acumulada(df_sentimiento, file_id)
    generar_nubes_sentimiento(df_sentimiento, file_id)
    generar_top_emojis(df_sentimiento, file_id)
    exportar_cuentas_por_sentimiento(df_sentimiento, file_id)
    exportar_cuentas_sentimiento_dominante(df_sentimiento, file_id)

    print(f"\n✅ ¡PROCESO COMPLETADO!")
    print(f"📂 Revisa la carpeta '{OUTPUT_FOLDER}' para ver los resultados de '{file_id}'.")
    input("\nPresiona Enter para volver al menú...")

if __name__ == "__main__":
    import sys

    csv_arg = None
    # Permite pasar la ruta del CSV como argumento: python analitica_comentarios.py "path/to/file.csv"
    if len(sys.argv) > 1:
        csv_arg = sys.argv[1]
        if not os.path.exists(csv_arg):
            print(f"❌ Archivo no encontrado: {csv_arg}")
            csv_arg = None

    main(csv_arg)
