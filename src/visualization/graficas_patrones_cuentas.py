# -*- coding: utf-8 -*-
"""
Gráficas de Patrones de Cuentas / Bots
======================================
Analiza el CSV *enriquecido* de comentarios (con metadatos de cada cuenta:
fecha de creación, followers, vídeos del perfil, etc.) para buscar PATRONES
propios de bots o cuentas coordinadas.

⚠️  IMPORTANTE — Esto NO clasifica bots automáticamente.
    La fecha de creación y el resto de señales son AUXILIARES. El resultado es
    una lista de "cuentas a revisar" manualmente, combinando varias señales:
    antigüedad + volumen de actividad + perfil vacío + concentración temporal.

Estrategia (según análisis de datos):
  - Se agrega POR AUTOR (autor_handle), no por comentario.
  - Se calcula la EDAD de la cuenta al hacer su primer comentario.
  - Se cruza edad con actividad (cuenta nueva + muy activa = más sospechoso).
  - Se mira concentración temporal (picos de cuentas creadas el mismo mes).

Columnas esperadas en el CSV enriquecido:
  autor_handle, fecha (del comentario), video_id, fecha_creacion_cuenta,
  followers, following, likes_y (likes de la cuenta), video_count (vídeos perfil),
  verified.

Degradación elegante: si falta una columna, la gráfica correspondiente se omite.
"""

import io
import os
import sys
import base64

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ── Estilo compartido ─────────────────────────────────────────────────────────
_BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, _BASE)
try:
    from config.viz_style import PALETA, STAT_BOX, apply_estilo_periodistico
except Exception:
    # Fallback mínimo si no se encuentra el módulo de estilo
    PALETA = {"primario": "#1F618D", "secundario": "#A93226", "neutro": "#4A4A4A",
              "apoyo": "#CA6F1E", "suave": "#999999", "pos": "#1E8449"}
    STAT_BOX = dict(boxstyle="round,pad=0.4", facecolor="white", alpha=0.9,
                    edgecolor="#CCCCCC", linewidth=0.7)

    def apply_estilo_periodistico(ax):
        ax.set_facecolor("#FFFFFF")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_color("#CCCCCC")
        ax.spines["bottom"].set_color("#CCCCCC")
        ax.grid(axis="y", color="#EBEBEB", linewidth=0.5)
        ax.set_axisbelow(True)
        ax.tick_params(colors="#555555", labelsize=9)

_MESES_ES = {1: "ene", 2: "feb", 3: "mar", 4: "abr", 5: "may", 6: "jun",
             7: "jul", 8: "ago", 9: "sep", 10: "oct", 11: "nov", 12: "dic"}


