import argparse
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
from wordcloud import WordCloud, STOPWORDS
import os
import re
import emoji
from matplotlib.colors import to_rgb

try:
    import tkinter as tk
    from tkinter import filedialog, simpledialog
    _HAS_TK = True
except Exception:
    _HAS_TK = False

# --- CONFIGURACIÓN ---
BASE_DIR        = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUTPUT_BASE     = os.path.join(BASE_DIR, "outputs")
OUTPUT_FOLDER   = OUTPUT_BASE
LOGO_TIKTOK     = os.path.join(BASE_DIR, "assets", "tiktok_logo.jpg")
TWITTER_DPI    = 100   # 16×9 inches × 100dpi = 1600×900px
FONT_EMOJI     = "C:/Windows/Fonts/seguiemj.ttf"

import sys as _sys
_sys.path.insert(0, BASE_DIR)
from config.viz_style import (
    PALETA, PALETA_CAT, COLOR_MARCA, STAT_BOX, apply_estilo_periodistico
)

# Mapa de traducción para entradas de usuario (nombre → código hex)
COLOR_TRANSLATOR = {
    'rojo': '#A93226', 'azul': '#1F618D', 'verde': '#1E8449',
    'amarillo': '#F39C12', 'negro': '#222222', 'blanco': 'white',
    'naranja': '#CA6F1E', 'rosa': '#C0392B', 'morado': '#7D3C98',
    'gris': '#4A4A4A', 'cian': '#117A65',
    **COLOR_MARCA,
}


# --- UTILIDADES ---

def create_output_folder(file_id=None):
    global OUTPUT_FOLDER
    if file_id:
        project = file_id.split('_videos')[0] if '_videos' in file_id else file_id
        OUTPUT_FOLDER = os.path.join(OUTPUT_BASE, project, "publicaciones")
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

def save_plot(filename, tight=True):
    path = os.path.join(OUTPUT_FOLDER, filename)
    if tight:
        plt.savefig(path, bbox_inches='tight', dpi=TWITTER_DPI, facecolor='white')
    else:
        plt.savefig(path, dpi=TWITTER_DPI, facecolor='white')
    print(f"-> Guardado: {filename}")
    plt.close()

def get_file_path():
    if _HAS_TK:
        try:
            root = tk.Tk(); root.withdraw()
            return filedialog.askopenfilename(
                title="Selecciona el archivo CSV de TikTok",
                filetypes=[("CSV Files", "*.csv")])
        except Exception:
            pass
    return input("Ruta al CSV de TikTok: ").strip()

def ask_string(title, prompt):
    if _HAS_TK:
        try:
            root = tk.Tk(); root.withdraw()
            return simpledialog.askstring(title, prompt)
        except Exception:
            pass
    return input(f"{prompt}\n> ").strip()

def validate_color(color_input):
    if not color_input: return '#A93226'
    return COLOR_TRANSLATOR.get(color_input.lower().strip(), color_input.strip())

def make_color_func(target_color):
    try:
        rgb = to_rgb(target_color)
    except ValueError:
        return lambda *a, **k: '#222222'
    def color_func(word, font_size, position, orientation, random_state=None, **kwargs):
        r, g, b = rgb
        factor = random_state.uniform(0.5, 1.0) if random_state else 0.8
        return (int(r*factor*255), int(g*factor*255), int(b*factor*255))
    return color_func

def clean_text(text):
    if not isinstance(text, str): return ""
    text = re.sub(r'http\S+', '', text)
    return emoji.replace_emoji(text, replace='')

def extract_emojis(text):
    if not isinstance(text, str): return ""
    return ''.join(c for c in text if c in emoji.EMOJI_DATA)


# --- GRÁFICAS ---

def _add_watermark(ax):
    """Logo de TikTok como marca de agua discreta en la esquina inferior derecha."""
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


def _get_account(file_id):
    """Extrae el nombre de cuenta a partir del file_id. Ej: user_sanchezcastejon_videos → @sanchezcastejon"""
    name = file_id.split('_videos')[0] if '_videos' in file_id else file_id
    if name.startswith('user_'):
        return f"@{name[5:]}"
    return name

_STAT_BOX = dict(boxstyle='round,pad=0.5', facecolor='white', alpha=0.92,
                 edgecolor='#CCCCCC', linewidth=0.8)


