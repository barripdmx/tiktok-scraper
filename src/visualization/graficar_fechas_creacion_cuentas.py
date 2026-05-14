# -*- coding: utf-8 -*-
"""
Gráficas de fechas de creación de cuentas TikTok a partir de CSVs enriquecidos.

Casos de uso:
1. Un CSV enriquecido de un solo sentimiento dominante:
   -> barra por mes de creación.
2. Varios CSVs enriquecidos (positivo / neutro / negativo):
   -> barras apiladas por mes,
   -> barras 100% apiladas,
   -> boxplot de antigüedad hasta el primer comentario.
"""

import math
import os
from typing import List

import matplotlib.pyplot as plt
import pandas as pd


SENTIMENT_ORDER = ["positivo", "neutro", "negativo", "empate"]
TWITTER_DPI = 100
TWITTER_FIGSIZE = (19, 8)
SENTIMENT_COLORS = {
    "positivo": "#A93226",
    "neutro": "#95A5A6",
    "negativo": "#4A4A4A",
    "empate": "#C7C7C7",
}
MESES_ES_CORTOS = {
    1: "ene", 2: "feb", 3: "mar", 4: "abr",
    5: "may", 6: "jun", 7: "jul", 8: "ago",
    9: "sep", 10: "oct", 11: "nov", 12: "dic",
}


def infer_sentiment_from_filename(path: str) -> str:
    name = os.path.basename(path).lower()
    for sent in SENTIMENT_ORDER:
        if sent in name:
            return sent
    return "sin_etiqueta"


def parse_dt(series: pd.Series, dayfirst: bool = True) -> pd.Series:
    return pd.to_datetime(series, errors="coerce", dayfirst=dayfirst)


def format_int(value) -> str:
    return f"{int(value):,}".replace(",", ".")


def format_month_label(period_value, multiline: bool = False) -> str:
    period = pd.Period(str(period_value), freq="M")
    month = MESES_ES_CORTOS[period.month]
    if multiline:
        return f"{month}\n{period.year}"
    return f"{month} {period.year}"


def build_period_axis(periods, target_labels: int = 20, multiline: bool = False):
    periods = list(periods)
    positions = list(range(len(periods)))
    labels = [format_month_label(period, multiline=multiline) for period in periods]
    step = max(1, math.ceil(len(periods) / max(target_labels, 1)))
    tick_positions = sorted(set([0, len(periods) - 1] + list(range(0, len(periods), step))))
    tick_labels = [labels[i] for i in tick_positions]
    return positions, tick_positions, tick_labels


def style_ax(ax):
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
    ax.tick_params(axis="x", labelsize=8, pad=6)
    ax.tick_params(axis="y", labelsize=10, pad=4)


def figure_height_for_periods(n: int, min_h: float = 10.0, max_h: float = 30.0) -> float:
    return max(min_h, min(max_h, 0.20 * max(n, 1) + 4.0))


def load_accounts_csv(path: str) -> pd.DataFrame:
    try:
        df = pd.read_csv(path, encoding="utf-8-sig")
    except Exception:
        df = pd.read_csv(path, encoding="utf-8")

    if "autor_handle" not in df.columns:
        raise ValueError(f"Falta 'autor_handle' en {path}")
    if "fecha_creacion_cuenta" not in df.columns:
        raise ValueError(f"Falta 'fecha_creacion_cuenta' en {path}")

    work = df.copy()
    work["autor_handle"] = (
        work["autor_handle"].fillna("").astype(str).str.strip().str.lstrip("@")
    )
    work = work[
        work["autor_handle"].ne("")
        & work["autor_handle"].str.lower().ne("nan")
        & work["autor_handle"].str.lower().ne("none")
    ].copy()

    work["fecha_creacion_dt"] = parse_dt(work["fecha_creacion_cuenta"], dayfirst=True)
    if "primer_comentario" in work.columns:
        work["primer_comentario_dt"] = parse_dt(work["primer_comentario"], dayfirst=False)
    else:
        work["primer_comentario_dt"] = pd.NaT

    if "sentimiento_dominante" not in work.columns:
        work["sentimiento_dominante"] = infer_sentiment_from_filename(path)
    else:
        work["sentimiento_dominante"] = (
            work["sentimiento_dominante"].fillna("").astype(str).str.strip().str.lower()
        )
        fallback = infer_sentiment_from_filename(path)
        work.loc[work["sentimiento_dominante"].eq(""), "sentimiento_dominante"] = fallback

    work["source_file"] = os.path.basename(path)
    return work