def _to_base64_png(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()


def _add_watermark(fig):
    fig.text(0.99, 0.01, "Análisis de patrones — señales auxiliares, no prueba de bot",
             ha="right", va="bottom", fontsize=7, color="#BBBBBB", style="italic")


# ============================================================================
# Normalización de columnas y agregación por cuenta
# ============================================================================

def _col(df, *candidatos):
    """Devuelve el primer nombre de columna existente de entre los candidatos."""
    for c in candidatos:
        if c in df.columns:
            return c
    return None


def agregar_por_cuenta(df: pd.DataFrame) -> pd.DataFrame:
    """
    Agrega el CSV enriquecido (nivel comentario) a nivel CUENTA.

    Devuelve un DataFrame con una fila por autor_handle y columnas:
      autor_handle, n_comentarios, n_videos, primer_comentario, fecha_creacion,
      followers, following, likes_cuenta, video_count, verified,
      edad_al_comentar_dias
    """
    col_autor = _col(df, "autor_handle", "author", "username", "uniqueId")
    if col_autor is None:
        raise ValueError("No se encontró columna de autor (autor_handle)")

    col_creacion = _col(df, "fecha_creacion_cuenta")
    if col_creacion is None:
        raise ValueError("No se encontró 'fecha_creacion_cuenta' — ¿es un CSV enriquecido?")

    col_fecha_com = _col(df, "fecha", "created_at", "date", "timestamp")
    col_video     = _col(df, "video_id", "videoId", "aweme_id_api")
    col_followers = _col(df, "followers", "follower_count")
    col_following = _col(df, "following", "following_count")
    col_likes     = _col(df, "likes_y", "account_likes", "heart")
    col_vcount    = _col(df, "video_count", "perfil_video_count")
    col_verified  = _col(df, "verified")

    work = df.copy()

    # Normalizar handle
    work["_autor"] = (work[col_autor].fillna("").astype(str)
                      .str.strip().str.lstrip("@"))
    work = work[work["_autor"].str.lower().isin(["", "nan", "none"]) == False]

    # Parsear fechas
    work["_fecha_creacion"] = pd.to_datetime(work[col_creacion], errors="coerce",
                                             dayfirst=True)
    if col_fecha_com:
        work["_fecha_com"] = pd.to_datetime(work[col_fecha_com], errors="coerce",
                                            dayfirst=False)
    else:
        work["_fecha_com"] = pd.NaT

    # Agregación
    agg_spec = {
        "n_comentarios": ("_autor", "size"),
        "primer_comentario": ("_fecha_com", "min"),
        "ultimo_comentario": ("_fecha_com", "max"),
        "fecha_creacion": ("_fecha_creacion", "first"),
    }
    if col_video:
        agg_spec["n_videos"] = (col_video, "nunique")
    if col_followers:
        agg_spec["followers"] = (col_followers, "first")
    if col_following:
        agg_spec["following"] = (col_following, "first")
    if col_likes:
        agg_spec["likes_cuenta"] = (col_likes, "first")
    if col_vcount:
        agg_spec["video_count"] = (col_vcount, "first")
    if col_verified:
        agg_spec["verified"] = (col_verified, "first")

    cuentas = work.groupby("_autor").agg(**agg_spec).reset_index()
    cuentas = cuentas.rename(columns={"_autor": "autor_handle"})

    # Edad de la cuenta al primer comentario
    cuentas["edad_al_comentar_dias"] = (
        cuentas["primer_comentario"] - cuentas["fecha_creacion"]
    ).dt.days
    # Edades negativas = datos inconsistentes → NaN
    cuentas.loc[cuentas["edad_al_comentar_dias"] < 0, "edad_al_comentar_dias"] = np.nan

    # Asegurar columnas numéricas presentes
    for c in ["n_videos", "followers", "following", "likes_cuenta", "video_count"]:
        if c not in cuentas.columns:
            cuentas[c] = np.nan
        cuentas[c] = pd.to_numeric(cuentas[c], errors="coerce")

    return cuentas


# ============================================================================
# Score de sospecha (heurístico — NO es clasificación de bot)
# ============================================================================

def calcular_score(cuentas: pd.DataFrame) -> pd.DataFrame:
    """
    Añade columna 'score_sospecha' (0-100) combinando varias señales.
    Solo aplica a cuentas con fecha de creación conocida.
    """
    c = cuentas.copy()
    con_fecha = c["fecha_creacion"].notna()

    score = pd.Series(0.0, index=c.index)

    # ── Señal 1: antigüedad al comentar (peso fuerte) ─────────────────────────
    edad = c["edad_al_comentar_dias"]
    score += np.where(edad < 7, 35, 0)
    score += np.where((edad >= 7) & (edad < 30), 25, 0)
    score += np.where((edad >= 30) & (edad < 90), 12, 0)

    # ── Señal 2: volumen de comentarios (percentil 90 del dataset) ────────────
    if c["n_comentarios"].notna().any():
        p90 = c["n_comentarios"].quantile(0.90)
        score += np.where(c["n_comentarios"] >= max(p90, 3), 15, 0)

    # ── Señal 3: comenta en muchos vídeos distintos ───────────────────────────
    if c["n_videos"].notna().any():
        p90v = c["n_videos"].quantile(0.90)
        score += np.where(c["n_videos"] >= max(p90v, 3), 12, 0)

    # ── Señal 4: pocos followers (perfil sin audiencia) ───────────────────────
    score += np.where(c["followers"].fillna(99999) < 50, 10, 0)

    # ── Señal 5: perfil sin vídeos propios (consumidor puro) ──────────────────
    score += np.where(c["video_count"].fillna(99999) == 0, 16, 0)

    # ── Señal 6: cuenta sin likes acumulados ──────────────────────────────────
    score += np.where(c["likes_cuenta"].fillna(99999) == 0, 6, 0)

    # Normalizar a 0-100 (el máximo teórico de pesos es 35+15+12+10+16+6 = 94)
    score = (score / 94.0 * 100).clip(0, 100)
    c["score_sospecha"] = score.round(1)
    # Sin fecha de creación no se puede valorar la señal principal
    c.loc[~con_fecha, "score_sospecha"] = np.nan
    return c


# ============================================================================
# GRÁFICA 1: Cobertura del enriquecido
# ============================================================================

def grafica_cobertura(cuentas: pd.DataFrame) -> str:
    """Dona: cuentas con vs sin fecha de creación resuelta."""
    total = len(cuentas)
    if total == 0:
        return ""
    con = int(cuentas["fecha_creacion"].notna().sum())
    sin = total - con

    fig, ax = plt.subplots(figsize=(8, 6))
    fig.patch.set_facecolor("white")

    sizes  = [con, sin]
    labels = [f"Con fecha\n({con:,})", f"Sin fecha\n({sin:,})"]
    colors = [PALETA["primario"], "#D5D8DC"]

    wedges, texts, autotexts = ax.pie(
        sizes, labels=labels, autopct=lambda p: f"{p:.1f}%",
        colors=colors, startangle=90, textprops={"fontsize": 11},
        wedgeprops={"edgecolor": "white", "linewidth": 2})
    for at in autotexts:
        at.set_color("white"); at.set_fontweight("bold")

    centre = plt.Circle((0, 0), 0.66, fc="white")
    ax.add_artist(centre)
    pct = con / total * 100
    ax.text(0, 0, f"{pct:.1f}%\nenriquecido", ha="center", va="center",
            fontsize=14, fontweight="bold", color=PALETA["primario"])

    ax.set_title(f"Cobertura del enriquecido — {con:,} de {total:,} cuentas\n"
                 "(el análisis de patrones solo usa las cuentas con fecha)",
                 fontsize=12, fontweight="bold", pad=18)
    _add_watermark(fig)
    return _to_base64_png(fig)


# ============================================================================
# GRÁFICA 2: Antigüedad de la cuenta al primer comentario
# ============================================================================

def grafica_antiguedad(cuentas: pd.DataFrame) -> str:
    """Histograma de edad (días) con líneas en 7/30/90 días."""
    edad = cuentas["edad_al_comentar_dias"].dropna()
    if edad.empty:
        return ""

    fig, ax = plt.subplots(figsize=(14, 7))
    fig.patch.set_facecolor("white")

    # Cap visual para no aplastar el histograma con colas muy largas
    cap = edad.quantile(0.99)
    datos = edad.clip(upper=cap)
    ax.hist(datos, bins=60, color=PALETA["primario"], alpha=0.85, edgecolor="white")

    for dias, col, txt in [(7, "#A93226", "7 días"),
                           (30, "#CA6F1E", "30 días"),
                           (90, "#7D3C98", "90 días")]:
        if dias <= cap:
            ax.axvline(dias, color=col, linestyle="--", linewidth=1.6)
            ax.text(dias, ax.get_ylim()[1] * 0.95, f" {txt}", color=col,
                    fontsize=9, fontweight="bold", va="top")

    mediana = int(edad.median())
    n7  = int((edad < 7).sum())
    n30 = int((edad < 30).sum())
    n90 = int((edad < 90).sum())
    ax.text(0.97, 0.80,
            f"Mediana: {mediana:,} días\n"
            f"< 7 días: {n7:,}\n< 30 días: {n30:,}\n< 90 días: {n90:,}",
            transform=ax.transAxes, ha="right", va="top",
            fontsize=10, bbox=STAT_BOX)

    apply_estilo_periodistico(ax)
    ax.set_xlabel("Edad de la cuenta al hacer su primer comentario (días)", fontsize=11)
    ax.set_ylabel("Número de cuentas", fontsize=11)
    ax.set_title("¿Cuentas recién creadas comentando? — Antigüedad al primer comentario",
                 fontsize=13, fontweight="bold", pad=15)
    _add_watermark(fig)
    return _to_base64_png(fig)


# ============================================================================
# GRÁFICA 3: Cuentas creadas por mes (concentración temporal)
# ============================================================================

def grafica_creadas_por_mes(cuentas: pd.DataFrame) -> str:
    """Barras del nº de cuentas por mes de creación; resalta el pico."""
    fechas = cuentas["fecha_creacion"].dropna()
    if fechas.empty or fechas.dt.to_period("M").nunique() < 2:
        return ""

    serie = fechas.dt.to_period("M").value_counts().sort_index()
    etiquetas = [f"{_MESES_ES[p.month]}\n{p.year}" for p in serie.index]
    pico_idx = int(np.argmax(serie.values))

    fig, ax = plt.subplots(figsize=(15, 7))
    fig.patch.set_facecolor("white")

    colores = [PALETA["secundario"] if i == pico_idx else PALETA["primario"]
               for i in range(len(serie))]
    ax.bar(range(len(serie)), serie.values, color=colores, alpha=0.9, width=0.8)

    # Etiquetas de eje (máx ~20)
    step = max(1, len(serie) // 20)
    ticks = list(range(0, len(serie), step))
    ax.set_xticks(ticks)
    ax.set_xticklabels([etiquetas[i] for i in ticks], fontsize=8)

    pico_p = serie.index[pico_idx]
    ax.text(0.02, 0.95,
            f"Pico: {_MESES_ES[pico_p.month]} {pico_p.year} "
            f"con {int(serie.values[pico_idx]):,} cuentas creadas\n"
            "Un pico cercano a la polémica puede indicar coordinación",
            transform=ax.transAxes, ha="left", va="top",
            fontsize=10, fontweight="bold", bbox=STAT_BOX)

    apply_estilo_periodistico(ax)
    ax.grid(axis="x", visible=False)
    ax.set_xlabel("Mes de creación de la cuenta", fontsize=11)
    ax.set_ylabel("Número de cuentas", fontsize=11)
    ax.set_title("¿Oleada de cuentas nuevas? — Cuentas por mes de creación",
                 fontsize=13, fontweight="bold", pad=15)
    _add_watermark(fig)
    return _to_base64_png(fig)


# ============================================================================
# GRÁFICA 4: Edad vs actividad (scatter con cuadrante sospechoso)
# ============================================================================

def grafica_edad_vs_actividad(cuentas: pd.DataFrame) -> str:
    """Scatter edad (días) × nº comentarios; sombrea 'nuevas + muy activas'."""
    sub = cuentas.dropna(subset=["edad_al_comentar_dias", "n_comentarios"]).copy()
    if sub.empty:
        return ""

    fig, ax = plt.subplots(figsize=(12, 7))
    fig.patch.set_facecolor("white")

    edad = sub["edad_al_comentar_dias"].clip(lower=0) + 1  # +1 para escala log
    coms = sub["n_comentarios"]

    # Umbral de actividad: percentil 90 (mín 3)
    umbral_com = max(sub["n_comentarios"].quantile(0.90), 3)

    sospechosa = (sub["edad_al_comentar_dias"] < 90) & (sub["n_comentarios"] >= umbral_com)
    ax.scatter(edad[~sospechosa], coms[~sospechosa], s=25, alpha=0.4,
               color=PALETA["suave"], edgecolor="none", label="Resto")
    ax.scatter(edad[sospechosa], coms[sospechosa], s=55, alpha=0.85,
               color=PALETA["secundario"], edgecolor="black", linewidth=0.5,
               label=f"Nueva (<90 d) + activa (≥{int(umbral_com)} com.)")

    ax.axvspan(1, 90, ymin=0, ymax=1, color=PALETA["secundario"], alpha=0.05)
    ax.axvline(90, color=PALETA["secundario"], linestyle="--", linewidth=1.2)
    ax.set_xscale("log")

    n_sosp = int(sospechosa.sum())
    ax.text(0.97, 0.95, f"{n_sosp:,} cuentas en el\ncuadrante a revisar",
            transform=ax.transAxes, ha="right", va="top",
            fontsize=10, fontweight="bold", bbox=STAT_BOX)

    apply_estilo_periodistico(ax)
    ax.set_xlabel("Edad de la cuenta al comentar (días, escala log)", fontsize=11)
    ax.set_ylabel("Nº de comentarios de la cuenta", fontsize=11)
    ax.legend(fontsize=9, loc="upper left", framealpha=0.8)
    ax.set_title("Cuentas nuevas y muy activas — Edad vs Actividad",
                 fontsize=13, fontweight="bold", pad=15)
    _add_watermark(fig)
    return _to_base64_png(fig)


# ============================================================================
# GRÁFICA 5: Followers vs actividad
# ============================================================================

def grafica_followers_vs_actividad(cuentas: pd.DataFrame) -> str:
    """Scatter followers (log) × nº comentarios; perfiles vacíos muy activos."""
    sub = cuentas.dropna(subset=["followers", "n_comentarios"]).copy()
    if sub.empty:
        return ""

    fig, ax = plt.subplots(figsize=(12, 7))
    fig.patch.set_facecolor("white")

    foll = sub["followers"].clip(lower=0) + 1
    coms = sub["n_comentarios"]

    umbral_com = max(sub["n_comentarios"].quantile(0.90), 3)
    vacios = (sub["followers"] < 50) & (sub["n_comentarios"] >= umbral_com)

    ax.scatter(foll[~vacios], coms[~vacios], s=25, alpha=0.4,
               color=PALETA["suave"], edgecolor="none", label="Resto")
    ax.scatter(foll[vacios], coms[vacios], s=55, alpha=0.85,
               color=PALETA["apoyo"], edgecolor="black", linewidth=0.5,
               label=f"<50 followers + ≥{int(umbral_com)} com.")
    ax.axvline(50, color=PALETA["apoyo"], linestyle="--", linewidth=1.2)
    ax.set_xscale("log")

    n_v = int(vacios.sum())
    ax.text(0.97, 0.95, f"{n_v:,} cuentas con poca\naudiencia pero muy activas",
            transform=ax.transAxes, ha="right", va="top",
            fontsize=10, fontweight="bold", bbox=STAT_BOX)

    apply_estilo_periodistico(ax)
    ax.set_xlabel("Followers de la cuenta (escala log)", fontsize=11)
    ax.set_ylabel("Nº de comentarios de la cuenta", fontsize=11)
    ax.legend(fontsize=9, loc="upper left", framealpha=0.8)
    ax.set_title("Perfiles sin audiencia muy activos — Followers vs Actividad",
                 fontsize=13, fontweight="bold", pad=15)
    _add_watermark(fig)
    return _to_base64_png(fig)


# ============================================================================
# GRÁFICA 6: Vídeos del perfil (bins)
# ============================================================================

def grafica_videos_perfil(cuentas: pd.DataFrame) -> str:
    """Barras por bins de video_count; resalta cuentas con 0 vídeos."""
    vc = cuentas["video_count"].dropna()
    if vc.empty:
        return ""

    bins   = [-0.5, 0.5, 5.5, 20.5, np.inf]
    labels = ["0 vídeos", "1–5", "6–20", ">20"]
    cats   = pd.cut(vc, bins=bins, labels=labels)
    counts = cats.value_counts().reindex(labels, fill_value=0)

    fig, ax = plt.subplots(figsize=(10, 6))
    fig.patch.set_facecolor("white")

    colores = [PALETA["secundario"], PALETA["primario"], PALETA["primario"], PALETA["primario"]]
    bars = ax.bar(labels, counts.values, color=colores, alpha=0.9, width=0.65)

    total = counts.sum()
    for bar, val in zip(bars, counts.values):
        pct = val / total * 100 if total else 0
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + total * 0.01,
                f"{int(val):,}\n({pct:.1f}%)", ha="center", va="bottom", fontsize=9)

    ax.set_ylim(0, counts.max() * 1.20)
    apply_estilo_periodistico(ax)
    ax.set_xlabel("Vídeos publicados en el perfil de la cuenta", fontsize=11)
    ax.set_ylabel("Número de cuentas", fontsize=11)
    ax.set_title("¿Perfiles sin contenido propio? — Vídeos en el perfil",
                 fontsize=13, fontweight="bold", pad=15)
    _add_watermark(fig)
    return _to_base64_png(fig)


# ============================================================================
# GRÁFICA 7: Antigüedad mediana por volumen de actividad
# ============================================================================

def grafica_edad_por_volumen(cuentas: pd.DataFrame) -> str:
    """Mediana de antigüedad por bins de nº de comentarios."""
    sub = cuentas.dropna(subset=["edad_al_comentar_dias", "n_comentarios"]).copy()
    if sub.empty:
        return ""

    bins   = [0.5, 1.5, 3.5, 10.5, np.inf]
    labels = ["1", "2–3", "4–10", ">10"]
    sub["bin"] = pd.cut(sub["n_comentarios"], bins=bins, labels=labels)

    med = sub.groupby("bin", observed=True)["edad_al_comentar_dias"].median().reindex(labels)
    cnt = sub.groupby("bin", observed=True)["edad_al_comentar_dias"].size().reindex(labels)
    if med.dropna().empty:
        return ""

    fig, ax = plt.subplots(figsize=(11, 6))
    fig.patch.set_facecolor("white")

    bars = ax.bar(labels, med.values, color=PALETA["primario"], alpha=0.9, width=0.6)
    for bar, val, n in zip(bars, med.values, cnt.values):
        if not np.isnan(val):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                    f"{int(val):,} días\n(n={int(n):,})",
                    ha="center", va="bottom", fontsize=9)

    apply_estilo_periodistico(ax)
    ax.set_xlabel("Nº de comentarios de la cuenta", fontsize=11)
    ax.set_ylabel("Antigüedad mediana al comentar (días)", fontsize=11)
    ax.set_title("¿Las cuentas más activas son más nuevas? — Antigüedad por volumen",
                 fontsize=13, fontweight="bold", pad=15)
    _add_watermark(fig)
    return _to_base64_png(fig)


