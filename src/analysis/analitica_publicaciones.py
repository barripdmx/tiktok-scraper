import argparse
import numpy as np
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


# ── GRÁFICAS DE RENDIMIENTO (nuevas) ─────────────────────────────────────────

def graf_distribucion_vistas(df, file_id, color):
    """10. Histograma logarítmico de vistas con media y mediana."""
    print("Generando distribución de vistas (log)...")
    vistas = pd.to_numeric(df['video_vistas'], errors='coerce').dropna()
    vistas = vistas[vistas > 0]
    if len(vistas) < 5:
        return

    media   = vistas.mean()
    mediana = vistas.median()

    bins = np.logspace(np.log10(vistas.min()), np.log10(vistas.max()), 40)
    fig, ax = plt.subplots(figsize=(16, 9))
    fig.patch.set_facecolor('#FFFFFF')

    ax.hist(vistas, bins=bins, color=color, edgecolor='none', alpha=0.82)
    ax.axvline(media,   color='#A93226', linewidth=1.8, linestyle='--',
               label=f'Media   {media:,.0f}')
    ax.axvline(mediana, color='#1F618D', linewidth=1.8, linestyle=':',
               label=f'Mediana {mediana:,.0f}')
    ax.set_xscale('log')
    ax.legend(fontsize=10, framealpha=0.9)
    ax.set_title(f"distribución de vistas de {_get_account(file_id)}",
                 fontsize=14, color='#444444', pad=12)
    ax.set_xlabel("Vistas (escala logarítmica)", fontsize=11)
    ax.set_ylabel("Número de vídeos", fontsize=11)
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{int(v):,}"))
    concentracion = (vistas >= mediana * 10).mean() * 100
    ax.text(0.02, 0.97,
            f"mediana {mediana:,.0f} · media {media:,.0f} vistas",
            transform=ax.transAxes, fontsize=12, fontweight='bold',
            va='top', ha='left', color='#222222', bbox=_STAT_BOX)
    apply_estilo_periodistico(ax)
    _add_watermark(ax)
    plt.tight_layout()
    save_plot(f"{file_id}_distribucion_vistas.png")


def graf_scatter_vistas_engagement(df, file_id, color):
    """11. Scatter: vistas vs engagement rate con etiquetas de cuadrante."""
    print("Generando scatter vistas vs engagement...")
    work = df.copy()
    for c in ['video_vistas', 'video_likes', 'video_comentarios',
              'video_compartidos', 'video_guardados']:
        work[c] = pd.to_numeric(work.get(c, 0), errors='coerce').fillna(0)

    work = work[work['video_vistas'] > 0].copy()
    if len(work) < 5:
        return

    work['eng_rate'] = (
        work['video_likes'] + work['video_comentarios'] +
        work['video_compartidos'] + work['video_guardados']
    ) / work['video_vistas'] * 100

    med_views = work['video_vistas'].median()
    med_er    = work['eng_rate'].median()

    # Color por cuadrante
    def _cuadrante_color(r):
        if r['video_vistas'] >= med_views and r['eng_rate'] >= med_er:
            return '#1E8449'   # verde  — viral de alta calidad
        if r['video_vistas'] >= med_views and r['eng_rate'] < med_er:
            return '#A93226'   # rojo   — viral vacío
        if r['video_vistas'] < med_views and r['eng_rate'] >= med_er:
            return '#1F618D'   # azul   — comunidad comprometida
        return '#AAAAAA'       # gris   — bajo alcance y engagement

    point_colors = work.apply(_cuadrante_color, axis=1)

    fig, ax = plt.subplots(figsize=(16, 9))
    fig.patch.set_facecolor('#FFFFFF')

    ax.scatter(work['video_vistas'], work['eng_rate'],
               c=point_colors, alpha=0.65, s=55, edgecolors='none')
    ax.axvline(med_views, color='#CCCCCC', linewidth=1, linestyle='--')
    ax.axhline(med_er,    color='#CCCCCC', linewidth=1, linestyle='--')
    ax.set_xscale('log')
    ax.set_xlabel("Vistas (escala log)", fontsize=11)
    ax.set_ylabel("Engagement Rate (%)", fontsize=11)
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{int(v):,}"))
    ax.set_title(f"vistas vs engagement rate — {_get_account(file_id)}",
                 fontsize=14, color='#444444', pad=12)

    # Etiquetas de cuadrante
    for (tx, ty, txt, col) in [
        (0.73, 0.96, "viral de alta calidad",    '#1E8449'),
        (0.73, 0.08, "viral vacío",               '#A93226'),
        (0.02, 0.96, "comunidad comprometida",    '#1F618D'),
        (0.02, 0.08, "bajo alcance y engagement", '#999999'),
    ]:
        ax.text(tx, ty, txt, transform=ax.transAxes, fontsize=9,
                color=col, ha='left', va='top', alpha=0.85)

    apply_estilo_periodistico(ax)
    ax.grid(axis='x', color='#EBEBEB', linewidth=0.5)
    _add_watermark(ax)
    plt.tight_layout()
    save_plot(f"{file_id}_scatter_vistas_engagement.png")


