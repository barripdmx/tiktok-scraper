# -*- coding: utf-8 -*-
"""
Gráficas Multidimensionales — Análisis Avanzado de Sentimiento con IA
=====================================================================
6 visualizaciones para los análisis multidimensionales (sesgo, arquetipos,
pain points, intención, sarcasmo). Se incrustan como base64 PNG en el HTML.

Las columnas esperadas son:
  - sentiment: POS, NEG, NEU (o positivo, negativo, neutro)
  - bias: conservador, progresista, neutro, mixto, no_inferible
  - archetype: testigo_indignado, reactor_bajo_senal, etc.
  - pain_point: doble_rasero_fiscal, fatiga_corrupcion, etc.
  - intent: compra, info, difusion, castigo, ninguna
  - sarcasm: bool (True si ironía)
  - likes_count: int (opcional, para "volumen vs influencia")

Degradación elegante: si una columna no existe, la gráfica devuelve "".
"""

import io
import base64
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import cm
import seaborn as sns

# Paletas de colores consistentes
_BIAS_COLOR = {
    "Conservador": "#2C3E50",
    "Progresista": "#A93226",
    "Neutro": "#7F8C8D",
    "Mixto": "#8E44AD",
    "No inferible": "#BDC3C7"
}

_ARQ_COLOR = {
    "Testigo indignado": "#E74C3C",
    "Reactor de baja señal": "#9B59B6",
    "Fiscal del meme": "#3498DB",
    "Moralista punitivo": "#E67E22",
    "Amplificador": "#C0392B",
    "Redirector partidista": "#16A085",
    "Defensor escéptico": "#2980B9",
    "Igualador antisistema": "#D35400",
    "Expansor conspirativo": "#8E44AD",
    "Buscador de contexto": "#27AE60",
}

_SENTIMENT_COLOR = {"Positivo": "#1E8449", "Negativo": "#A93226", "Neutro": "#4A4A4A"}

def _normalize_sentiment(val):
    """Mapea sentimiento a formato legible (POS→Positivo, etc.)."""
    label_map = {"POS": "Positivo", "NEG": "Negativo", "NEU": "Neutro",
                 "positivo": "Positivo", "negativo": "Negativo", "neutro": "Neutro"}
    return label_map.get(str(val), str(val))

def _normalize_bias(val):
    """Mapea sesgo a formato legible."""
    pretty = {"conservador": "Conservador", "progresista": "Progresista",
              "neutro": "Neutro", "mixto": "Mixto", "no_inferible": "No inferible"}
    return pretty.get(str(val), str(val))

def _normalize_archetype(val):
    """Mapea arquetipo a formato legible."""
    pretty = {
        "testigo_indignado": "Testigo indignado",
        "reactor_bajo_senal": "Reactor de baja señal",
        "meme_fiscal": "Fiscal del meme",
        "moralista_punitivo": "Moralista punitivo",
        "amplificador": "Amplificador",
        "redirector_partidista": "Redirector partidista",
        "defensor_esceptico": "Defensor escéptico",
        "igualador_antisistema": "Igualador antisistema",
        "expansor_conspirativo": "Expansor conspirativo",
        "buscador_contexto": "Buscador de contexto",
        "otro": "Otro",
    }
    return pretty.get(str(val), str(val))

def _normalize_pain_point(val):
    """Mapea pain point a formato legible."""
    pretty = {
        "doble_rasero_fiscal": "Doble rasero fiscal",
        "fatiga_corrupcion": "Fatiga de corrupción",
        "judicializacion_selectiva": "Judicialización selectiva",
        "microeconomia": "Microeconomía",
        "perdida_terreno_cultural": "Pérdida terreno cultural",
        "sobreproduccion_falsedad": "Sobreproducción / falsedad",
        "otro": "Otro",
    }
    return pretty.get(str(val), str(val))