# ============================================================================
# GRÁFICA 8: Ranking de cuentas a revisar (score de sospecha)
# ============================================================================

def grafica_cuentas_a_revisar(cuentas: pd.DataFrame, top: int = 15) -> str:
    """Barras horizontales con las top N cuentas por score de sospecha."""
    if "score_sospecha" not in cuentas.columns:
        return ""
    sub = cuentas.dropna(subset=["score_sospecha"])
    sub = sub[sub["score_sospecha"] > 0].nlargest(top, "score_sospecha")
    if sub.empty:
        return ""

    fig, ax = plt.subplots(figsize=(12, max(4, len(sub) * 0.45)))
    fig.patch.set_facecolor("white")

    # Color por intensidad del score
    colores = plt.cm.OrRd(np.linspace(0.45, 0.9, len(sub)))
    etiquetas = ["@" + h for h in sub["autor_handle"]]
    bars = ax.barh(etiquetas[::-1], sub["score_sospecha"].values[::-1],
                   color=colores[::-1], edgecolor="none", height=0.65)

    for bar, (_, row) in zip(bars, sub[::-1].iterrows()):
        edad = row["edad_al_comentar_dias"]
        edad_txt = f"{int(edad)}d" if not np.isnan(edad) else "?"
        detalle = (f"  {row['score_sospecha']:.0f} · "
                   f"{int(row['n_comentarios'])} com · "
                   f"edad {edad_txt}")
        ax.text(bar.get_width() + 1, bar.get_y() + bar.get_height() / 2,
                detalle, va="center", fontsize=8, color="#222222")

    ax.set_xlim(0, 110)
    apply_estilo_periodistico(ax)
    ax.grid(axis="x", color="#EBEBEB", linewidth=0.5)
    ax.set_xlabel("Score de sospecha (0–100, heurístico)", fontsize=11)
    ax.set_title("Cuentas a REVISAR manualmente (no son bots confirmados)\n"
                 "Score = antigüedad + actividad + perfil vacío + sin audiencia",
                 fontsize=12, fontweight="bold", pad=15)
    _add_watermark(fig)
    return _to_base64_png(fig)