def graf_duracion_vs_vistas(df, file_id, color):
    """12. Vistas medias por bucket de duración del vídeo."""
    if 'video_duracion_seg' not in df.columns:
        return
    print("Generando duración vs vistas...")
    work = df.copy()
    work['video_duracion_seg'] = pd.to_numeric(work['video_duracion_seg'], errors='coerce')
    work['video_vistas']       = pd.to_numeric(work['video_vistas'],       errors='coerce')
    work = work.dropna(subset=['video_duracion_seg', 'video_vistas'])
    work = work[work['video_duracion_seg'] > 0]
    if len(work) < 5:
        return

    buckets = [(0, 15, '≤15s'), (15, 30, '16-30s'), (30, 60, '31-60s'), (60, 9999, '>60s')]
    labels, means, ns = [], [], []
    for lo, hi, lbl in buckets:
        sub = work[(work['video_duracion_seg'] > lo) & (work['video_duracion_seg'] <= hi)]
        if len(sub) >= 2:
            labels.append(f"{lbl}\n(n={len(sub)})")
            means.append(sub['video_vistas'].mean())
            ns.append(len(sub))
    if not labels:
        return

    max_mean = max(means)
    bar_colors = [color if v == max_mean else color + '99' for v in means]
    fig, ax = plt.subplots(figsize=(16, 9))
    fig.patch.set_facecolor('#FFFFFF')
    bars = ax.bar(range(len(labels)), means, color=bar_colors, edgecolor='none', width=0.55)
    for bar, v in zip(bars, means):
        ax.text(bar.get_x() + bar.get_width() / 2, v + max_mean * 0.01,
                f"{int(v):,}", ha='center', va='bottom',
                fontsize=11, fontweight='bold', color='#222222')

    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, fontsize=11)
    ax.set_ylabel("Vistas medias", fontsize=11)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{int(v):,}"))
    ax.set_ylim(0, max_mean * 1.22)
    ax.set_title(f"duración del vídeo vs vistas medias — {_get_account(file_id)}",
                 fontsize=14, color='#444444', pad=12)
    best = labels[means.index(max_mean)].split('\n')[0]
    ax.text(0.02, 0.97, f"los vídeos {best} generan más vistas de media",
            transform=ax.transAxes, fontsize=12, fontweight='bold',
            va='top', ha='left', color='#222222', bbox=_STAT_BOX)
    apply_estilo_periodistico(ax)
    _add_watermark(ax)
    plt.tight_layout()
    save_plot(f"{file_id}_duracion_vs_vistas.png")


def graf_pareto_vistas(df, file_id, color):
    """14. Curva de Pareto: % de vídeos vs % acumulado de vistas."""
    print("Generando curva de Pareto de vistas...")
    vistas = pd.to_numeric(df['video_vistas'], errors='coerce').dropna()
    vistas = vistas[vistas >= 0].sort_values(ascending=False).reset_index(drop=True)
    if len(vistas) < 5:
        return

    total      = vistas.sum()
    pct_videos = (vistas.index + 1) / len(vistas) * 100
    pct_vistas = vistas.cumsum() / total * 100

    fig, ax = plt.subplots(figsize=(16, 9))
    fig.patch.set_facecolor('#FFFFFF')

    ax.plot(pct_videos, pct_vistas, color=color, linewidth=2.5,
            label='Concentración real')
    ax.plot([0, 100], [0, 100], color='#CCCCCC', linewidth=1.2,
            linestyle='--', label='Igualdad perfecta')
    ax.fill_between(pct_videos, pct_vistas, pct_videos, alpha=0.08, color=color)

    idx_20 = int(np.searchsorted(pct_videos.values, 20))
    if idx_20 < len(pct_vistas):
        y_20 = float(pct_vistas.iloc[min(idx_20, len(pct_vistas) - 1)])
        ax.axvline(20,  color='#A93226', linewidth=1, linestyle=':')
        ax.axhline(y_20, color='#A93226', linewidth=1, linestyle=':')
        ax.scatter([20], [y_20], color='#A93226', s=65, zorder=5)
        ax.text(0.02, 0.97,
                f"el 20% de los vídeos acumula el {y_20:.0f}% de las vistas",
                transform=ax.transAxes, fontsize=12, fontweight='bold',
                va='top', ha='left', color='#222222', bbox=_STAT_BOX)

    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.set_xlabel("% de vídeos (ordenados por vistas desc)", fontsize=11)
    ax.set_ylabel("% acumulado de vistas totales", fontsize=11)
    ax.set_title(f"concentración del alcance (Pareto) — {_get_account(file_id)}",
                 fontsize=14, color='#444444', pad=12)
    ax.legend(fontsize=10, framealpha=0.9)
    apply_estilo_periodistico(ax)
    ax.grid(axis='x', color='#EBEBEB', linewidth=0.5)
    _add_watermark(ax)
    plt.tight_layout()
    save_plot(f"{file_id}_pareto_vistas.png")