def graf_nube_palabras(df, file_id, color):
    print("Generando nube de palabras...")
    all_desc = " ".join(df['video_desc'].dropna().astype(str))
    sw = set(STOPWORDS)
    sw.update(['de','la','que','el','en','y','a','los','del','se','las','por','un',
               'para','con','no','una','su','al','lo','como','más','pero','sus','le',
               'ya','o','este','sí','porque','esta','entre','cuando','muy','sin',
               'sobre','también','me','hasta','hay','donde','quien','desde','todo',
               'nos','durante','todos','uno','les','ni','contra','otros','ese','eso',
               'ante','ellos','e','esto','mí','antes','algunos','qué','unos','yo',
               'otro','otras','otra','él','tanto','esa','estos','mucho','cual','poco',
               'ella','estar','estas','algunas','algo','es','son','fue','era',
               'video','tiktok'])
    wc = WordCloud(stopwords=sw, background_color='white', color_func=make_color_func(color),
                   width=1600, height=900, max_words=200).generate(clean_text(all_desc))
    fig, ax = plt.subplots(figsize=(16, 9))
    fig.patch.set_facecolor('#FFFFFF')
    ax.imshow(wc, interpolation='bilinear')
    ax.axis('off')
    ax.set_title(f"palabras más usadas por {_get_account(file_id)}",
                 fontsize=14, color='#444444', pad=12)
    _add_watermark(ax)
    save_plot(f"{file_id}_nube_palabras.png", tight=False)


def graf_nube_hashtags(df, file_id, color):
    if 'hashtags' not in df.columns:
        return
    all_hashtags = []
    for tags in df['hashtags'].dropna():
        all_hashtags.extend(tags.split('|'))
    if not all_hashtags:
        return
    print("Generando nube de hashtags...")
    wc = WordCloud(background_color='white', color_func=make_color_func(color),
                   width=1600, height=900, max_words=150).generate(" ".join(all_hashtags))
    fig, ax = plt.subplots(figsize=(16, 9))
    fig.patch.set_facecolor('#FFFFFF')
    ax.imshow(wc, interpolation='bilinear')
    ax.axis('off')
    ax.set_title(f"hashtags más usados por {_get_account(file_id)}",
                 fontsize=14, color='#444444', pad=12)
    _add_watermark(ax)
    save_plot(f"{file_id}_nube_hashtags.png", tight=False)


def graf_nube_emoticonos(df, file_id, color):
    all_desc = " ".join(df['video_desc'].dropna().astype(str))
    emojis_found = extract_emojis(all_desc)
    if not emojis_found:
        return
    print("Generando nube de emoticonos...")
    try:
        wc = WordCloud(background_color='white', color_func=make_color_func(color),
                       font_path=FONT_EMOJI, width=1600, height=900,
                       regexp=r"\S").generate(" ".join(emojis_found))
    except OSError:
        wc = WordCloud(background_color='white', color_func=make_color_func(color),
                       width=1600, height=900, regexp=r"\S").generate(" ".join(emojis_found))
    fig, ax = plt.subplots(figsize=(16, 9))
    fig.patch.set_facecolor('#FFFFFF')
    ax.imshow(wc, interpolation='bilinear')
    ax.axis('off')
    ax.set_title(f"emoticonos más usados por {_get_account(file_id)}",
                 fontsize=14, color='#444444', pad=12)
    _add_watermark(ax)
    save_plot(f"{file_id}_nube_emoticonos.png", tight=False)


def graf_evolucion_vistas(df, file_id, color):
    print("Generando evolución de vistas...")
    fig, ax = plt.subplots(figsize=(16, 9))
    fig.patch.set_facecolor('#FFFFFF')

    ax.plot(df['video_fecha_dt'], df['video_vistas'],
            marker='o', linestyle='-', color=color, markersize=4, linewidth=2)
    ax.fill_between(df['video_fecha_dt'], df['video_vistas'], alpha=0.06, color=color)

    max_vistas = df['video_vistas'].max()
    ax.set_title(f"evolución de vistas de {_get_account(file_id)}",
                 fontsize=14, color='#444444', pad=12)
    ax.text(0.02, 0.97, f"pico de {max_vistas:,.0f} vistas en un solo vídeo",
            transform=ax.transAxes, fontsize=12, fontweight='bold',
            va='top', ha='left', color='#222222', bbox=_STAT_BOX)
    ax.set_xlabel("Fecha", fontsize=11)
    ax.set_ylabel("Vistas", fontsize=11)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{int(v):,}"))
    ax.tick_params(axis='x', rotation=45)
    apply_estilo_periodistico(ax)
    _add_watermark(ax)
    plt.tight_layout()
    save_plot(f"{file_id}_evolucion_vistas.png")


