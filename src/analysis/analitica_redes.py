# -*- coding: utf-8 -*-
"""
Analitica para redes (TikTok videos CSV)
Genera graficas y resumen pensados para presentar en redes.

Uso:
  python analitica_redes.py
  python analitica_redes.py H:\\TikTok\\data_tiktok\\adamuz_videos.csv
"""

import os
import re
import sys
from datetime import datetime

import pandas as pd

try:
    import numpy as np
except Exception:
    np = None

try:
    import matplotlib.pyplot as plt
except Exception:
    print("Falta matplotlib. Instala: pip install matplotlib")
    raise

try:
    import seaborn as sns
    HAS_SEABORN = True
except Exception:
    HAS_SEABORN = False


BASE_DIR   = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs", "graficas_redes")


def select_csv():
    if len(sys.argv) > 1:
        return sys.argv[1]
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        path = filedialog.askopenfilename(
            title="Selecciona un CSV de videos (scraper hashtag/user)",
            filetypes=[("CSV files", "*.csv")],
        )
        return path
    except Exception:
        return input("Ruta CSV: ").strip()


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def load_csv(path):
    try:
        df = pd.read_csv(path, encoding="utf-8-sig")
    except Exception:
        df = pd.read_csv(path, encoding="utf-8", errors="ignore")
    return df


def parse_dates(df):
    if "video_fecha" in df.columns:
        df["video_fecha"] = pd.to_datetime(
            df["video_fecha"], errors="coerce", dayfirst=True
        )
    return df


def coerce_numeric(df, cols):
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    return df


def short_label(desc, max_len=45):
    if not isinstance(desc, str):
        return ""
    desc = desc.replace("\n", " ").strip()
    if len(desc) <= max_len:
        return desc
    return desc[: max_len - 1].rstrip() + "…"


def split_hashtags(value):
    if not isinstance(value, str) or not value.strip():
        return []
    parts = re.split(r"[|,\s]+", value.strip())
    tags = []
    for p in parts:
        p = p.strip().lstrip("#")
        if p:
            tags.append(p.lower())
    return tags


def safe_pct(v):
    try:
        return f"{v:.2%}"
    except Exception:
        return "n/a"


def format_int(v):
    try:
        return f"{int(v):,}".replace(",", ".")
    except Exception:
        return "0"


def setup_style():
    if HAS_SEABORN:
        sns.set_theme(style="whitegrid")
    plt.rcParams["figure.figsize"] = (10, 5.5)
    plt.rcParams["figure.dpi"] = 120
    plt.rcParams["savefig.dpi"] = 200


def save_fig(name):
    path = os.path.join(OUTPUT_DIR, name)
    plt.tight_layout()
    plt.savefig(path, bbox_inches="tight")
    plt.close()
    print(f"OK {path}")


def plot_kpis(df):
    if df.empty:
        return
    min_dt = df["video_fecha"].min()
    max_dt = df["video_fecha"].max()
    total_views = df["video_vistas"].sum()
    total_eng = df["engagement_total"].sum()
    avg_er = df["engagement_rate"].mean()
    med_views = df["video_vistas"].median()
    total_videos = len(df)

    plt.figure(figsize=(10, 5))
    plt.axis("off")
    lines = [
        f"Videos: {format_int(total_videos)}",
        f"Rango: {min_dt.date() if pd.notna(min_dt) else '?'} a {max_dt.date() if pd.notna(max_dt) else '?'}",
        f"Vistas totales: {format_int(total_views)}",
        f"Engagement total: {format_int(total_eng)}",
        f"Engagement rate medio: {safe_pct(avg_er)}",
        f"Mediana de vistas: {format_int(med_views)}",
    ]
    y = 0.9
    for line in lines:
        plt.text(0.05, y, line, fontsize=14, fontweight="bold")
        y -= 0.13
    save_fig("01_kpis_resumen.png")


def plot_evolucion(df):
    if df["video_fecha"].isna().all():
        return
    df = df.dropna(subset=["video_fecha"]).copy()
    df = df.set_index("video_fecha").sort_index()
    days = (df.index.max() - df.index.min()).days
    freq = "D" if days <= 60 else "W"

    agg = df.resample(freq).agg(
        videos=("video_id", "count"),
        vistas=("video_vistas", "sum"),
        engagement=("engagement_total", "sum"),
    )
    if agg.empty:
        return

    fig, ax1 = plt.subplots(figsize=(10, 5.5))
    ax1.plot(agg.index, agg["vistas"], label="Vistas", color="#1f77b4")
    ax1.set_ylabel("Vistas")
    ax2 = ax1.twinx()
    ax2.plot(agg.index, agg["videos"], label="Videos", color="#ff7f0e")
    ax2.set_ylabel("Videos")
    ax1.set_title("Evolucion de videos y vistas")
    save_fig("02_evolucion_videos_vistas.png")