def _to_base64_png(fig):
    """Convierte una figura matplotlib a string base64 PNG y cierra la figura."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()


# ============================================================================
# GRÁFICA 1: Heatmap Sesgo × Sentimiento
# ============================================================================

def grafica_heatmap_sesgo_sentimiento(df: pd.DataFrame) -> str:
    """
    Heatmap que muestra la distribución de sentimiento (POS/NEG/NEU) dentro de
    cada bloque político (Conservador/Progresista/Neutro/Mixto).

    Devuelve: string base64 PNG, o "" si faltan columnas.
    """
    if 'bias' not in df.columns or 'sentiment' not in df.columns:
        return ""

    df_clean = df[['bias', 'sentiment']].dropna()
    if df_clean.empty:
        return ""

    # Normalizar etiquetas
    df_clean['bias_norm'] = df_clean['bias'].apply(_normalize_bias)
    df_clean['sent_norm'] = df_clean['sentiment'].apply(_normalize_sentiment)

    # Tabla cruzada: sesgo × sentimiento
    crosstab = pd.crosstab(df_clean['bias_norm'], df_clean['sent_norm'])

    # Reordenar columnas de sentimiento y filas de sesgo
    sent_order = [s for s in ["Positivo", "Neutro", "Negativo"] if s in crosstab.columns]
    bias_order = [b for b in ["Conservador", "Progresista", "Mixto", "Neutro", "No inferible"]
                  if b in crosstab.index]

    crosstab = crosstab.loc[bias_order, sent_order]

    # Heatmap
    fig, ax = plt.subplots(figsize=(8, 5))
    sns.heatmap(crosstab, annot=True, fmt="d", cmap="RdYlGn", ax=ax,
                cbar_kws={"label": "Nº comentarios"}, linewidths=0.5, linecolor="white")
    ax.set_title("Distribución de Sentimiento por Sesgo Político", fontsize=14, fontweight="bold", pad=20)
    ax.set_xlabel("Sentimiento", fontsize=12)
    ax.set_ylabel("Sesgo Político", fontsize=12)
    fig.patch.set_facecolor("white")

    return _to_base64_png(fig)


# ============================================================================
# GRÁFICA 2: Arquetipos de Comentarista (Barras con Top-N)
# ============================================================================

def grafica_arquetipos(df: pd.DataFrame, top: int = 8) -> str:
    """
    Barras horizontales ordenadas mostrando los top N arquetipos.

    Devuelve: string base64 PNG, o "" si falta columna.
    """
    if 'archetype' not in df.columns:
        return ""

    df_clean = df['archetype'].dropna()
    if df_clean.empty:
        return ""

    # Normalizar y contar
    arq_norm = df_clean.apply(_normalize_archetype)
    counts = arq_norm.value_counts().head(top)

    if counts.empty:
        return ""

    # Colores: mapear cada arquetipo a su color
    colores = [_ARQ_COLOR.get(name, "#999999") for name in counts.index]

    fig, ax = plt.subplots(figsize=(10, max(3, len(counts) * 0.4)))
    fig.patch.set_facecolor("white")

    bars = ax.barh(counts.index[::-1], counts.values[::-1], color=colores[::-1],
                   edgecolor="none", height=0.6)

    # Etiquetas con porcentaje
    total = counts.sum()
    for bar, val in zip(bars, counts.values[::-1]):
        pct = val / total * 100
        ax.text(bar.get_width() + 20, bar.get_y() + bar.get_height() / 2,
                f"{int(val):,} ({pct:.1f}%)", va="center", fontsize=9, color="#222222")

    ax.set_xlim(0, counts.max() * 1.35)
    ax.set_facecolor("white")
    for sp in ["top", "right", "left"]:
        ax.spines[sp].set_visible(False)
    ax.spines["bottom"].set_color("#CCCCCC")
    ax.grid(axis="x", color="#EBEBEB", linewidth=0.5)
    ax.set_axisbelow(True)
    ax.tick_params(colors="#555555", labelsize=9)
    ax.set_xlabel("Nº comentarios", fontsize=10)
    ax.set_title("Arquetipos de Comentarista (Top {})".format(min(top, len(counts))),
                 fontsize=12, fontweight="bold", pad=15)

    plt.tight_layout()
    return _to_base64_png(fig)


# ============================================================================
# GRÁFICA 3: Ranking de Pain Points
# ============================================================================

def grafica_pain_points(df: pd.DataFrame, top: int = 8) -> str:
    """
    Barras horizontales de los top pain points (frustraciones), excluyendo "ninguno".

    Devuelve: string base64 PNG, o "" si falta columna.
    """
    if 'pain_point' not in df.columns:
        return ""

    df_clean = df['pain_point'].dropna()
    if df_clean.empty:
        return ""

    # Normalizar y contar, excluyendo "ninguno"
    pp_norm = df_clean.apply(_normalize_pain_point)
    pp_norm = pp_norm[pp_norm != "ninguno"]
    counts = pp_norm.value_counts().head(top)

    if counts.empty:
        return ""

    fig, ax = plt.subplots(figsize=(10, max(3, len(counts) * 0.4)))
    fig.patch.set_facecolor("white")

    # Paleta de rojos para pain points (son negativos)
    colores = plt.cm.Reds(np.linspace(0.4, 0.8, len(counts)))

    bars = ax.barh(counts.index[::-1], counts.values[::-1], color=colores[::-1],
                   edgecolor="none", height=0.6)

    # Etiquetas
    total = counts.sum()
    for bar, val in zip(bars, counts.values[::-1]):
        pct = val / total * 100
        ax.text(bar.get_width() + 20, bar.get_y() + bar.get_height() / 2,
                f"{int(val):,} ({pct:.1f}%)", va="center", fontsize=9, color="#222222")

    ax.set_xlim(0, counts.max() * 1.35)
    ax.set_facecolor("white")
    for sp in ["top", "right", "left"]:
        ax.spines[sp].set_visible(False)
    ax.spines["bottom"].set_color("#CCCCCC")
    ax.grid(axis="x", color="#EBEBEB", linewidth=0.5)
    ax.set_axisbelow(True)
    ax.tick_params(colors="#555555", labelsize=9)
    ax.set_xlabel("Nº comentarios", fontsize=10)
    ax.set_title("Puntos de Dolor (Pain Points) - Top {}".format(min(top, len(counts))),
                 fontsize=12, fontweight="bold", pad=15)

    plt.tight_layout()
    return _to_base64_png(fig)


# ============================================================================
# GRÁFICA 4: Heatmap Sesgo × Pain Point
# ============================================================================

def grafica_heatmap_sesgo_pain_point(df: pd.DataFrame) -> str:
    """
    Heatmap que muestra qué pain points afectan a cada bloque político.

    Devuelve: string base64 PNG, o "" si faltan columnas.
    """
    if 'bias' not in df.columns or 'pain_point' not in df.columns:
        return ""

    df_clean = df[['bias', 'pain_point']].dropna()
    if df_clean.empty:
        return ""

    # Excluir "ninguno"
    df_clean = df_clean[df_clean['pain_point'] != 'ninguno']
    if df_clean.empty:
        return ""

    # Normalizar
    df_clean['bias_norm'] = df_clean['bias'].apply(_normalize_bias)
    df_clean['pp_norm'] = df_clean['pain_point'].apply(_normalize_pain_point)

    # Tabla cruzada
    crosstab = pd.crosstab(df_clean['bias_norm'], df_clean['pp_norm'])

    # Reordenar
    bias_order = [b for b in ["Conservador", "Progresista", "Mixto", "Neutro", "No inferible"]
                  if b in crosstab.index]
    crosstab = crosstab.loc[bias_order, :]

    # Heatmap
    fig, ax = plt.subplots(figsize=(12, 5))
    sns.heatmap(crosstab, annot=True, fmt="d", cmap="YlOrRd", ax=ax,
                cbar_kws={"label": "Nº comentarios"}, linewidths=0.5, linecolor="white")
    ax.set_title("Pain Points por Sesgo Político", fontsize=14, fontweight="bold", pad=20)
    ax.set_xlabel("Pain Point", fontsize=11)
    ax.set_ylabel("Sesgo Político", fontsize=11)
    fig.patch.set_facecolor("white")
    plt.xticks(rotation=45, ha="right")

    return _to_base64_png(fig)


# ============================================================================
# GRÁFICA 5: Volumen vs Influencia (Scatter)
# ============================================================================

def grafica_volumen_vs_influencia(df: pd.DataFrame) -> str:
    """
    Scatter plot: eje X = nº comentarios por bias, eje Y = suma de likes.
    Cada burbuja = bloque político, tamaño = varianza de likes.

    Devuelve: string base64 PNG, o "" si faltan columnas.
    """
    if 'bias' not in df.columns:
        return ""

    # Agrupar por sesgo: contar comentarios y sumar likes
    if 'likes_count' not in df.columns:
        # Sin likes_count, usar solo nº de comentarios por sesgo
        df_clean = df[['bias']].dropna()
        if df_clean.empty:
            return ""

        df_clean['bias_norm'] = df_clean['bias'].apply(_normalize_bias)
        agg = df_clean.groupby('bias_norm').size().reset_index(name='comentarios')
        agg['influencia'] = agg['comentarios']  # Proxy: mismo volumen
        agg['varianza'] = agg['comentarios'] * 10  # Para tamaño de burbuja
    else:
        df_clean = df[['bias', 'likes_count']].dropna()
        if df_clean.empty:
            return ""

        df_clean['bias_norm'] = df_clean['bias'].apply(_normalize_bias)
        agg = df_clean.groupby('bias_norm').agg({
            'likes_count': ['sum', 'var', 'count']
        }).reset_index()
        agg.columns = ['bias_norm', 'influencia', 'varianza', 'comentarios']
        agg['varianza'] = agg['varianza'].fillna(0) + 1  # Evitar tamaño cero

    if agg.empty:
        return ""

    fig, ax = plt.subplots(figsize=(10, 6))
    fig.patch.set_facecolor("white")

    # Scatter plot
    for idx, row in agg.iterrows():
        bias = row['bias_norm']
        color = _BIAS_COLOR.get(bias, "#999999")
        ax.scatter(row['comentarios'], row['influencia'],
                  s=max(100, row['varianza'] * 2), alpha=0.7, color=color,
                  edgecolor="black", linewidth=1.5, label=bias)
        # Anotación con el nombre del sesgo
        ax.annotate(bias, (row['comentarios'], row['influencia']),
                   fontsize=9, ha="center", va="center", fontweight="bold")

    ax.set_xlabel("Nº de comentarios", fontsize=11)
    ax.set_ylabel("Suma de likes", fontsize=11)
    ax.set_title("Volumen vs Influencia por Sesgo Político",
                fontsize=12, fontweight="bold", pad=15)
    ax.grid(True, alpha=0.3, linestyle="--", color="#CCCCCC")
    ax.set_facecolor("#FAFAFA")

    # Escala logarítmica si hay mucha varianza
    if agg['comentarios'].max() / agg['comentarios'].min() > 100:
        ax.set_xscale("log")
    if agg['influencia'].max() / agg['influencia'].min() > 100:
        ax.set_yscale("log")

    plt.tight_layout()
    return _to_base64_png(fig)


# ============================================================================
# GRÁFICA 6: Sarcasmo dentro de NEG (Dona partida)
# ============================================================================

def grafica_sarcasmo_en_negativo(df: pd.DataFrame) -> str:
    """
    Dona partida mostrando dentro de comentarios NEG:
      - Sarcasmo/Ironía (sarcasm=true)
      - NEG Legítimo (sarcasm=false o NaN)

    Devuelve: string base64 PNG, o "" si faltan columnas.
    """
    if 'sentiment' not in df.columns:
        return ""

    # Filtrar solo NEG
    df_neg = df[df['sentiment'].isin(['NEG', 'negativo'])].copy()
    if df_neg.empty:
        return ""

    # Contar sarcasmo
    if 'sarcasm' in df_neg.columns:
        n_sarcasm = df_neg['sarcasm'].fillna(False).astype(bool).sum()
        n_legit = len(df_neg) - n_sarcasm
    else:
        n_legit = len(df_neg)
        n_sarcasm = 0

    if n_legit == 0 and n_sarcasm == 0:
        return ""

    # Dona
    fig, ax = plt.subplots(figsize=(8, 6))
    fig.patch.set_facecolor("white")

    labels = []
    sizes = []
    colors = []

    if n_legit > 0:
        labels.append(f"NEG Legítimo ({n_legit:,})")
        sizes.append(n_legit)
        colors.append("#A93226")  # Rojo oscuro

    if n_sarcasm > 0:
        labels.append(f"Sarcasmo/Ironía 🤨 ({n_sarcasm:,})")
        sizes.append(n_sarcasm)
        colors.append("#E74C3C")  # Rojo claro (irónico)

    wedges, texts, autotexts = ax.pie(sizes, labels=labels, autopct="%1.1f%%",
                                       colors=colors, startangle=90,
                                       textprops={"fontsize": 11})

    # Centro blanco (estilo dona)
    centre_circle = plt.Circle((0, 0), 0.70, fc="white", edgecolor="white", linewidth=0)
    ax.add_artist(centre_circle)

    # Mejorar textos
    for autotext in autotexts:
        autotext.set_color("white")
        autotext.set_fontweight("bold")

    ax.set_title(f"Sarcasmo dentro de Comentarios Negativos\n({len(df_neg):,} NEG totales)",
                fontsize=12, fontweight="bold", pad=20)

    plt.tight_layout()
    return _to_base64_png(fig)


# ============================================================================
# GRÁFICA 7: Distribución de Intención
# ============================================================================

def grafica_intencion(df: pd.DataFrame) -> str:
    """
    Barras horizontales con la distribución de intención de los comentaristas
    (compra, info, difusion, castigo, ninguna).
    """
    if 'intent' not in df.columns:
        return ""

    df_clean = df['intent'].dropna()
    df_clean = df_clean[df_clean.str.strip() != ""]
    if df_clean.empty:
        return ""

    pretty = {
        "compra": "Compra / Consumo",
        "info": "Buscar información",
        "difusion": "Difusión / Amplificar",
        "castigo": "Castigar / Atacar",
        "ninguna": "Sin intención clara",
    }
    counts = df_clean.apply(lambda x: pretty.get(str(x).strip(), str(x))).value_counts()

    colores = ["#1F618D", "#CA6F1E", "#7D3C98", "#A93226", "#999999"]

    fig, ax = plt.subplots(figsize=(10, max(3, len(counts) * 0.55)))
    fig.patch.set_facecolor("white")

    bars = ax.barh(counts.index[::-1], counts.values[::-1],
                   color=colores[:len(counts)][::-1], edgecolor="none", height=0.6)

    total = counts.sum()
    for bar, val in zip(bars, counts.values[::-1]):
        pct = val / total * 100
        ax.text(bar.get_width() + total * 0.005,
                bar.get_y() + bar.get_height() / 2,
                f"{int(val):,}  ({pct:.1f}%)", va="center", fontsize=9, color="#222222")

    ax.set_xlim(0, counts.max() * 1.35)
    ax.set_facecolor("white")
    for sp in ["top", "right", "left"]:
        ax.spines[sp].set_visible(False)
    ax.spines["bottom"].set_color("#CCCCCC")
    ax.grid(axis="x", color="#EBEBEB", linewidth=0.5)
    ax.set_axisbelow(True)
    ax.tick_params(colors="#555555", labelsize=10)
    ax.set_xlabel("Nº comentarios", fontsize=10)
    ax.set_title("¿Qué quieren hacer los comentaristas? — Distribución de Intención",
                 fontsize=12, fontweight="bold", pad=15)

    plt.tight_layout()
    return _to_base64_png(fig)


# ============================================================================
# GRÁFICA 8: Evolución temporal del sesgo político
# ============================================================================

def grafica_evolucion_sesgo_temporal(df: pd.DataFrame) -> str:
    """
    Líneas semanales con el % de cada sesgo político a lo largo del tiempo.
    Requiere columna de fecha (created_at, date, fecha o similar).
    """
    if 'bias' not in df.columns:
        return ""

    # Detectar columna de fecha
    col_fecha = None
    for c in ['created_at', 'date', 'fecha', 'timestamp', 'publish_time']:
        if c in df.columns:
            col_fecha = c
            break
    if col_fecha is None:
        return ""

    df_t = df[[col_fecha, 'bias']].dropna().copy()
    try:
        df_t[col_fecha] = pd.to_datetime(df_t[col_fecha], unit='s', errors='coerce')
        if df_t[col_fecha].isna().all():
            df_t[col_fecha] = pd.to_datetime(df[col_fecha], errors='coerce')
    except Exception:
        df_t[col_fecha] = pd.to_datetime(df_t[col_fecha], errors='coerce')

    df_t = df_t.dropna(subset=[col_fecha])
    if df_t.empty or df_t[col_fecha].nunique() < 3:
        return ""

    df_t['bias_norm'] = df_t['bias'].apply(_normalize_bias)
    df_t['semana'] = df_t[col_fecha].dt.to_period('W').dt.start_time

    pivot = (df_t.groupby(['semana', 'bias_norm'])
             .size().unstack(fill_value=0))
    pivot_pct = pivot.div(pivot.sum(axis=1), axis=0) * 100

    # Solo mostrar sesgos con presencia real (>1% en alguna semana)
    cols_validos = pivot_pct.columns[(pivot_pct > 1).any()]
    if cols_validos.empty:
        return ""
    pivot_pct = pivot_pct[cols_validos]

    fig, ax = plt.subplots(figsize=(14, 6))
    fig.patch.set_facecolor("white")

    for col in pivot_pct.columns:
        color = _BIAS_COLOR.get(col, "#999999")
        ax.plot(pivot_pct.index, pivot_pct[col], marker="o", markersize=4,
                linewidth=2, color=color, label=col)

    ax.set_facecolor("white")
    for sp in ["top", "right"]:
        ax.spines[sp].set_visible(False)
    ax.spines["left"].set_color("#CCCCCC")
    ax.spines["bottom"].set_color("#CCCCCC")
    ax.grid(axis="y", color="#EBEBEB", linewidth=0.5)
    ax.set_axisbelow(True)
    ax.tick_params(colors="#555555", labelsize=9)
    ax.set_ylabel("% de comentarios", fontsize=10)
    ax.set_xlabel("")
    ax.legend(title="Sesgo", fontsize=9, title_fontsize=9, framealpha=0.7)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.0f}%"))
    ax.set_title("Evolución Semanal del Sesgo Político en Comentarios",
                 fontsize=12, fontweight="bold", pad=15)

    plt.xticks(rotation=30, ha="right")
    plt.tight_layout()
    return _to_base64_png(fig)


# ============================================================================
# GRÁFICA 9: Sentimiento por vídeo (Top 10 vídeos más negativos)
# ============================================================================

def grafica_sentimiento_por_video(df: pd.DataFrame, top: int = 10) -> str:
    """
    Barras apiladas horizontales con % POS/NEU/NEG por vídeo.
    Ordenadas por % NEG descendente. Muestra los top N vídeos con más comentarios.
    """
    if 'sentiment' not in df.columns:
        return ""

    col_video = None
    for c in ['video_id', 'videoId', 'id_video']:
        if c in df.columns:
            col_video = c
            break
    if col_video is None:
        return ""

    df_v = df[[col_video, 'sentiment']].dropna().copy()
    df_v['sent_norm'] = df_v['sentiment'].apply(_normalize_sentiment)

    # Solo vídeos con mínimo 10 comentarios
    conteo = df_v[col_video].value_counts()
    videos_validos = conteo[conteo >= 10].index
    df_v = df_v[df_v[col_video].isin(videos_validos)]

    if df_v.empty:
        return ""

    pivot = (df_v.groupby([col_video, 'sent_norm'])
             .size().unstack(fill_value=0))

    # Calcular % y ordenar por % NEG
    pivot_pct = pivot.div(pivot.sum(axis=1), axis=0) * 100
    if 'Negativo' not in pivot_pct.columns:
        return ""

    pivot_pct = pivot_pct.sort_values('Negativo', ascending=False).head(top)

    # Etiqueta: ID acortado
    pivot_pct.index = [str(i)[-6:] for i in pivot_pct.index]

    cols = [c for c in ['Negativo', 'Neutro', 'Positivo'] if c in pivot_pct.columns]
    colores_map = {'Positivo': '#1E8449', 'Neutro': '#4A4A4A', 'Negativo': '#A93226'}
    colores = [colores_map[c] for c in cols]

    fig, ax = plt.subplots(figsize=(12, max(4, len(pivot_pct) * 0.55)))
    fig.patch.set_facecolor("white")

    left = np.zeros(len(pivot_pct))
    for col, color in zip(cols, colores):
        vals = pivot_pct[col].values
        bars = ax.barh(pivot_pct.index, vals, left=left, color=color,
                       label=col, edgecolor="white", linewidth=0.5, height=0.6)
        for bar, val, l in zip(bars, vals, left):
            if val > 8:
                ax.text(l + val / 2, bar.get_y() + bar.get_height() / 2,
                        f"{val:.0f}%", ha="center", va="center",
                        fontsize=8, color="white", fontweight="bold")
        left += vals

    ax.set_xlim(0, 100)
    ax.set_facecolor("white")
    for sp in ["top", "right", "left"]:
        ax.spines[sp].set_visible(False)
    ax.spines["bottom"].set_color("#CCCCCC")
    ax.tick_params(colors="#555555", labelsize=9)
    ax.set_xlabel("% de comentarios", fontsize=10)
    ax.set_ylabel(f"ID de vídeo (últimos 6 dígitos)", fontsize=9)
    ax.legend(loc="lower right", fontsize=9, framealpha=0.7)
    ax.set_title(f"Top {top} Vídeos con Mayor % de Comentarios Negativos",
                 fontsize=12, fontweight="bold", pad=15)

    plt.tight_layout()
    return _to_base64_png(fig)


# ============================================================================
# GRÁFICA 10: Likes por sentimiento
# ============================================================================

def grafica_likes_por_sentimiento(df: pd.DataFrame) -> str:
    """
    Diagrama de caja (boxplot) o barras de promedio de likes por sentimiento.
    Responde: ¿los comentarios negativos reciben más likes?
    """
    if 'sentiment' not in df.columns or 'likes_count' not in df.columns:
        return ""

    df_l = df[['sentiment', 'likes_count']].dropna().copy()
    df_l = df_l[df_l['likes_count'] >= 0]
    df_l['sent_norm'] = df_l['sentiment'].apply(_normalize_sentiment)

    if df_l.empty:
        return ""

    orden = [s for s in ['Negativo', 'Neutro', 'Positivo'] if s in df_l['sent_norm'].unique()]
    colores = {'Positivo': '#1E8449', 'Neutro': '#4A4A4A', 'Negativo': '#A93226'}

    # Agrupar: mediana + media
    stats = (df_l.groupby('sent_norm')['likes_count']
             .agg(['median', 'mean', 'count'])
             .loc[orden])

    fig, ax = plt.subplots(figsize=(9, 5))
    fig.patch.set_facecolor("white")

    x = np.arange(len(orden))
    bars = ax.bar(x, stats['median'], color=[colores[s] for s in orden],
                  edgecolor="none", width=0.5)

    # Punto de media
    ax.scatter(x, stats['mean'], color='black', zorder=5, s=60,
               marker='D', label='Media')

    # Etiquetas
    for i, (sent, row) in enumerate(stats.iterrows()):
        ax.text(i, row['median'] + stats['median'].max() * 0.02,
                f"Mediana: {row['median']:.0f}\nMedia: {row['mean']:.1f}",
                ha='center', va='bottom', fontsize=9, color='#222222')

    ax.set_xticks(x)
    ax.set_xticklabels(orden, fontsize=11)
    ax.set_facecolor("white")
    for sp in ["top", "right"]:
        ax.spines[sp].set_visible(False)
    ax.spines["left"].set_color("#CCCCCC")
    ax.spines["bottom"].set_color("#CCCCCC")
    ax.grid(axis="y", color="#EBEBEB", linewidth=0.5)
    ax.set_axisbelow(True)
    ax.tick_params(colors="#555555")
    ax.set_ylabel("Likes por comentario", fontsize=10)
    ax.legend(fontsize=9)
    ax.set_title("¿Qué sentimiento recibe más likes? — Mediana y Media de Likes",
                 fontsize=12, fontweight="bold", pad=15)

    plt.tight_layout()
    return _to_base64_png(fig)


# ============================================================================
# GRÁFICA 11: Heatmap Intención × Sesgo
# ============================================================================

def grafica_heatmap_intencion_sesgo(df: pd.DataFrame) -> str:
    """
    Heatmap que cruza intención con sesgo político.
    ¿Qué bloque quiere 'castigar' vs 'difundir'?
    """
    if 'intent' not in df.columns or 'bias' not in df.columns:
        return ""

    df_c = df[['intent', 'bias']].dropna().copy()
    df_c = df_c[df_c['intent'].str.strip() != ""]
    if df_c.empty:
        return ""

    intent_pretty = {
        "compra": "Compra", "info": "Información",
        "difusion": "Difusión", "castigo": "Castigo", "ninguna": "Sin intención",
    }
    df_c['intent_norm'] = df_c['intent'].apply(lambda x: intent_pretty.get(str(x).strip(), str(x)))
    df_c['bias_norm'] = df_c['bias'].apply(_normalize_bias)

    crosstab = pd.crosstab(df_c['bias_norm'], df_c['intent_norm'])

    bias_order = [b for b in ["Conservador", "Progresista", "Mixto", "Neutro", "No inferible"]
                  if b in crosstab.index]
    crosstab = crosstab.loc[bias_order, :]

    fig, ax = plt.subplots(figsize=(12, 5))
    sns.heatmap(crosstab, annot=True, fmt="d", cmap="Blues", ax=ax,
                cbar_kws={"label": "Nº comentarios"}, linewidths=0.5, linecolor="white")
    ax.set_title("Intención por Sesgo Político — ¿Quién quiere castigar vs difundir?",
                 fontsize=13, fontweight="bold", pad=20)
    ax.set_xlabel("Intención", fontsize=11)
    ax.set_ylabel("Sesgo Político", fontsize=11)
    fig.patch.set_facecolor("white")
    plt.xticks(rotation=30, ha="right")
    plt.tight_layout()
    return _to_base64_png(fig)


# ============================================================================
# GRÁFICA 12: Top comentaristas por arquetipo
# ============================================================================

def grafica_top_comentaristas_por_arquetipo(df: pd.DataFrame, top_arq: int = 3, top_users: int = 5) -> str:
    """
    Para los top_arq arquetipos más frecuentes, muestra los top_users
    comentaristas más activos dentro de cada arquetipo.
    Útil para identificar cuentas bot o coordinadas.
    """
    if 'archetype' not in df.columns:
        return ""

    col_autor = None
    for c in ['author_id', 'author', 'username', 'user_id', 'uniqueId']:
        if c in df.columns:
            col_autor = c
            break
    if col_autor is None:
        return ""

    df_a = df[['archetype', col_autor]].dropna().copy()
    df_a['arq_norm'] = df_a['archetype'].apply(_normalize_archetype)

    # Top arquetipos por volumen
    top_arquetipos = df_a['arq_norm'].value_counts().head(top_arq).index.tolist()
    if not top_arquetipos:
        return ""

    fig, axes = plt.subplots(1, len(top_arquetipos),
                              figsize=(6 * len(top_arquetipos), 5), sharey=False)
    if len(top_arquetipos) == 1:
        axes = [axes]
    fig.patch.set_facecolor("white")

    for ax, arq in zip(axes, top_arquetipos):
        sub = df_a[df_a['arq_norm'] == arq]
        top_u = sub[col_autor].value_counts().head(top_users)

        if top_u.empty:
            ax.axis("off")
            continue

        color = _ARQ_COLOR.get(arq, "#1F618D")
        bars = ax.barh(top_u.index[::-1], top_u.values[::-1],
                       color=color, alpha=0.85, edgecolor="none", height=0.6)

        for bar, val in zip(bars, top_u.values[::-1]):
            ax.text(bar.get_width() + top_u.max() * 0.02,
                    bar.get_y() + bar.get_height() / 2,
                    str(int(val)), va="center", fontsize=9)

        ax.set_facecolor("white")
        for sp in ["top", "right", "left"]:
            ax.spines[sp].set_visible(False)
        ax.spines["bottom"].set_color("#CCCCCC")
        ax.grid(axis="x", color="#EBEBEB", linewidth=0.5)
        ax.set_axisbelow(True)
        ax.tick_params(colors="#555555", labelsize=8)
        ax.set_title(arq, fontsize=10, fontweight="bold", color=color, pad=10)
        ax.set_xlabel("Nº comentarios", fontsize=9)
        ax.set_xlim(0, top_u.max() * 1.25)

    fig.suptitle(f"Top {top_users} Comentaristas por Arquetipo (Top {top_arq} arquetipos)",
                 fontsize=12, fontweight="bold", y=1.02)
    plt.tight_layout()
    return _to_base64_png(fig)


# ============================================================================
# GRÁFICA 13: Ratio de sarcasmo por sesgo político
# ============================================================================

def grafica_sarcasmo_por_sesgo(df: pd.DataFrame) -> str:
    """
    Barras con el % de sarcasmo/ironía dentro de cada bloque político.
    ¿Qué bloque usa más ironía para comentar?
    """
    if 'sarcasm' not in df.columns or 'bias' not in df.columns:
        return ""

    df_s = df[['sarcasm', 'bias']].dropna().copy()
    if df_s.empty:
        return ""

    df_s['bias_norm'] = df_s['bias'].apply(_normalize_bias)
    df_s['sarcasm_bool'] = df_s['sarcasm'].fillna(False).astype(bool)

    stats = df_s.groupby('bias_norm')['sarcasm_bool'].agg(['sum', 'count'])
    stats['pct'] = stats['sum'] / stats['count'] * 100
    stats = stats.sort_values('pct', ascending=True)

    if stats.empty:
        return ""

    fig, ax = plt.subplots(figsize=(9, max(3, len(stats) * 0.6)))
    fig.patch.set_facecolor("white")

    colores = [_BIAS_COLOR.get(idx, "#999999") for idx in stats.index]
    bars = ax.barh(stats.index, stats['pct'], color=colores,
                   edgecolor="none", height=0.55)

    for bar, (idx, row) in zip(bars, stats.iterrows()):
        ax.text(bar.get_width() + 0.3,
                bar.get_y() + bar.get_height() / 2,
                f"{row['pct']:.1f}%  ({int(row['sum']):,} de {int(row['count']):,})",
                va="center", fontsize=9, color="#222222")

    ax.set_xlim(0, stats['pct'].max() * 1.5)
    ax.set_facecolor("white")
    for sp in ["top", "right", "left"]:
        ax.spines[sp].set_visible(False)
    ax.spines["bottom"].set_color("#CCCCCC")
    ax.grid(axis="x", color="#EBEBEB", linewidth=0.5)
    ax.set_axisbelow(True)
    ax.tick_params(colors="#555555", labelsize=10)
    ax.set_xlabel("% comentarios con sarcasmo/ironía", fontsize=10)
    ax.set_title("¿Qué bloque político usa más sarcasmo?",
                 fontsize=12, fontweight="bold", pad=15)

    plt.tight_layout()
    return _to_base64_png(fig)


# ============================================================================
# GRÁFICA 14: Evolución de arquetipos en el tiempo
# ============================================================================

def grafica_evolucion_arquetipos_temporal(df: pd.DataFrame, top: int = 5) -> str:
    """
    Área apilada mensual con los top N arquetipos.
    ¿Cambia el perfil del comentarista según el momento?
    """
    if 'archetype' not in df.columns:
        return ""

    col_fecha = None
    for c in ['created_at', 'date', 'fecha', 'timestamp', 'publish_time']:
        if c in df.columns:
            col_fecha = c
            break
    if col_fecha is None:
        return ""

    df_t = df[[col_fecha, 'archetype']].dropna().copy()
    try:
        df_t[col_fecha] = pd.to_datetime(df_t[col_fecha], unit='s', errors='coerce')
        if df_t[col_fecha].isna().all():
            df_t[col_fecha] = pd.to_datetime(df[col_fecha], errors='coerce')
    except Exception:
        df_t[col_fecha] = pd.to_datetime(df_t[col_fecha], errors='coerce')

    df_t = df_t.dropna(subset=[col_fecha])
    if df_t.empty or df_t[col_fecha].nunique() < 3:
        return ""

    df_t['arq_norm'] = df_t['archetype'].apply(_normalize_archetype)
    df_t['mes'] = df_t[col_fecha].dt.to_period('M').dt.start_time

    # Top N arquetipos por volumen total
    top_arqs = df_t['arq_norm'].value_counts().head(top).index.tolist()
    df_t_top = df_t[df_t['arq_norm'].isin(top_arqs)]

    pivot = (df_t_top.groupby(['mes', 'arq_norm'])
             .size().unstack(fill_value=0)[top_arqs])

    if pivot.empty or len(pivot) < 2:
        return ""

    pivot_pct = pivot.div(pivot.sum(axis=1), axis=0) * 100

    fig, ax = plt.subplots(figsize=(14, 6))
    fig.patch.set_facecolor("white")

    colores = [_ARQ_COLOR.get(a, "#999999") for a in top_arqs]
    ax.stackplot(pivot_pct.index, pivot_pct.T.values,
                 labels=top_arqs, colors=colores, alpha=0.8)

    ax.set_facecolor("white")
    for sp in ["top", "right"]:
        ax.spines[sp].set_visible(False)
    ax.spines["left"].set_color("#CCCCCC")
    ax.spines["bottom"].set_color("#CCCCCC")
    ax.tick_params(colors="#555555", labelsize=9)
    ax.set_ylabel("% de comentarios", fontsize=10)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.0f}%"))
    ax.legend(loc="upper left", fontsize=8, title="Arquetipo",
              title_fontsize=8, framealpha=0.7, bbox_to_anchor=(1.01, 1))
    ax.set_title(f"Evolución Mensual de Arquetipos (Top {top})",
                 fontsize=12, fontweight="bold", pad=15)

    plt.xticks(rotation=30, ha="right")
    plt.tight_layout()
    return _to_base64_png(fig)


# ============================================================================
# Función auxiliar: generar todas las gráficas (para uso como librería)
# ============================================================================

def generar_todas_graficas(df: pd.DataFrame) -> dict:
    """
    Genera las 6 gráficas multidimensionales y las devuelve en un dict.

    Devuelve:
    {
        "heatmap_sesgo_sentimiento": "base64 PNG o ''",
        "arquetipos": "base64 PNG o ''",
        "pain_points": "base64 PNG o ''",
        "heatmap_sesgo_pain_point": "base64 PNG o ''",
        "volumen_vs_influencia": "base64 PNG o ''",
        "sarcasmo_en_negativo": "base64 PNG o ''",
    }
    """
    return {
        "heatmap_sesgo_sentimiento":        grafica_heatmap_sesgo_sentimiento(df),
        "arquetipos":                        grafica_arquetipos(df),
        "pain_points":                       grafica_pain_points(df),
        "heatmap_sesgo_pain_point":          grafica_heatmap_sesgo_pain_point(df),
        "volumen_vs_influencia":             grafica_volumen_vs_influencia(df),
        "sarcasmo_en_negativo":              grafica_sarcasmo_en_negativo(df),
        "intencion":                         grafica_intencion(df),
        "evolucion_sesgo_temporal":          grafica_evolucion_sesgo_temporal(df),
        "sentimiento_por_video":             grafica_sentimiento_por_video(df),
        "likes_por_sentimiento":             grafica_likes_por_sentimiento(df),
        "heatmap_intencion_sesgo":           grafica_heatmap_intencion_sesgo(df),
        "top_comentaristas_por_arquetipo":   grafica_top_comentaristas_por_arquetipo(df),
        "sarcasmo_por_sesgo":                grafica_sarcasmo_por_sesgo(df),
        "evolucion_arquetipos_temporal":     grafica_evolucion_arquetipos_temporal(df),
    }


# ============================================================================
# Ejecución standalone (llamado desde el menú o la terminal)
# ============================================================================

def main():
    import os
    import sys
    import tkinter as tk
    from tkinter import filedialog, messagebox

    # ── Selector de CSV ──────────────────────────────────────────────────────
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    csv_path = filedialog.askopenfilename(
        title="Selecciona el CSV con análisis de sentimiento (Mistral o Groq)",
        filetypes=[
            ("CSV con sentimiento", "*con_sentimiento*.csv"),
            ("Todos los CSV", "*.csv"),
        ],
    )
    root.destroy()

    if not csv_path:
        print("Operación cancelada.")
        return

    # ── Cargar datos ─────────────────────────────────────────────────────────
    print(f"\n  Cargando: {os.path.basename(csv_path)}")
    try:
        df = pd.read_csv(csv_path, low_memory=False)
    except Exception as e:
        print(f"  ❌ Error al leer CSV: {e}")
        return

    print(f"  Filas   : {len(df):,}")

    # Verificar que tiene columnas de análisis multidimensional
    columnas_multi = {'bias', 'archetype', 'pain_point', 'intent', 'sarcasm'}
    encontradas = columnas_multi & set(df.columns)
    if not encontradas:
        root2 = tk.Tk()
        root2.withdraw()
        messagebox.showerror(
            "CSV no válido",
            "Este CSV no contiene columnas de análisis multidimensional.\n\n"
            "Necesita columnas como: bias, archetype, pain_point, intent, sarcasm.\n\n"
            "Ejecuta primero el análisis de sentimiento con Mistral o Groq."
        )
        root2.destroy()
        return

    # ── Carpeta de salida ────────────────────────────────────────────────────
    # Carpeta de salida — fuente única de verdad para las rutas del proyecto
    _BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    sys.path.insert(0, _BASE)
    from config.rutas import derivar_proyecto, dir_multidimensionales
    carpeta_salida = dir_multidimensionales(derivar_proyecto(csv_path))

    print(f"\n  Generando gráficas en: {carpeta_salida}\n")

    # ── Generar y guardar ────────────────────────────────────────────────────
    GRAFICAS = [
        ("heatmap_sesgo_sentimiento",       grafica_heatmap_sesgo_sentimiento,       "01_heatmap_sesgo_sentimiento.png"),
        ("arquetipos",                      grafica_arquetipos,                      "02_arquetipos.png"),
        ("pain_points",                     grafica_pain_points,                     "03_pain_points.png"),
        ("heatmap_sesgo_pain_point",        grafica_heatmap_sesgo_pain_point,        "04_heatmap_sesgo_pain_point.png"),
        ("volumen_vs_influencia",           grafica_volumen_vs_influencia,           "05_volumen_vs_influencia.png"),
        ("sarcasmo_en_negativo",            grafica_sarcasmo_en_negativo,            "06_sarcasmo_en_negativo.png"),
        ("intencion",                       grafica_intencion,                       "07_intencion.png"),
        ("evolucion_sesgo_temporal",        grafica_evolucion_sesgo_temporal,        "08_evolucion_sesgo_temporal.png"),
        ("sentimiento_por_video",           grafica_sentimiento_por_video,           "09_sentimiento_por_video.png"),
        ("likes_por_sentimiento",           grafica_likes_por_sentimiento,           "10_likes_por_sentimiento.png"),
        ("heatmap_intencion_sesgo",         grafica_heatmap_intencion_sesgo,         "11_heatmap_intencion_sesgo.png"),
        ("top_comentaristas_por_arquetipo", grafica_top_comentaristas_por_arquetipo, "12_top_comentaristas_por_arquetipo.png"),
        ("sarcasmo_por_sesgo",              grafica_sarcasmo_por_sesgo,              "13_sarcasmo_por_sesgo.png"),
        ("evolucion_arquetipos_temporal",   grafica_evolucion_arquetipos_temporal,   "14_evolucion_arquetipos_temporal.png"),
    ]

    generadas = []
    omitidas  = []

    for nombre, func, filename in GRAFICAS:
        try:
            b64 = func(df)
            if not b64:
                omitidas.append(nombre)
                print(f"  ⚠️  {filename} — omitida (columnas no disponibles)")
                continue

            ruta = os.path.join(carpeta_salida, filename)
            import base64 as _b64
            with open(ruta, "wb") as f:
                f.write(_b64.b64decode(b64))

            generadas.append(ruta)
            print(f"  ✅ {filename}")

        except Exception as e:
            omitidas.append(nombre)
            print(f"  ❌ {filename} — error: {e}")

    # ── Resumen final ────────────────────────────────────────────────────────
    print(f"\n  ── Resumen ──────────────────────────────")
    print(f"  Generadas : {len(generadas)}/{len(GRAFICAS)}")
    if omitidas:
        print(f"  Omitidas  : {', '.join(omitidas)}")
    print(f"  Carpeta   : {carpeta_salida}\n")

    if generadas:
        root3 = tk.Tk()
        root3.withdraw()
        abrir = messagebox.askyesno(
            "✅ Gráficas generadas",
            f"Se han generado {len(generadas)} gráfica(s) en:\n\n{carpeta_salida}\n\n"
            "¿Abrir la carpeta?"
        )
        root3.destroy()
        if abrir:
            if sys.platform == "win32":
                os.startfile(carpeta_salida)
            else:
                import subprocess
                subprocess.run(["open" if sys.platform == "darwin" else "xdg-open", carpeta_salida])
    else:
        root4 = tk.Tk()
        root4.withdraw()
        messagebox.showwarning(
            "Sin gráficas",
            "No se generó ninguna gráfica.\n"
            "Comprueba que el CSV tiene columnas: bias, archetype, pain_point, sentiment."
        )
        root4.destroy()


if __name__ == "__main__":
    main()
