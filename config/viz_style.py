# -*- coding: utf-8 -*-
"""viz_style.py — Constantes de estilo visual compartidas por todos los módulos.

Importar desde cualquier script en src/ así:
    import sys, os
    _BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    sys.path.insert(0, _BASE)
    from config.viz_style import (
        PALETA, PALETA_CAT, COLOR_MARCA, STAT_BOX, apply_estilo_periodistico
    )
"""

# ── Paleta semántica ─────────────────────────────────────────────────────────
PALETA = {
    "primario":   "#1F618D",   # azul oscuro  — datos principales
    "secundario": "#A93226",   # rojo-burdeos — contraste / sentimiento negativo
    "neutro":     "#4A4A4A",   # gris antracita — series neutras
    "apoyo":      "#CA6F1E",   # naranja       — tercer canal
    "suave":      "#999999",   # gris claro    — referencia / ejes
    "pos":        "#1E8449",   # verde         — sentimiento positivo
    "neg":        "#A93226",   # rojo-burdeos  — sentimiento negativo
    "neu":        "#4A4A4A",   # gris          — sentimiento neutro
}

# ── Secuencia para gráficos categóricos (barras, líneas multi-serie) ─────────
PALETA_CAT = [
    "#1F618D", "#A93226", "#CA6F1E", "#4A4A4A", "#1E8449", "#7D3C98",
]

# ── Colores por marca / operador / partido ────────────────────────────────────
COLOR_MARCA = {
    # Telecomunicaciones
    "vodafone":   "#A93226",
    "orange":     "#CA6F1E",
    "yoigo":      "#7D3C98",
    "masmovil":   "#CA6F1E",
    "pepephone":  "#A93226",
    "lowi":       "#222222",
    "simyo":      "#CA6F1E",
    "movistar":   "#1F618D",
    "digi":       "#117A65",
    "o2":         "#1A5276",
    # Política
    "psoe":       "#A93226",
    "pp":         "#1F618D",
    "vox":        "#117A65",
    "podemos":    "#7D3C98",
    "sumar":      "#7D3C98",
    "ciudadanos": "#CA6F1E",
    "junts":      "#CA6F1E",
    "erc":        "#A93226",
    "esquerra":   "#A93226",
}

# ── Caja de anotación estadística (para ax.text(..., bbox=STAT_BOX)) ─────────
STAT_BOX = dict(
    boxstyle="round,pad=0.4",
    facecolor="white",
    alpha=0.90,
    edgecolor="#CCCCCC",
    linewidth=0.7,
)


# ── Función de estilo Tufte minimalista ───────────────────────────────────────
def apply_estilo_periodistico(ax):
    """Elimina spines top/right y aplica rejilla horizontal muy tenue (Tufte)."""
    ax.set_facecolor("#FFFFFF")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#CCCCCC")
    ax.spines["bottom"].set_color("#CCCCCC")
    ax.spines["left"].set_linewidth(0.8)
    ax.spines["bottom"].set_linewidth(0.8)
    ax.grid(axis="y", color="#EBEBEB", linewidth=0.5, linestyle="-")
    ax.set_axisbelow(True)
    ax.tick_params(colors="#555555", labelsize=9)
    ax.xaxis.label.set_color("#222222")
    ax.yaxis.label.set_color("#222222")