def combine_inputs(paths: List[str]) -> pd.DataFrame:
    frames = [load_accounts_csv(path) for path in paths]
    combined = pd.concat(frames, ignore_index=True)
    combined = combined.drop_duplicates(subset=["autor_handle"], keep="first")
    combined = combined.dropna(subset=["fecha_creacion_dt"]).copy()

    if "primer_comentario_dt" in combined.columns:
        combined["edad_cuenta_dias"] = (
            combined["primer_comentario_dt"] - combined["fecha_creacion_dt"]
        ).dt.days
        combined.loc[combined["edad_cuenta_dias"] < 0, "edad_cuenta_dias"] = pd.NA

    combined["mes_creacion"] = combined["fecha_creacion_dt"].dt.to_period("M").astype(str)
    return combined


def build_prefix(paths: List[str], df: pd.DataFrame) -> str:
    if len(paths) == 1:
        base = os.path.splitext(os.path.basename(paths[0]))[0]
        return base

    presentes = [s for s in SENTIMENT_ORDER if s in set(df["sentimiento_dominante"])]
    if presentes:
        return "cuentas_" + "_".join(presentes) + "_fechas_creacion"
    return "cuentas_fechas_creacion"


def build_output_dir(paths: List[str]) -> str:
    first_dir = os.path.dirname(paths[0]) or os.getcwd()
    out_dir = os.path.join(first_dir, "fechas_creacion")
    os.makedirs(out_dir, exist_ok=True)
    return out_dir


def plot_single_timeline(df: pd.DataFrame, output_dir: str, prefix: str) -> str:
    counts = df.groupby("mes_creacion").size()
    counts = counts.sort_index()
    positions, tick_positions, tick_labels = build_period_axis(
        counts.index,
        target_labels=16,
        multiline=True,
    )

    sentimiento = df["sentimiento_dominante"].mode().iloc[0] if not df.empty else "cuentas"
    color = SENTIMENT_COLORS.get(sentimiento, "#4A4A4A")

    fig, ax = plt.subplots(figsize=TWITTER_FIGSIZE)
    fig.patch.set_facecolor("#FFFFFF")
    bars = ax.bar(positions, counts.values, color=color, edgecolor="none", alpha=0.9, width=0.78)

    top_mes = counts.idxmax()
    top_val = int(counts.max())
    for i, (bar, val) in enumerate(zip(bars, counts.values)):
        if len(counts) <= 24 or i in {0, len(counts) - 1, counts.argmax()}:
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + max(counts.max() * 0.01, 2),
                format_int(val),
                ha="center",
                va="bottom",
                fontsize=7,
                rotation=0,
                color="#222222",
            )

    ax.set_title(f"cuentas {sentimiento}s por fecha de creación", fontsize=14, color="#444444", pad=12)
    ax.text(
        0.02, 0.97,
        f"pico en {format_month_label(top_mes)} con {format_int(top_val)} cuentas",
        transform=ax.transAxes,
        fontsize=12,
        fontweight="bold",
        va="top",
        ha="left",
        color="#222222",
        bbox=dict(boxstyle="round,pad=0.5", facecolor="white", alpha=0.92, edgecolor="#CCCCCC", linewidth=0.8),
    )
    ax.set_xlabel("Mes de creación", fontsize=11)
    ax.set_ylabel("Número de cuentas", fontsize=11)
    ax.set_xticks(tick_positions, tick_labels)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: format_int(v)))
    ax.margins(x=0.01)
    style_ax(ax)
    ax.grid(axis="x", visible=False)
    plt.tight_layout(rect=(0.02, 0.06, 1, 1))

    out_path = os.path.join(output_dir, f"{prefix}_fechas_creacion_por_mes.png")
    plt.savefig(out_path, dpi=TWITTER_DPI, facecolor="white", bbox_inches=None, pad_inches=0)
    plt.close()
    return out_path