def plot_heatmap(df):
    if df["video_fecha"].isna().all():
        return
    d = df.dropna(subset=["video_fecha"]).copy()
    d["hora"] = d["video_fecha"].dt.hour
    d["dow"] = d["video_fecha"].dt.dayofweek
    dow_names = ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]
    pivot = d.pivot_table(index="dow", columns="hora", values="video_id", aggfunc="count", fill_value=0)
    if pivot.empty:
        return
    pivot = pivot.reindex(range(0, 7))

    plt.figure(figsize=(12, 4.8))
    if HAS_SEABORN:
        sns.heatmap(pivot, cmap="YlOrRd")
    else:
        plt.imshow(pivot, aspect="auto", cmap="YlOrRd")
        plt.colorbar()
    plt.yticks(range(0, 7), dow_names)
    plt.xlabel("Hora")
    plt.ylabel("Dia semana")
    plt.title("Heatmap de publicaciones (conteo)")
    save_fig("03_heatmap_publicaciones.png")


def plot_top_videos(df, by="video_vistas", fname="04_top_videos_vistas.png"):
    if by not in df.columns:
        return
    d = df.copy()
    d["label"] = d["video_desc"].apply(short_label)
    d = d.sort_values(by=by, ascending=False).head(10)
    if d.empty:
        return
    plt.figure(figsize=(10, 6))
    plt.barh(d["label"][::-1], d[by][::-1], color="#2ca02c")
    plt.xlabel(by.replace("_", " "))
    plt.title(f"Top 10 videos por {by.replace('_', ' ')}")
    save_fig(fname)


def plot_engagement_rate(df):
    if "engagement_rate" not in df.columns or "video_vistas" not in df.columns:
        return
    d = df.copy()
    d = d[d["video_vistas"] >= 100].copy()
    d["label"] = d["video_desc"].apply(short_label)
    d = d.sort_values(by="engagement_rate", ascending=False).head(10)
    if d.empty:
        return
    plt.figure(figsize=(10, 6))
    plt.barh(d["label"][::-1], d["engagement_rate"][::-1], color="#9467bd")
    plt.xlabel("engagement rate")
    plt.title("Top 10 engagement rate (>=100 vistas)")
    save_fig("05_top_engagement_rate.png")


def plot_hashtags(df):
    if "hashtags" not in df.columns:
        return
    tags = []
    for v in df["hashtags"].fillna(""):
        tags.extend(split_hashtags(v))
    if not tags:
        return
    s = pd.Series(tags).value_counts().head(15)
    plt.figure(figsize=(10, 6))
    plt.barh(s.index[::-1], s.values[::-1], color="#d62728")
    plt.xlabel("Frecuencia")
    plt.title("Top hashtags")
    save_fig("06_top_hashtags.png")


def plot_music(df):
    if "music_title" not in df.columns:
        return
    d = df.copy()
    d["music_title"] = d["music_title"].fillna("").astype(str).str.strip()
    d["music_author"] = d.get("music_author", "").fillna("").astype(str).str.strip()
    d["music_label"] = d["music_title"]
    has_author = d["music_author"].str.len() > 0
    d.loc[has_author, "music_label"] = d.loc[has_author, "music_title"] + " - " + d.loc[has_author, "music_author"]
    s = d["music_label"].value_counts().head(10)
    if s.empty:
        return
    plt.figure(figsize=(10, 6))
    plt.barh(s.index[::-1], s.values[::-1], color="#8c564b")
    plt.xlabel("Frecuencia")
    plt.title("Top musicas")
    save_fig("07_top_musicas.png")


def plot_duration_vs_views(df):
    if "video_duracion_seg" not in df.columns or "video_vistas" not in df.columns:
        return
    d = df.copy()
    d = d[(d["video_duracion_seg"] > 0) & (d["video_vistas"] > 0)]
    if d.empty:
        return
    plt.figure(figsize=(10, 6))
    plt.scatter(d["video_duracion_seg"], d["video_vistas"], alpha=0.4, s=18)
    plt.yscale("log")
    plt.xlabel("Duracion (seg)")
    plt.ylabel("Vistas (log)")
    plt.title("Duracion vs vistas")
    save_fig("08_duracion_vs_vistas.png")