def graf_publicaciones_por_mes(df, file_id, color):
    print("Generando publicaciones por mes...")
    df['año_mes'] = df['video_fecha_dt'].dt.to_period('M')
    pub_por_mes = df.groupby('año_mes').size()

    fig, ax = plt.subplots(figsize=(16, 9))
    fig.patch.set_facecolor('#FFFFFF')
    x = range(len(pub_por_mes))
    bars = ax.bar(x, pub_por_mes.values, color=color, edgecolor='none', alpha=0.85)

    for i, v in enumerate(pub_por_mes.values):
        ax.text(i, v + pub_por_mes.max() * 0.01, str(v),
                ha='center', va='bottom', fontsize=9, color='#222222', fontweight='bold')

    mes_pico = pub_por_mes.idxmax()
    ax.set_title(f"publicaciones por mes de {_get_account(file_id)}",
                 fontsize=14, color='#444444', pad=12)
    ax.text(0.02, 0.97, f"mes más activo: {mes_pico} con {pub_por_mes.max()} publicaciones",
            transform=ax.transAxes, fontsize=12, fontweight='bold',
            va='top', ha='left', color='#222222', bbox=_STAT_BOX)
    ax.set_ylabel("Publicaciones", fontsize=11)
    ax.set_xticks(list(x))
    ax.set_xticklabels([str(m) for m in pub_por_mes.index], rotation=45, ha='right', fontsize=9)
    ax.set_ylim(0, pub_por_mes.max() * 1.18)
    apply_estilo_periodistico(ax)
    _add_watermark(ax)
    plt.tight_layout()
    save_plot(f"{file_id}_publicaciones_por_mes.png")


def graf_publicaciones_por_dia(df, file_id, color):
    print("Generando publicaciones por día de semana...")
    dias_semana = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
    df['dia_semana'] = df['video_fecha_dt'].dt.dayofweek
    pub_por_dia = df.groupby('dia_semana').size().reindex(range(7), fill_value=0)

    fig, ax = plt.subplots(figsize=(16, 9))
    fig.patch.set_facecolor('#FFFFFF')

    # Destacar el día pico con color pleno, resto con alpha
    colores_barras = [color if i == pub_por_dia.idxmax() else color + '99' for i in range(7)]
    bars = ax.bar(dias_semana, pub_por_dia.values, color=colores_barras, edgecolor='none')

    for bar, v in zip(bars, pub_por_dia.values):
        ax.text(bar.get_x() + bar.get_width()/2, v + pub_por_dia.max()*0.01,
                str(v), ha='center', va='bottom', fontsize=10,
                color='#222222', fontweight='bold')

    dia_pico = dias_semana[pub_por_dia.idxmax()]
    ax.set_title(f"publicaciones por día de la semana de {_get_account(file_id)}",
                 fontsize=14, color='#444444', pad=12)
    ax.text(0.02, 0.97, f"{dia_pico.lower()} es el día con más publicaciones",
            transform=ax.transAxes, fontsize=12, fontweight='bold',
            va='top', ha='left', color='#222222', bbox=_STAT_BOX)
    ax.set_ylabel("Publicaciones", fontsize=11)
    ax.set_ylim(0, pub_por_dia.max() * 1.18)
    apply_estilo_periodistico(ax)
    _add_watermark(ax)
    plt.tight_layout()
    save_plot(f"{file_id}_publicaciones_por_dia_semana.png")


def graf_publicaciones_por_hora(df, file_id, color):
    print("Generando publicaciones por hora...")
    df['hora'] = df['video_fecha_dt'].dt.hour
    pub_por_hora = df.groupby('hora').size().reindex(range(24), fill_value=0)
    max_hora = pub_por_hora.idxmax()

    fig, ax = plt.subplots(figsize=(16, 9))
    fig.patch.set_facecolor('#FFFFFF')

    colores_barras = [color if i == max_hora else color + '88' for i in range(24)]
    ax.bar(range(24), pub_por_hora.values, color=colores_barras, edgecolor='none')

    ax.set_title(f"publicaciones por hora de {_get_account(file_id)}",
                 fontsize=14, color='#444444', pad=12)
    ax.text(0.02, 0.97, f"hora pico de publicación: {max_hora:02d}:00h",
            transform=ax.transAxes, fontsize=12, fontweight='bold',
            va='top', ha='left', color='#222222', bbox=_STAT_BOX)
    ax.set_ylabel("Publicaciones", fontsize=11)
    ax.set_xlabel("Hora del día", fontsize=11)
    ax.set_xticks(range(24))
    ax.set_xticklabels([f"{h:02d}h" for h in range(24)], rotation=45, ha='right', fontsize=8)
    apply_estilo_periodistico(ax)
    _add_watermark(ax)
    plt.tight_layout()
    save_plot(f"{file_id}_publicaciones_por_hora.png")