def plot_stacked_counts(df: pd.DataFrame, output_dir: str, prefix: str) -> str:
    pivot = (
        df.groupby(["mes_creacion", "sentimiento_dominante"])
        .size()
        .unstack(fill_value=0)
        .reindex(columns=[s for s in SENTIMENT_ORDER if s in df["sentimiento_dominante"].unique()], fill_value=0)
        .sort_index()
    )
    positions, tick_positions, tick_labels = build_period_axis(
        pivot.index,
        target_labels=16,
        multiline=True,
    )

    fig, ax = plt.subplots(figsize=TWITTER_FIGSIZE)
    fig.patch.set_facecolor("#FFFFFF")
    left = pd.Series(0, index=pivot.index)
    for sent in pivot.columns:
        ax.bar(
            positions,
            pivot[sent].values,
            bottom=left.values,
            color=SENTIMENT_COLORS.get(sent, "#999999"),
            edgecolor="none",
            alpha=0.9,
            width=0.82,
            label=sent,
        )
        left += pivot[sent]

    total_top_mes = pivot.sum(axis=1).idxmax()
    total_top_val = int(pivot.sum(axis=1).max())
    ax.set_title("cuentas por fecha de creación y sentimiento dominante", fontsize=14, color="#444444", pad=12)
    ax.text(
        0.02, 0.97,
        f"pico total en {format_month_label(total_top_mes)} con {format_int(total_top_val)} cuentas",
        transform=ax.transAxes,
        fontsize=12,
        fontweight="bold",
        va="top",
        ha="left",
        color="#222222",
        bbox=dict(boxstyle="round,pad=0.5", facecolor="white", alpha=0.92, edgecolor="#CCCCCC", linewidth=0.8),
    )
    ax.set_xlabel("Mes de creación", fontsize=11)
    ax.set_ylabel("Número de cuentas", fontsize=11)
    ax.set_xticks(tick_positions, tick_labels)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: format_int(v)))
    ax.legend(title="Sentimiento")
    ax.margins(x=0.01)
    style_ax(ax)
    ax.grid(axis="x", visible=False)
    plt.tight_layout(rect=(0.02, 0.06, 1, 1))

    out_path = os.path.join(output_dir, f"{prefix}_fechas_creacion_apilado.png")
    plt.savefig(out_path, dpi=TWITTER_DPI, facecolor="white", bbox_inches=None, pad_inches=0)
    plt.close()
    return out_path


def plot_stacked_share(df: pd.DataFrame, output_dir: str, prefix: str) -> str:
    pivot = (
        df.groupby(["mes_creacion", "sentimiento_dominante"])
        .size()
        .unstack(fill_value=0)
        .reindex(columns=[s for s in SENTIMENT_ORDER if s in df["sentimiento_dominante"].unique()], fill_value=0)
        .sort_index()
    )
    share = pivot.div(pivot.sum(axis=1), axis=0).fillna(0) * 100
    positions, tick_positions, tick_labels = build_period_axis(
        share.index,
        target_labels=16,
        multiline=True,
    )

    fig, ax = plt.subplots(figsize=TWITTER_FIGSIZE)
    fig.patch.set_facecolor("#FFFFFF")
    left = pd.Series(0, index=share.index)
    for sent in share.columns:
        ax.bar(
            positions,
            share[sent].values,
            bottom=left.values,
            color=SENTIMENT_COLORS.get(sent, "#999999"),
            edgecolor="none",
            alpha=0.92,
            width=0.82,
            label=sent,
        )
        left += share[sent]

    ax.set_title("peso relativo de cada sentimiento en las fechas de creación", fontsize=14, color="#444444", pad=12)
    ax.text(
        0.02, 0.97,
        "barras al 100% para comparar la mezcla de cuentas por mes",
        transform=ax.transAxes,
        fontsize=12,
        fontweight="bold",
        va="top",
        ha="left",
        color="#222222",
        bbox=dict(boxstyle="round,pad=0.5", facecolor="white", alpha=0.92, edgecolor="#CCCCCC", linewidth=0.8),
    )
    ax.set_xlabel("Mes de creación", fontsize=11)
    ax.set_ylabel("% de cuentas", fontsize=11)
    ax.set_ylim(0, 100)
    ax.set_xticks(tick_positions, tick_labels)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{int(v)}%"))
    ax.legend(title="Sentimiento")
    ax.margins(x=0.01)
    style_ax(ax)
    ax.grid(axis="x", visible=False)
    plt.tight_layout(rect=(0.02, 0.06, 1, 1))

    out_path = os.path.join(output_dir, f"{prefix}_fechas_creacion_100pct.png")
    plt.savefig(out_path, dpi=TWITTER_DPI, facecolor="white", bbox_inches=None, pad_inches=0)
    plt.close()
    return out_path