def graf_engagement_desglose(df, file_id):
    """15. Barras horizontales apiladas con desglose de likes/comentarios/compartidos/guardados para top 10."""
    print("Generando desglose de engagement (top 10)...")
    work = df.copy()
    eng_cols = [c for c in ['video_likes', 'video_comentarios',
                             'video_compartidos', 'video_guardados']
                if c in work.columns]
    if not eng_cols or 'video_vistas' not in work.columns:
        return

    for c in eng_cols + ['video_vistas']:
        work[c] = pd.to_numeric(work[c], errors='coerce').fillna(0)

    top10 = work.nlargest(10, 'video_vistas').copy()
    if top10.empty:
        return

    if 'video_desc' in top10.columns:
        etiquetas = [
            (str(d)[:38] + '…' if len(str(d)) > 38 else str(d))
            for d in top10['video_desc'].fillna('(sin desc)')
        ]
    else:
        etiquetas = [f"Vídeo #{i+1}" for i in range(len(top10))]

    meta_cols = {
        'video_likes':        ('Likes',        '#1F618D'),
        'video_comentarios':  ('Comentarios',  '#A93226'),
        'video_compartidos':  ('Compartidos',  '#CA6F1E'),
        'video_guardados':    ('Guardados',    '#4A4A4A'),
    }

    fig, ax = plt.subplots(figsize=(16, 9))
    fig.patch.set_facecolor('#FFFFFF')

    acum = np.zeros(len(top10))
    for col, (label, col_color) in meta_cols.items():
        if col not in top10.columns:
            continue
        vals = top10[col].values.astype(float)
        ax.barh(range(len(top10)), vals, left=acum, color=col_color,
                edgecolor='none', height=0.65, label=label, alpha=0.88)
        acum += vals

    ax.set_yticks(range(len(top10)))
    ax.set_yticklabels(etiquetas, fontsize=9)
    ax.set_xlabel("Interacciones", fontsize=11)
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{int(v):,}"))
    ax.set_title(f"desglose de engagement — top 10 vídeos de {_get_account(file_id)}",
                 fontsize=14, color='#444444', pad=12)
    ax.legend(loc='lower right', fontsize=10, framealpha=0.9)
    apply_estilo_periodistico(ax)
    ax.spines['left'].set_visible(False)
    ax.tick_params(axis='y', left=False)
    _add_watermark(ax)
    plt.tight_layout()
    save_plot(f"{file_id}_engagement_desglose.png")


def graf_cadencia_publicacion(df, file_id, color):
    """17. Vídeos publicados por semana con media móvil de 4 semanas."""
    print("Generando cadencia de publicación (rolling 4 semanas)...")
    if 'video_fecha_dt' not in df.columns:
        return
    dft = df.dropna(subset=['video_fecha_dt']).copy()
    if len(dft) < 8:
        return

    dft = dft.set_index('video_fecha_dt').sort_index()
    weekly  = dft.resample('W').size().rename('posts')
    if len(weekly) < 4:
        return
    rolling = weekly.rolling(4, min_periods=1).mean()
    media_global = weekly.mean()

    fig, ax = plt.subplots(figsize=(16, 9))
    fig.patch.set_facecolor('#FFFFFF')
    ax.bar(weekly.index, weekly.values, color=color + '55',
           edgecolor='none', width=5, label='Vídeos/semana')
    ax.plot(rolling.index, rolling.values, color=color, linewidth=2.5,
            label='Media móvil 4 semanas')
    ax.axhline(media_global, color='#CCCCCC', linewidth=1, linestyle='--')
    ax.set_title(f"cadencia de publicación de {_get_account(file_id)}",
                 fontsize=14, color='#444444', pad=12)
    ax.text(0.02, 0.97,
            f"media global: {media_global:.1f} vídeos/semana",
            transform=ax.transAxes, fontsize=12, fontweight='bold',
            va='top', ha='left', color='#222222', bbox=_STAT_BOX)
    ax.set_ylabel("Vídeos publicados", fontsize=11)
    ax.tick_params(axis='x', rotation=45)
    ax.legend(fontsize=10, framealpha=0.9)
    apply_estilo_periodistico(ax)
    _add_watermark(ax)
    plt.tight_layout()
    save_plot(f"{file_id}_cadencia_publicacion.png")


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
            graf_cadencia_publicacion(df, file_id, color_text)   # 17

        except Exception as e:
            print(f"-> Error en gráficas temporales: {e}")

    # Gráficas de rendimiento (no requieren fechas)
    try:
        graf_distribucion_vistas(df, file_id, color_text)        # 10
        graf_scatter_vistas_engagement(df, file_id, color_text)  # 11
        graf_duracion_vs_vistas(df, file_id, color_text)         # 12
        graf_pareto_vistas(df, file_id, color_text)              # 14
        graf_engagement_desglose(df, file_id)                    # 15
    except Exception as e:
        print(f"-> Error en gráficas de rendimiento: {e}")

    print(f"\n¡PROCESO COMPLETADO! Revisa '{OUTPUT_FOLDER}/'")
    print(f"   Gráficas generadas: 9 originales + 6 nuevas de rendimiento")

if __name__ == "__main__":
    main()