def plot_view_distribution(df):
    if "video_vistas" not in df.columns:
        return
    d = df[df["video_vistas"] > 0]
    if d.empty:
        return
    plt.figure(figsize=(10, 5.5))
    plt.hist(d["video_vistas"], bins=30, color="#1f77b4", alpha=0.8)
    plt.xscale("log")
    plt.xlabel("Vistas (log)")
    plt.ylabel("Frecuencia")
    plt.title("Distribucion de vistas")
    save_fig("09_distribucion_vistas.png")


def plot_top_accounts(df):
    if "username" not in df.columns:
        return
    s = df["username"].value_counts().head(10)
    if s.empty:
        return
    plt.figure(figsize=(10, 6))
    plt.barh(s.index[::-1], s.values[::-1], color="#17becf")
    plt.xlabel("Videos")
    plt.title("Top cuentas por volumen")
    save_fig("10_top_cuentas.png")


def export_tables(df):
    out1 = df.sort_values("video_vistas", ascending=False).head(20)
    out2 = df.sort_values("engagement_rate", ascending=False).head(20)
    out1.to_csv(os.path.join(OUTPUT_DIR, "top_videos_vistas.csv"), index=False, encoding="utf-8-sig")
    out2.to_csv(os.path.join(OUTPUT_DIR, "top_videos_engagement.csv"), index=False, encoding="utf-8-sig")


def export_summary(df):
    min_dt = df["video_fecha"].min()
    max_dt = df["video_fecha"].max()
    total_views = df["video_vistas"].sum()
    total_eng = df["engagement_total"].sum()
    avg_er = df["engagement_rate"].mean()
    total_videos = len(df)
    top_views = df.sort_values("video_vistas", ascending=False).head(5)
    top_er = df.sort_values("engagement_rate", ascending=False).head(5)

    lines = []
    lines.append(f"Videos: {format_int(total_videos)}")
    lines.append(f"Rango: {min_dt.date() if pd.notna(min_dt) else '?'} a {max_dt.date() if pd.notna(max_dt) else '?'}")
    lines.append(f"Vistas totales: {format_int(total_views)}")
    lines.append(f"Engagement total: {format_int(total_eng)}")
    lines.append(f"Engagement rate medio: {safe_pct(avg_er)}")
    lines.append("")
    lines.append("Top 5 por vistas:")
    for _, r in top_views.iterrows():
        lines.append(f"- {format_int(r['video_vistas'])} vistas | {short_label(r.get('video_desc',''))}")
    lines.append("")
    lines.append("Top 5 por engagement rate:")
    for _, r in top_er.iterrows():
        lines.append(f"- {safe_pct(r['engagement_rate'])} | {short_label(r.get('video_desc',''))}")

    with open(os.path.join(OUTPUT_DIR, "resumen_redes.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main():
    path = select_csv()
    if not path:
        print("No se selecciono CSV.")
        return
    if not os.path.exists(path):
        print("No existe:", path)
        return

    ensure_dir(OUTPUT_DIR)
    setup_style()

    df = load_csv(path)
    if df.empty:
        print("CSV vacio.")
        return

    # Deduplicar por video_id si existe
    if "video_id" in df.columns:
        df = df.drop_duplicates(subset=["video_id"])

    df = parse_dates(df)
    df = coerce_numeric(
        df,
        [
            "video_duracion_seg",
            "video_width",
            "video_height",
            "video_likes",
            "video_vistas",
            "video_compartidos",
            "video_comentarios",
            "video_guardados",
        ],
    )

    if np is not None:
        df["engagement_total"] = (
            df["video_likes"]
            + df["video_comentarios"]
            + df["video_compartidos"]
            + df["video_guardados"]
        )
        df["engagement_rate"] = np.where(
            df["video_vistas"] > 0,
            df["engagement_total"] / df["video_vistas"],
            np.nan,
        )
    else:
        df["engagement_total"] = (
            df["video_likes"]
            + df["video_comentarios"]
            + df["video_compartidos"]
            + df["video_guardados"]
        )
        df["engagement_rate"] = df["engagement_total"] / df["video_vistas"].replace(0, pd.NA)

    plot_kpis(df)
    plot_evolucion(df)
    plot_heatmap(df)
    plot_top_videos(df, by="video_vistas", fname="04_top_videos_vistas.png")
    plot_engagement_rate(df)
    plot_hashtags(df)
    plot_music(df)
    plot_duration_vs_views(df)
    plot_view_distribution(df)
    plot_top_accounts(df)
    export_tables(df)
    export_summary(df)

    print("Listo. Revisa:", OUTPUT_DIR)


if __name__ == "__main__":
    main()