def plot_age_boxplot(df: pd.DataFrame, output_dir: str, prefix: str) -> str:
    work = df.dropna(subset=["edad_cuenta_dias"]).copy()
    work = work[work["sentimiento_dominante"].isin([s for s in SENTIMENT_ORDER if s != "empate"])].copy()
    cats = [s for s in ["positivo", "neutro", "negativo"] if s in set(work["sentimiento_dominante"])]

    fig, ax = plt.subplots(figsize=TWITTER_FIGSIZE)
    fig.patch.set_facecolor("#FFFFFF")

    data = [work.loc[work["sentimiento_dominante"] == sent, "edad_cuenta_dias"].dropna() for sent in cats]
    box = ax.boxplot(data, patch_artist=True, labels=cats)
    for patch, sent in zip(box["boxes"], cats):
        patch.set_facecolor(SENTIMENT_COLORS.get(sent, "#999999"))
        patch.set_alpha(0.8)
    for median in box["medians"]:
        median.set_color("#FFFFFF")
        median.set_linewidth(2)

    medians = {
        sent: int(work.loc[work["sentimiento_dominante"] == sent, "edad_cuenta_dias"].median())
        for sent in cats
    }
    summary = " | ".join([f"{sent}: {format_int(val)} días" for sent, val in medians.items()])

    ax.set_title("antigüedad de la cuenta hasta su primer comentario", fontsize=14, color="#444444", pad=12)
    ax.text(
        0.02, 0.97,
        summary,
        transform=ax.transAxes,
        fontsize=11,
        fontweight="bold",
        va="top",
        ha="left",
        color="#222222",
        bbox=dict(boxstyle="round,pad=0.5", facecolor="white", alpha=0.92, edgecolor="#CCCCCC", linewidth=0.8),
    )
    ax.set_xlabel("Sentimiento dominante", fontsize=11)
    ax.set_ylabel("Edad de la cuenta (días)", fontsize=11)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: format_int(v)))
    style_ax(ax)
    plt.tight_layout()

    out_path = os.path.join(output_dir, f"{prefix}_edad_cuenta_boxplot.png")
    plt.savefig(out_path, dpi=TWITTER_DPI, facecolor="white", bbox_inches=None, pad_inches=0)
    plt.close()
    return out_path


def save_summary(df: pd.DataFrame, output_dir: str, prefix: str) -> str:
    summary = (
        df.groupby(["mes_creacion", "sentimiento_dominante"])
        .size()
        .reset_index(name="cuentas")
        .sort_values(["mes_creacion", "sentimiento_dominante"])
    )
    out_path = os.path.join(output_dir, f"{prefix}_resumen_fechas_creacion.csv")
    summary.to_csv(out_path, index=False, encoding="utf-8-sig")
    return out_path


def get_input_paths() -> List[str]:
    raw = input(
        "Ruta(s) CSV enriquecido(s), separadas por comas: "
    ).strip()
    if not raw:
        return []
    paths = [part.strip().strip('"') for part in raw.split(",") if part.strip()]
    return [p for p in paths if os.path.isfile(p)]


def main():
    print("=" * 72)
    print("Gráficas de fechas de creación de cuentas TikTok")
    print("=" * 72)

    paths = get_input_paths()
    if not paths:
        print("❌ No se indicaron CSVs válidos")
        return

    df = combine_inputs(paths)
    if df.empty:
        print("❌ No hay filas válidas con fecha_creacion_cuenta")
        return

    output_dir = build_output_dir(paths)
    prefix = build_prefix(paths, df)

    print(f"\nCSV(s) cargados: {len(paths)}")
    print(f"Cuentas válidas: {format_int(len(df))}")
    print(f"Salida:          {output_dir}")

    summary_path = save_summary(df, output_dir, prefix)
    print(f"-> Resumen CSV: {summary_path}")

    if len(set(df["sentimiento_dominante"])) <= 1:
        out = plot_single_timeline(df, output_dir, prefix)
        print(f"-> Gráfica: {out}")
    else:
        out1 = plot_stacked_counts(df, output_dir, prefix)
        out2 = plot_stacked_share(df, output_dir, prefix)
        print(f"-> Gráfica apilada: {out1}")
        print(f"-> Gráfica 100%:    {out2}")

        if df["edad_cuenta_dias"].notna().any():
            out3 = plot_age_boxplot(df, output_dir, prefix)
            print(f"-> Boxplot edad:    {out3}")


if __name__ == "__main__":
    main()