# ============================================================================
# Orquestación
# ============================================================================

def generar_todas_graficas(cuentas: pd.DataFrame) -> dict:
    """Genera todas las gráficas y las devuelve como dict de base64 (para HTML)."""
    return {
        "cobertura":              grafica_cobertura(cuentas),
        "antiguedad":             grafica_antiguedad(cuentas),
        "creadas_por_mes":        grafica_creadas_por_mes(cuentas),
        "edad_vs_actividad":      grafica_edad_vs_actividad(cuentas),
        "followers_vs_actividad": grafica_followers_vs_actividad(cuentas),
        "videos_perfil":          grafica_videos_perfil(cuentas),
        "edad_por_volumen":       grafica_edad_por_volumen(cuentas),
        "cuentas_a_revisar":      grafica_cuentas_a_revisar(cuentas),
    }


# ============================================================================
# Ejecución standalone (menú / terminal)
# ============================================================================

def main():
    import tkinter as tk
    from tkinter import filedialog, messagebox

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    csv_path = filedialog.askopenfilename(
        title="Selecciona el CSV ENRIQUECIDO con fechas de creación de cuentas",
        filetypes=[
            ("CSV enriquecido", "*enriquecido*.csv"),
            ("Todos los CSV", "*.csv"),
        ],
    )
    root.destroy()

    if not csv_path:
        print("Operación cancelada.")
        return

    print("=" * 72)
    print("  GRÁFICAS DE PATRONES DE CUENTAS / BOTS")
    print("  ⚠️  Señales auxiliares — NO clasifica bots automáticamente")
    print("=" * 72)
    print(f"  Cargando: {os.path.basename(csv_path)}")

    try:
        df = pd.read_csv(csv_path, encoding="utf-8-sig", low_memory=False)
    except Exception:
        try:
            df = pd.read_csv(csv_path, low_memory=False)
        except Exception as e:
            print(f"  ❌ Error al leer CSV: {e}")
            return

    print(f"  Filas (comentarios): {len(df):,}")

    # ── Agregar por cuenta ────────────────────────────────────────────────────
    try:
        cuentas = agregar_por_cuenta(df)
    except ValueError as e:
        root2 = tk.Tk(); root2.withdraw()
        messagebox.showerror("CSV no válido",
            f"{e}\n\nEste módulo necesita el CSV *enriquecido* "
            "(opción 'Edad de Cuentas' del menú), que añade la columna "
            "'fecha_creacion_cuenta' y followers/vídeos del perfil.")
        root2.destroy()
        print(f"  ❌ {e}")
        return

    cuentas = calcular_score(cuentas)

    con_fecha = int(cuentas["fecha_creacion"].notna().sum())
    print(f"  Cuentas únicas     : {len(cuentas):,}")
    print(f"  Con fecha creación : {con_fecha:,} "
          f"({con_fecha / max(len(cuentas), 1) * 100:.1f}%)")

    # ── Carpeta de salida ─────────────────────────────────────────────────────
    nombre_base = os.path.splitext(os.path.basename(csv_path))[0]
    file_id = nombre_base
    for suf in ["_comentarios_api_enriquecido_fechas_creacion",
                "_enriquecido_fechas_creacion", "_enriquecido"]:
        if suf in file_id:
            file_id = file_id.split(suf)[0]
            break

    carpeta = os.path.join(_BASE, "outputs", file_id, "graficas_patrones_cuentas")
    os.makedirs(carpeta, exist_ok=True)
    print(f"\n  Generando en: {carpeta}\n")

    # ── Generar y guardar PNG ─────────────────────────────────────────────────
    GRAFICAS = [
        ("cobertura",              grafica_cobertura,              "01_cobertura_enriquecido.png"),
        ("antiguedad",             grafica_antiguedad,             "02_antiguedad_al_comentar.png"),
        ("creadas_por_mes",        grafica_creadas_por_mes,        "03_cuentas_creadas_por_mes.png"),
        ("edad_vs_actividad",      grafica_edad_vs_actividad,      "04_edad_vs_actividad.png"),
        ("followers_vs_actividad", grafica_followers_vs_actividad, "05_followers_vs_actividad.png"),
        ("videos_perfil",          grafica_videos_perfil,          "06_videos_del_perfil.png"),
        ("edad_por_volumen",       grafica_edad_por_volumen,       "07_edad_por_volumen.png"),
        ("cuentas_a_revisar",      grafica_cuentas_a_revisar,      "08_cuentas_a_revisar.png"),
    ]

    generadas, omitidas = [], []
    for nombre, func, filename in GRAFICAS:
        try:
            b64 = func(cuentas)
            if not b64:
                omitidas.append(nombre)
                print(f"  ⚠️  {filename} — omitida (datos insuficientes)")
                continue
            with open(os.path.join(carpeta, filename), "wb") as f:
                f.write(base64.b64decode(b64))
            generadas.append(filename)
            print(f"  ✅ {filename}")
        except Exception as e:
            omitidas.append(nombre)
            print(f"  ❌ {filename} — error: {e}")

    # ── Export CSV "cuentas a revisar" ────────────────────────────────────────
    cols_export = ["autor_handle", "score_sospecha", "n_comentarios", "n_videos",
                   "edad_al_comentar_dias", "fecha_creacion", "primer_comentario",
                   "followers", "following", "likes_cuenta", "video_count", "verified"]
    cols_export = [c for c in cols_export if c in cuentas.columns]
    revisar = (cuentas.dropna(subset=["score_sospecha"])
               .sort_values("score_sospecha", ascending=False))[cols_export]
    csv_out = os.path.join(carpeta, "cuentas_a_revisar.csv")
    revisar.to_csv(csv_out, index=False, encoding="utf-8-sig")
    print(f"\n  📄 cuentas_a_revisar.csv ({len(revisar):,} cuentas con score)")

    # ── Resumen ───────────────────────────────────────────────────────────────
    print(f"\n  ── Resumen ──────────────────────────────")
    print(f"  Gráficas generadas : {len(generadas)}/{len(GRAFICAS)}")
    if omitidas:
        print(f"  Omitidas           : {', '.join(omitidas)}")
    print(f"  Carpeta            : {carpeta}\n")

    root3 = tk.Tk(); root3.withdraw()
    if messagebox.askyesno("✅ Patrones de cuentas generados",
            f"Se generaron {len(generadas)} gráfica(s) + cuentas_a_revisar.csv en:\n\n"
            f"{carpeta}\n\n¿Abrir la carpeta?"):
        root3.destroy()
        if sys.platform == "win32":
            os.startfile(carpeta)
        else:
            import subprocess
            subprocess.run(["open" if sys.platform == "darwin" else "xdg-open", carpeta])
    else:
        root3.destroy()


if __name__ == "__main__":
    main()