def graf_heatmap(df, file_id):
    print("Generando heatmap de actividad...")
    dias_semana = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
    heatmap_data = df.groupby(['dia_semana', 'hora']).size().unstack(fill_value=0)
    heatmap_data = heatmap_data.reindex(index=range(7), columns=range(24), fill_value=0)

    fig, ax = plt.subplots(figsize=(16, 9))
    fig.patch.set_facecolor('#FFFFFF')
    im = ax.imshow(heatmap_data.values, cmap='Reds', aspect='auto')
    plt.colorbar(im, ax=ax, label='Publicaciones', shrink=0.8)
    ax.set_title(f"mapa de calor de actividad de publicación de {_get_account(file_id)}",
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
    save_plot(f"{file_id}_heatmap_actividad.png")


def graf_timeline(df, file_id, color):
    print("Generando timeline acumulado...")
    df_s = df.sort_values('video_fecha_dt').copy()
    df_s['pub_acumuladas'] = range(1, len(df_s) + 1)

    fig, ax = plt.subplots(figsize=(16, 9))
    fig.patch.set_facecolor('#FFFFFF')
    ax.plot(df_s['video_fecha_dt'], df_s['pub_acumuladas'], color=color, linewidth=2.5)
    ax.fill_between(df_s['video_fecha_dt'], df_s['pub_acumuladas'], alpha=0.06, color=color)

    ax.set_title(f"evolución acumulada de publicaciones de {_get_account(file_id)}",
                 fontsize=14, color='#444444', pad=12)
    ax.text(0.02, 0.97, f"{len(df_s):,} publicaciones acumuladas en el periodo analizado",
            transform=ax.transAxes, fontsize=12, fontweight='bold',
            va='top', ha='left', color='#222222', bbox=_STAT_BOX)
    ax.set_ylabel("Publicaciones acumuladas", fontsize=11)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{int(v):,}"))
    ax.tick_params(axis='x', rotation=45)
    apply_estilo_periodistico(ax)
    _add_watermark(ax)
    plt.tight_layout()
    save_plot(f"{file_id}_timeline_publicaciones.png")


# --- PRINCIPAL ---

def main():
    parser = argparse.ArgumentParser(description="Analítica TikTok — genera gráficas PNG")
    parser.add_argument("csv", nargs="?", help="Ruta al CSV de videos")
    parser.add_argument("--color-texto", dest="color_texto")
    parser.add_argument("--color-emoji", dest="color_emoji")
    args = parser.parse_args()

    print("--- INICIANDO ANALÍTICA TIKTOK ---")

    csv_file = args.csv or get_file_path()
    if not csv_file:
        print("Operación cancelada.")
        return

    file_id = os.path.splitext(os.path.basename(csv_file))[0]
    print(f"Procesando: {file_id}")
    create_output_folder(file_id)

    try:
        df = pd.read_csv(csv_file)
        print(f"Cargados {len(df):,} registros.")
    except Exception as e:
        print(f"Error: {e}"); return

    color_text = validate_color(args.color_texto or ask_string(
        "Color", f"Color principal para '{file_id}'\n(Ej: psoe, rojo, azul, movistar):"))
    color_emoji = validate_color(args.color_emoji or ask_string(
        "Color emoji", f"Color para emoticonos (Enter = mismo que principal):") or args.color_texto)

    # Nubes
    graf_nube_palabras(df, file_id, color_text)
    graf_nube_hashtags(df, file_id, color_text)
    graf_nube_emoticonos(df, file_id, color_emoji)

    # Reporte TXT
    metrics = ['video_likes', 'video_vistas', 'video_compartidos', 'video_comentarios', 'video_guardados']
    with open(os.path.join(OUTPUT_FOLDER, f"{file_id}_mejores_videos.txt"), "w", encoding="utf-8") as f:
        f.write(f"--- REPORTE DE MEJORES VIDEOS: {file_id} ---\n\n")
        for m in metrics:
            if m in df.columns:
                top = df.loc[df[m].idxmax()]
                f.write(f"GANADOR EN {m.upper()}: {top[m]:,}\nDesc: {top['video_desc']}\nURL: {top['video_url']}\n\n")
    print(f"-> Reporte: {file_id}_mejores_videos.txt")

    # Gráficas temporales
    if 'video_fecha' in df.columns:
        try:
            df['video_fecha_dt'] = pd.to_datetime(df['video_fecha'], dayfirst=True)
            df = df.sort_values('video_fecha_dt')
            df['dia_semana'] = df['video_fecha_dt'].dt.dayofweek
            df['hora']       = df['video_fecha_dt'].dt.hour

            graf_evolucion_vistas(df, file_id, color_text)
            graf_publicaciones_por_mes(df, file_id, color_text)
            graf_publicaciones_por_dia(df, file_id, color_text)
            graf_publicaciones_por_hora(df, file_id, color_text)
            graf_heatmap(df, file_id)
            graf_timeline(df, file_id, color_text)

        except Exception as e:
            print(f"-> Error en gráficas temporales: {e}")

    print(f"\n¡PROCESO COMPLETADO! Revisa '{OUTPUT_FOLDER}/'")

if __name__ == "__main__":
    main()
