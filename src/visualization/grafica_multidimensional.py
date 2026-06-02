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
# Función auxiliar: generar todas las gráficas
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
        "heatmap_sesgo_sentimiento": grafica_heatmap_sesgo_sentimiento(df),
        "arquetipos": grafica_arquetipos(df),
        "pain_points": grafica_pain_points(df),
        "heatmap_sesgo_pain_point": grafica_heatmap_sesgo_pain_point(df),
        "volumen_vs_influencia": grafica_volumen_vs_influencia(df),
        "sarcasmo_en_negativo": grafica_sarcasmo_en_negativo(df),
    }
