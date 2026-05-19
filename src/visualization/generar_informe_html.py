# -*- coding: utf-8 -*-
"""
Generador de Informe HTML — TikTok Analytics
=============================================
Genera un informe HTML auto-contenido (sin dependencias externas,
funciona offline) a partir de:
  - Un CSV de publicaciones generado por los scrapers
  - Las imágenes generadas por analitica_publicaciones.py

USO:
  python generar_informe_html.py
  1. Selecciona el mismo CSV que usaste en analitica_publicaciones.py
  2. Se genera {nombre_csv}_informe.html en la carpeta gráficas/

SALIDA:
  gráficas/{nombre_csv}_informe.html  → abre directamente en el navegador
"""

import argparse
import os
import base64
import html
import re
import sys
import unicodedata
import pandas as pd
from datetime import datetime

try:
    import tkinter as tk
    from tkinter import filedialog, simpledialog
    _HAS_TK = True
except Exception:
    _HAS_TK = False
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

try:
    from wordcloud import WordCloud, STOPWORDS
    HAS_WORDCLOUD = True
except Exception:
    HAS_WORDCLOUD = False
    STOPWORDS = set()

try:
    import emoji
    HAS_EMOJI = True
except Exception:
    HAS_EMOJI = False

# ---------------------------------------------------------------------------
# MESES EN ESPAÑOL (strftime %B depende de la locale del sistema)
# ---------------------------------------------------------------------------

MESES_ES = {
    "January": "enero",    "February": "febrero", "March":    "marzo",
    "April":   "abril",    "May":      "mayo",     "June":     "junio",
    "July":    "julio",    "August":   "agosto",   "September":"septiembre",
    "October": "octubre",  "November": "noviembre","December": "diciembre",
}

def fecha_es() -> str:
    """Devuelve la fecha y hora actual con el mes en español."""
    now = datetime.now()
    mes = MESES_ES.get(now.strftime("%B"), now.strftime("%B"))
    return now.strftime(f"%d de {mes} de %Y, %H:%M")


def derive_title(file_id: str) -> str:
    """Sugiere un título a partir del nombre del archivo CSV."""
    title = file_id
    for suffix in ("_videos", "_comentarios"):
        if title.endswith(suffix):
            title = title[: -len(suffix)]
            break
    if title.startswith("user_"):
        title = title[5:]
    return title.replace("_", " ").title()

# ---------------------------------------------------------------------------
# CONFIGURACIÓN
# ---------------------------------------------------------------------------

BASE_DIR        = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUTPUTS_BASE    = os.path.join(BASE_DIR, "outputs")
OUTPUT_FOLDER   = OUTPUTS_BASE   # se sobreescribe en main() con outputs/{project}/publicaciones
INFORMES_FOLDER = OUTPUTS_BASE   # se sobreescribe en main() con outputs/{project}/informes

# Secciones del informe: cada una con sus imágenes y número de columnas
REPORT_SECTIONS = [
    {
        "title":  "Análisis de Contenido",
        "accent": "cyan",
        "cols":   3,
        "images": [
            ("nube_palabras",   "Nube de Palabras"),
            ("nube_hashtags",   "Nube de Hashtags"),
            ("nube_emoticonos", "Nube de Emoticonos"),
        ],
    },
    {
        "title":  "Rendimiento Temporal",
        "accent": "primary",
        "cols":   2,
        "images": [
            ("evolucion_vistas",       "Evolución de Vistas"),
            ("timeline_publicaciones", "Timeline Acumulado de Publicaciones"),
            ("publicaciones_por_mes",  "Publicaciones por Mes"),
        ],
    },
    {
        "title":  "Patrones de Publicación",
        "accent": "cyan",
        "cols":   2,
        "images": [
            ("publicaciones_por_dia_semana", "Por Día de la Semana"),
            ("publicaciones_por_hora",       "Por Hora del Día"),
            ("heatmap_actividad",            "Mapa de Calor — Actividad Semanal"),
        ],
    },
]

REQUIRED_IMAGE_KEYS = [
    "nube_palabras",
    "nube_hashtags",
    "nube_emoticonos",
    "evolucion_vistas",
    "timeline_publicaciones",
    "publicaciones_por_mes",
    "publicaciones_por_dia_semana",
    "publicaciones_por_hora",
    "heatmap_actividad",
]

# ---------------------------------------------------------------------------
# UTILIDADES
# ---------------------------------------------------------------------------

def _parse_args():
    parser = argparse.ArgumentParser(description="Genera informe HTML de TikTok Analytics")
    parser.add_argument("csv", nargs="?", help="Ruta al CSV de publicaciones")
    parser.add_argument("--titulo", help="Título del informe (hashtag o término)")
    return parser.parse_args()


def find_latest_videos_csv() -> str:
    """Busca el CSV de videos más reciente en data/ como fallback."""
    data_dir = os.path.join(BASE_DIR, "data")
    if not os.path.exists(data_dir):
        return ""
    candidatos = []
    for f in os.listdir(data_dir):
        if f.endswith(".csv") and "comentarios" not in f:
            full = os.path.join(data_dir, f)
            candidatos.append((os.path.getmtime(full), full))
    if candidatos:
        candidatos.sort(reverse=True)
        path = candidatos[0][1]
        print(f"   📋 CSV detectado automáticamente: {os.path.basename(path)}")
        return path
    # Si no hay CSV sin "comentarios", buscar cualquiera
    for f in os.listdir(data_dir):
        if f.endswith(".csv"):
            full = os.path.join(data_dir, f)
            candidatos.append((os.path.getmtime(full), full))
    if candidatos:
        candidatos.sort(reverse=True)
        path = candidatos[0][1]
        print(f"   📋 CSV detectado automáticamente: {os.path.basename(path)}")
        return path
    return ""


def get_file_path(cli_csv: str = None) -> str:
    if cli_csv and os.path.exists(cli_csv):
        return cli_csv
    print("📂 Abriendo selector de archivo...")
    print("   (si no aparece, busca la ventana en la barra de tareas)")
    if _HAS_TK:
        try:
            root = tk.Tk()
            root.withdraw()
            root.attributes('-topmost', True)
            path = filedialog.askopenfilename(
                title="Selecciona el CSV de publicaciones de TikTok",
                filetypes=[("CSV Files", "*.csv")],
                initialdir=os.path.join(BASE_DIR, "data"),
            )
            root.destroy()
            if path:
                return path
        except Exception:
            pass
    # Fallback: buscar automáticamente el CSV más reciente
    print("   ⚠️  Diálogo no disponible. Buscando CSV automáticamente...")
    return find_latest_videos_csv()


def get_report_title(default_title: str, cli_titulo: str = None) -> str:
    if cli_titulo and cli_titulo.strip():
        return cli_titulo.strip()
    if _HAS_TK:
        try:
            root = tk.Tk()
            root.withdraw()
            root.attributes('-topmost', True)
            report_title = simpledialog.askstring(
                "Título del informe",
                "Hashtag o término analizado\n(será el título principal del informe):",
                initialvalue=default_title,
            )
            root.destroy()
            if report_title and report_title.strip():
                return report_title.strip()
            return default_title
        except Exception:
            pass
    # Fallback: usar el título por defecto sin preguntar
    print(f"   Título automático: '{default_title}' (cierra y usa --titulo para cambiarlo)")
    val = default_title
    return val if val else default_title


def build_file_id_candidates(file_id: str) -> list[str]:
    candidates = [file_id]
    transforms = [
        ("_videos_v2_estricto", "_videos"),
        ("_comentarios_v2_estricto", "_comentarios"),
        ("_v2_estricto", ""),
        ("_estricto", ""),
        ("_v2", ""),
    ]

    changed = True
    while changed:
        changed = False
        current = list(candidates)
        for base in current:
            for src, dst in transforms:
                if src in base:
                    new_id = base.replace(src, dst)
                    if new_id and new_id not in candidates:
                        candidates.append(new_id)
                        changed = True

    return candidates


def resolve_image_path(file_id: str, key: str) -> tuple[str, str]:
    for cid in build_file_id_candidates(file_id):
        p = os.path.join(OUTPUT_FOLDER, f"{cid}_{key}.png")
        if os.path.exists(p):
            return p, cid
    return "", ""


def get_exact_image_path(file_id: str, key: str) -> str:
    return os.path.join(OUTPUT_FOLDER, f"{file_id}_{key}.png")


def save_current_plot(path: str) -> None:
    plt.tight_layout()
    plt.savefig(path, bbox_inches="tight", dpi=200)
    plt.close()


def save_placeholder_plot(path: str, title: str, msg: str) -> None:
    plt.figure(figsize=(10, 5))
    plt.axis("off")
    plt.title(title, fontsize=16, fontweight="bold")
    plt.text(0.5, 0.45, msg, ha="center", va="center", fontsize=11, color="#555555")
    save_current_plot(path)


def clean_text_cloud(text: str) -> str:
    txt = str(text or "")
    txt = re.sub(r"http\S+", " ", txt)
    if HAS_EMOJI:
        txt = emoji.replace_emoji(txt, replace=" ")
    return re.sub(r"\s+", " ", txt).strip()


def extract_emojis_from_text(text: str) -> str:
    if not HAS_EMOJI:
        return ""
    return "".join(ch for ch in str(text or "") if ch in emoji.EMOJI_DATA)


def build_plot_df(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    numeric_cols = [
        "video_vistas",
        "video_likes",
        "video_comentarios",
        "video_compartidos",
        "video_guardados",
        "video_duracion_seg",
    ]
    for c in numeric_cols:
        if c in d.columns:
            d[c] = pd.to_numeric(d[c], errors="coerce").fillna(0)
        else:
            d[c] = 0

    if "video_fecha" in d.columns:
        d["video_fecha_dt"] = pd.to_datetime(d["video_fecha"], errors="coerce", dayfirst=True)
    else:
        d["video_fecha_dt"] = pd.NaT
    return d


def generate_wordcloud_images(file_id: str, d: pd.DataFrame) -> None:
    word_path = get_exact_image_path(file_id, "nube_palabras")
    hash_path = get_exact_image_path(file_id, "nube_hashtags")
    emoji_path = get_exact_image_path(file_id, "nube_emoticonos")

    if not HAS_WORDCLOUD:
        save_placeholder_plot(word_path, "Nube de Palabras", "Instala wordcloud para generar esta gráfica.")
        save_placeholder_plot(hash_path, "Nube de Hashtags", "Instala wordcloud para generar esta gráfica.")
        save_placeholder_plot(emoji_path, "Nube de Emoticonos", "Instala wordcloud para generar esta gráfica.")
        return

    all_desc = " ".join(d.get("video_desc", pd.Series(dtype=object)).fillna("").astype(str))
    clean_desc = clean_text_cloud(all_desc)

    # 1) Nube de palabras
    if clean_desc.strip():
        sw = set(STOPWORDS)
        sw.update({
            "de", "la", "que", "el", "en", "y", "a", "los", "del", "se", "las",
            "por", "un", "para", "con", "no", "una", "su", "al", "lo", "como",
            "más", "pero", "es", "son", "video", "tiktok",
        })
        wc_text = WordCloud(
            stopwords=sw,
            background_color="white",
            width=1200,
            height=600,
            max_words=220,
        ).generate(clean_desc)
        plt.figure(figsize=(12, 6))
        plt.imshow(wc_text, interpolation="bilinear")
        plt.axis("off")
        plt.title("Nube de Palabras")
        save_current_plot(word_path)
    else:
        save_placeholder_plot(word_path, "Nube de Palabras", "No hay texto suficiente para generar la nube.")

    # 2) Nube de hashtags
    tags = []
    for v in d.get("hashtags", pd.Series(dtype=object)).fillna(""):
        tags.extend(split_hashtags(v))
    if tags:
        wc_hash = WordCloud(
            background_color="white",
            width=1200,
            height=600,
            max_words=200,
        ).generate(" ".join(tags))
        plt.figure(figsize=(12, 6))
        plt.imshow(wc_hash, interpolation="bilinear")
        plt.axis("off")
        plt.title("Nube de Hashtags")
        save_current_plot(hash_path)
    else:
        save_placeholder_plot(hash_path, "Nube de Hashtags", "No hay hashtags para generar la nube.")

    # 3) Nube de emoticonos
    emojis_found = extract_emojis_from_text(all_desc)
    if emojis_found:
        font_path = r"C:\Windows\Fonts\seguiemj.ttf"
        if not os.path.exists(font_path):
            font_path = None
        wc_emoji = WordCloud(
            background_color="white",
            width=1200,
            height=600,
            regexp=r"\S",
            font_path=font_path,
        ).generate(" ".join(emojis_found))
        plt.figure(figsize=(12, 6))
        plt.imshow(wc_emoji, interpolation="bilinear")
        plt.axis("off")
        plt.title("Nube de Emoticonos")
        save_current_plot(emoji_path)
    else:
        save_placeholder_plot(emoji_path, "Nube de Emoticonos", "No se detectaron emoticonos en las descripciones.")


def generate_temporal_images(file_id: str, d: pd.DataFrame) -> None:
    keys_titles = {
        "evolucion_vistas": "Evolución de Vistas",
        "timeline_publicaciones": "Timeline Acumulado de Publicaciones",
        "publicaciones_por_mes": "Publicaciones por Mes",
        "publicaciones_por_dia_semana": "Publicaciones por Día de la Semana",
        "publicaciones_por_hora": "Publicaciones por Hora del Día",
        "heatmap_actividad": "Mapa de Calor — Actividad Semanal",
    }

    dt = d.dropna(subset=["video_fecha_dt"]).copy()
    if dt.empty:
        for k, title in keys_titles.items():
            save_placeholder_plot(
                get_exact_image_path(file_id, k),
                title,
                "No hay fechas válidas para generar esta gráfica.",
            )
        return

    dt = dt.sort_values("video_fecha_dt")

    # Evolución de vistas
    plt.figure(figsize=(12, 6))
    plt.plot(dt["video_fecha_dt"], dt["video_vistas"], marker="o", linestyle="-", color="#1f77b4", markersize=4)
    plt.title("Evolución de Vistas")
    plt.xlabel("Fecha")
    plt.ylabel("Vistas")
    plt.grid(True, alpha=0.3)
    plt.xticks(rotation=45)
    save_current_plot(get_exact_image_path(file_id, "evolucion_vistas"))

    # Timeline acumulado
    dt2 = dt.copy()
    dt2["pub_acumuladas"] = range(1, len(dt2) + 1)
    plt.figure(figsize=(12, 6))
    plt.fill_between(dt2["video_fecha_dt"], dt2["pub_acumuladas"], alpha=0.25, color="#17becf")
    plt.plot(dt2["video_fecha_dt"], dt2["pub_acumuladas"], color="#17becf", linewidth=2)
    plt.title("Timeline Acumulado de Publicaciones")
    plt.xlabel("Fecha")
    plt.ylabel("Publicaciones acumuladas")
    plt.grid(True, alpha=0.3)
    plt.xticks(rotation=45)
    save_current_plot(get_exact_image_path(file_id, "timeline_publicaciones"))

    # Publicaciones por mes
    dt2["año_mes"] = dt2["video_fecha_dt"].dt.to_period("M")
    by_month = dt2.groupby("año_mes").size()
    plt.figure(figsize=(12, 6))
    ax = by_month.plot(kind="bar", color="#2ca02c", edgecolor="black", alpha=0.85)
    plt.title("Publicaciones por Mes")
    plt.xlabel("Mes")
    plt.ylabel("Número de publicaciones")
    plt.grid(True, alpha=0.3, axis="y")
    plt.xticks(rotation=45, ha="right")
    for i, v in enumerate(by_month.values):
        ax.text(i, v + 0.1, str(int(v)), ha="center", va="bottom", fontsize=9)
    save_current_plot(get_exact_image_path(file_id, "publicaciones_por_mes"))

    # Publicaciones por día semana
    dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    dt2["dow"] = dt2["video_fecha_dt"].dt.dayofweek
    by_dow = dt2.groupby("dow").size().reindex(range(7), fill_value=0)
    plt.figure(figsize=(10, 6))
    bars = plt.bar(dias, by_dow.values, color="#9467bd", edgecolor="black", alpha=0.85)
    plt.title("Publicaciones por Día de la Semana")
    plt.xlabel("Día")
    plt.ylabel("Número de publicaciones")
    plt.grid(True, alpha=0.3, axis="y")
    for bar, v in zip(bars, by_dow.values):
        plt.text(bar.get_x() + bar.get_width() / 2, v + 0.1, str(int(v)), ha="center", va="bottom", fontsize=9)
    save_current_plot(get_exact_image_path(file_id, "publicaciones_por_dia_semana"))

    # Publicaciones por hora
    dt2["hour"] = dt2["video_fecha_dt"].dt.hour
    by_hour = dt2.groupby("hour").size().reindex(range(24), fill_value=0)
    plt.figure(figsize=(12, 6))
    bars = plt.bar(range(24), by_hour.values, color="#ff7f0e", edgecolor="black", alpha=0.85)
    if by_hour.sum() > 0:
        peak = int(by_hour.idxmax())
        bars[peak].set_color("#d62728")
    plt.title("Publicaciones por Hora del Día")
    plt.xlabel("Hora (0-23)")
    plt.ylabel("Número de publicaciones")
    plt.xticks(range(24), [f"{h:02d}:00" for h in range(24)], rotation=45, ha="right")
    plt.grid(True, alpha=0.3, axis="y")
    save_current_plot(get_exact_image_path(file_id, "publicaciones_por_hora"))

    # Heatmap semanal
    heat = dt2.groupby(["dow", "hour"]).size().unstack(fill_value=0).reindex(index=range(7), columns=range(24), fill_value=0)
    plt.figure(figsize=(14, 6))
    plt.imshow(heat.values, cmap="YlOrRd", aspect="auto")
    plt.colorbar(label="Publicaciones")
    plt.title("Mapa de Calor — Actividad Semanal")
    plt.xlabel("Hora del día")
    plt.ylabel("Día de la semana")
    plt.xticks(range(24), [f"{h:02d}" for h in range(24)])
    plt.yticks(range(7), dias)
    save_current_plot(get_exact_image_path(file_id, "heatmap_actividad"))


def ensure_report_images(file_id: str, df: pd.DataFrame) -> None:
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    content_keys = ("nube_palabras", "nube_hashtags", "nube_emoticonos")
    temporal_keys = (
        "evolucion_vistas", "timeline_publicaciones", "publicaciones_por_mes",
        "publicaciones_por_dia_semana", "publicaciones_por_hora", "heatmap_actividad",
    )
    all_keys = content_keys + temporal_keys

    # Si todos los PNGs ya existen, no regenerar (preserva los del analista)
    existing = [k for k in all_keys if os.path.exists(get_exact_image_path(file_id, k))]
    missing  = [k for k in all_keys if k not in existing]

    if not missing:
        print(f"\n🧩 Gráficas existentes reutilizadas ({len(existing)}/9) — no se sobreescriben.")
        return

    print(f"\n🧩 Generando gráficas faltantes ({len(missing)}/9)...")
    d = build_plot_df(df)

    content_missing  = [k for k in content_keys  if k in missing]
    temporal_missing = [k for k in temporal_keys if k in missing]

    if content_missing:
        try:
            generate_wordcloud_images(file_id, d)
            print("   ✓ Gráficas de contenido listas")
        except Exception as e:
            print(f"   ⚠️ Error en gráficas de contenido: {e}")
            for key in content_missing:
                if not os.path.exists(get_exact_image_path(file_id, key)):
                    save_placeholder_plot(
                        get_exact_image_path(file_id, key),
                        key.replace("_", " ").title(),
                        "No se pudo generar automáticamente esta gráfica.",
                    )

    if temporal_missing:
        try:
            generate_temporal_images(file_id, d)
            print("   ✓ Gráficas temporales listas")
        except Exception as e:
            print(f"   ⚠️ Error en gráficas temporales: {e}")
            for key in temporal_missing:
                if not os.path.exists(get_exact_image_path(file_id, key)):
                    save_placeholder_plot(
                        get_exact_image_path(file_id, key),
                        key.replace("_", " ").title(),
                        "No se pudo generar automáticamente esta gráfica.",
                    )


def img_to_base64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def fmt_num(n) -> str:
    """Número con punto como separador de miles (1.234.567)."""
    try:
        return f"{int(n):,}".replace(",", ".")
    except Exception:
        return "—"


def col_sum(df: pd.DataFrame, col: str) -> int:
    if col in df.columns:
        return int(pd.to_numeric(df[col], errors="coerce").fillna(0).sum())
    return 0


def fmt_pct(v, digits: int = 2) -> str:
    try:
        if pd.isna(v):
            return "—"
        return f"{float(v) * 100:.{digits}f}%"
    except Exception:
        return "—"


def normalize_text(value: str) -> str:
    s = str(value or "").lower()
    s = unicodedata.normalize("NFKD", s)
    return "".join(ch for ch in s if not unicodedata.combining(ch))


def derive_topic_terms(report_title: str) -> list[str]:
    stop = {
        "de", "del", "la", "las", "el", "los", "y", "en", "por", "para", "con",
        "sin", "sobre", "tok", "tiktok", "analisis", "analytics", "reporte",
        "informe", "video", "videos",
    }
    raw_terms = re.findall(r"[a-z0-9]+", normalize_text(report_title))
    terms: list[str] = []
    for t in raw_terms:
        if len(t) < 3 or t in stop:
            continue
        variants = [t]
        if t.endswith("s") and len(t) > 4:
            variants.append(t[:-1])
        for item in variants:
            if item not in terms:
                terms.append(item)
    return terms


def split_hashtags(value: str) -> list[str]:
    if not isinstance(value, str) or not value.strip():
        return []
    out: list[str] = []
    for part in re.split(r"[|,\s]+", value.strip()):
        tag = normalize_text(part).replace("#", "").strip()
        if tag:
            out.append(tag)
    return out


def safe_link(url: str) -> str:
    url = str(url or "").strip()
    if url.startswith("https://") or url.startswith("http://"):
        return url
    return "#"


def build_table_rows(rows: list[tuple]) -> str:
    out = []
    for row in rows:
        tds = "".join(f"<td>{html.escape(str(c))}</td>" for c in row)
        out.append(f"<tr>{tds}</tr>")
    return "".join(out)


def build_extra_insights(df: pd.DataFrame, report_title: str) -> str:
    if df.empty:
        return ""

    work = df.copy()
    numeric_cols = [
        "video_vistas", "video_likes", "video_comentarios",
        "video_compartidos", "video_guardados", "video_duracion_seg",
    ]
    for c in numeric_cols:
        if c in work.columns:
            work[c] = pd.to_numeric(work[c], errors="coerce").fillna(0)
        else:
            work[c] = 0

    work["eng_total"] = (
        work["video_likes"]
        + work["video_comentarios"]
        + work["video_compartidos"]
        + work["video_guardados"]
    )
    work["engagement_rate"] = work["eng_total"] / work["video_vistas"].replace(0, pd.NA)

    total_views = float(work["video_vistas"].sum())
    total_eng = float(work["eng_total"].sum())
    if total_views <= 0:
        return ""

    sorted_views = work.sort_values("video_vistas", ascending=False)
    top1_share = float(sorted_views.head(1)["video_vistas"].sum() / total_views)
    top3_share = float(sorted_views.head(3)["video_vistas"].sum() / total_views)
    shares = work["video_vistas"] / total_views
    hhi = float((shares ** 2).sum()) if total_views > 0 else 0.0
    effective_n = (1.0 / hhi) if hhi > 0 else 0.0

    mean_views = float(work["video_vistas"].mean())
    median_views = float(work["video_vistas"].median())
    p90_views = float(work["video_vistas"].quantile(0.9))
    weighted_er = (total_eng / total_views) if total_views > 0 else 0.0
    mean_er = float(work["engagement_rate"].mean(skipna=True))
    median_er = float(work["engagement_rate"].median(skipna=True))
    ex_top1_weighted_er = None
    if len(sorted_views) > 1:
        ex = sorted_views.iloc[1:].copy()
        ex_views = float(ex["video_vistas"].sum())
        if ex_views > 0:
            ex_top1_weighted_er = float(ex["eng_total"].sum() / ex_views)

    terms = derive_topic_terms(report_title)
    topic_rate = None
    if terms and ("video_desc" in work.columns or "hashtags" in work.columns):
        desc = work.get("video_desc", pd.Series([""] * len(work))).fillna("").astype(str).map(normalize_text)
        tags = work.get("hashtags", pd.Series([""] * len(work))).fillna("").astype(str).map(normalize_text)
        topic_mask = pd.Series(False, index=work.index)
        for t in terms:
            pattern = re.escape(t)
            topic_mask = topic_mask | desc.str.contains(pattern, regex=True) | tags.str.contains(pattern, regex=True)
        topic_rate = float(topic_mask.mean())

    tag_counts: dict[str, int] = {}
    tag_rows: list[dict] = []
    if "hashtags" in work.columns:
        for _, row in work.iterrows():
            tags = split_hashtags(row.get("hashtags", ""))
            views = float(row.get("video_vistas", 0) or 0)
            for t in tags:
                tag_counts[t] = tag_counts.get(t, 0) + 1
                tag_rows.append({"tag": t, "views": views})

    top_tags_freq = sorted(tag_counts.items(), key=lambda kv: kv[1], reverse=True)[:6]
    top_tags_perf_rows: list[tuple] = []
    if tag_rows:
        tdf = pd.DataFrame(tag_rows)
        agg = (
            tdf.groupby("tag")
            .agg(posts=("views", "count"), mean_views=("views", "mean"), median_views=("views", "median"))
            .reset_index()
        )
        agg = agg[agg["posts"] >= 2].sort_values("mean_views", ascending=False).head(6)
        for _, r in agg.iterrows():
            top_tags_perf_rows.append(
                (
                    r["tag"],
                    int(r["posts"]),
                    fmt_num(r["mean_views"]),
                    fmt_num(r["median_views"]),
                )
            )

    duration_rows: list[tuple] = []
    if "video_duracion_seg" in work.columns:
        bucket_labels = ["<=10s", "11-30s", ">30s"]
        work["dur_bucket"] = pd.cut(
            work["video_duracion_seg"],
            bins=[-1, 10, 30, 10_000],
            labels=bucket_labels,
        )
        duration_agg = (
            work.groupby("dur_bucket", dropna=False)
            .agg(
                videos=("video_id", "count"),
                views=("video_vistas", "sum"),
                med_views=("video_vistas", "median"),
                er=("engagement_rate", "mean"),
            )
            .reset_index()
        )
        for _, r in duration_agg.iterrows():
            if pd.isna(r["dur_bucket"]):
                continue
            duration_rows.append(
                (
                    str(r["dur_bucket"]),
                    int(r["videos"]),
                    fmt_num(r["views"]),
                    fmt_num(r["med_views"]),
                    fmt_pct(r["er"]),
                )
            )

    hour_rows: list[tuple] = []
    if "video_fecha" in work.columns:
        dt = pd.to_datetime(work["video_fecha"], errors="coerce", dayfirst=True)
        d2 = work.copy()
        d2["video_fecha_dt"] = dt
        d2 = d2.dropna(subset=["video_fecha_dt"])
        if not d2.empty:
            d2["hour"] = d2["video_fecha_dt"].dt.hour
            hour_agg = (
                d2.groupby("hour")
                .agg(posts=("video_id", "count"), med_views=("video_vistas", "median"), mean_views=("video_vistas", "mean"))
                .reset_index()
            )
            hr = hour_agg[hour_agg["posts"] >= 2].sort_values("med_views", ascending=False).head(5)
            if hr.empty:
                hr = hour_agg.sort_values("posts", ascending=False).head(5)
            for _, r in hr.iterrows():
                hour_rows.append(
                    (
                        f"{int(r['hour']):02d}:00",
                        int(r["posts"]),
                        fmt_num(r["med_views"]),
                        fmt_num(r["mean_views"]),
                    )
                )

    duplicate_videos = int(work["video_id"].duplicated().sum()) if "video_id" in work.columns else 0
    missing_desc = int(
        (work.get("video_desc", pd.Series([""] * len(work))).fillna("").astype(str).str.strip() == "").sum()
    )
    missing_hashtags = int(
        (work.get("hashtags", pd.Series([""] * len(work))).fillna("").astype(str).str.strip() == "").sum()
    )

    topic_line = ""
    if topic_rate is not None:
        topic_terms_str = ", ".join(terms[:5]) if terms else "tema"
        topic_line = (
            f'<div class="callout"><strong>Coherencia temática:</strong> '
            f'{fmt_pct(topic_rate)} de los videos contienen términos del tema '
            f'({html.escape(topic_terms_str)}).</div>'
        )

    freq_tag_html = ""
    if top_tags_freq:
        pills = "".join(
            f'<span class="tag-pill">#{html.escape(tag)} <em>{count}</em></span>'
            for tag, count in top_tags_freq
        )
        freq_tag_html = f'<div class="pill-wrap">{pills}</div>'

    tag_perf_html = ""
    if top_tags_perf_rows:
        tag_perf_html = f"""
    <div class="insight-card span-2">
      <h3>Hashtags con Mejor Rendimiento (>=2 posts)</h3>
      <table class="mini-table">
        <thead><tr><th>Hashtag</th><th>Posts</th><th>Vistas medias</th><th>Vistas medianas</th></tr></thead>
        <tbody>{build_table_rows(top_tags_perf_rows)}</tbody>
      </table>
    </div>"""

    duration_html = ""
    if duration_rows:
        duration_html = f"""
    <div class="insight-card span-2">
      <h3>Duración vs Rendimiento</h3>
      <table class="mini-table">
        <thead><tr><th>Duración</th><th>Videos</th><th>Vistas totales</th><th>Vistas medianas</th><th>ER medio</th></tr></thead>
        <tbody>{build_table_rows(duration_rows)}</tbody>
      </table>
    </div>"""

    hours_html = ""
    if hour_rows:
        hours_html = f"""
    <div class="insight-card span-2">
      <h3>Mejores Horas de Publicación</h3>
      <table class="mini-table">
        <thead><tr><th>Hora</th><th>Posts</th><th>Mediana vistas</th><th>Media vistas</th></tr></thead>
        <tbody>{build_table_rows(hour_rows)}</tbody>
      </table>
    </div>"""

    ex_top1_line = ""
    if ex_top1_weighted_er is not None:
        ex_top1_line = f'<p class="muted">ER ponderado sin el video #1: <strong>{fmt_pct(ex_top1_weighted_er)}</strong></p>'

    return f"""
  <section>
    <h2><span class="acc-c">◉</span> Insights Avanzados</h2>
    <div class="insight-grid">
      <div class="insight-card">
        <h3>Concentración de Alcance</h3>
        <p>Top 1 video: <strong>{fmt_pct(top1_share)}</strong> de las vistas.</p>
        <p>Top 3 videos: <strong>{fmt_pct(top3_share)}</strong> de las vistas.</p>
        <p>HHI vistas: <strong>{hhi:.3f}</strong></p>
        <p class="muted">Nº efectivo de videos (1/HHI): <strong>{effective_n:.2f}</strong></p>
      </div>
      <div class="insight-card">
        <h3>Métricas Robustas</h3>
        <p>Media vistas/video: <strong>{fmt_num(mean_views)}</strong></p>
        <p>Mediana vistas/video: <strong>{fmt_num(median_views)}</strong></p>
        <p>P90 vistas: <strong>{fmt_num(p90_views)}</strong></p>
        <p>ER ponderado: <strong>{fmt_pct(weighted_er)}</strong></p>
        <p>ER media por video: <strong>{fmt_pct(mean_er)}</strong></p>
        <p>ER mediana por video: <strong>{fmt_pct(median_er)}</strong></p>
        {ex_top1_line}
      </div>
      <div class="insight-card span-2">
        <h3>Hashtags más usados</h3>
        {freq_tag_html if freq_tag_html else '<p class="muted">No hay hashtags suficientes para mostrar frecuencia.</p>'}
      </div>
      {tag_perf_html}
      {duration_html}
      {hours_html}
      <div class="insight-card span-2">
        <h3>Calidad de Datos</h3>
        <div class="pill-wrap">
          <span class="tag-pill">Duplicados video_id <em>{duplicate_videos}</em></span>
          <span class="tag-pill">Sin descripción <em>{missing_desc}</em></span>
          <span class="tag-pill">Sin hashtags <em>{missing_hashtags}</em></span>
        </div>
        {topic_line}
      </div>
    </div>
  </section>"""


# ---------------------------------------------------------------------------
# CONSTRUCTORES DE BLOQUES HTML
# ---------------------------------------------------------------------------

def build_kpi_card(icon: str, value: str, label: str, highlight: bool = False) -> str:
    cls = "kpi highlight" if highlight else "kpi"
    return f"""
      <div class="{cls}">
        <div class="kpi-icon">{icon}</div>
        <div class="kpi-value">{value}</div>
        <div class="kpi-label">{label}</div>
      </div>"""


def build_top_videos(df: pd.DataFrame) -> str:
    needed = {"video_vistas", "video_url", "video_desc"}
    if not needed.issubset(df.columns):
        return ""

    d = df.copy()
    for c in ("video_vistas", "video_likes", "video_comentarios"):
        if c in d.columns:
            d[c] = pd.to_numeric(d[c], errors="coerce").fillna(0)

    top5 = d.nlargest(5, "video_vistas")
    rows = ""
    for i, (_, row) in enumerate(top5.iterrows(), 1):
        desc_raw = str(row.get("video_desc", ""))
        desc     = (desc_raw[:90] + "…") if len(desc_raw) > 90 else desc_raw
        desc_safe = html.escape(desc)
        title_safe = html.escape(desc_raw)
        url      = safe_link(row.get("video_url", "#"))
        fecha    = str(row.get("video_fecha", ""))[:10]
        views    = fmt_num(row.get("video_vistas",      0))
        likes    = fmt_num(row.get("video_likes",       0))
        comments = fmt_num(row.get("video_comentarios", 0))
        rows += f"""
          <tr>
            <td class="rank">#{i}</td>
            <td class="desc"><a href="{html.escape(url)}" target="_blank" rel="noopener noreferrer" title="{title_safe}">{desc_safe}</a></td>
            <td class="fecha">{html.escape(fecha)}</td>
            <td class="num views">{views}</td>
            <td class="num">{likes}</td>
            <td class="num">{comments}</td>
          </tr>"""

    return f"""
  <section>
    <h2><span class="acc-p">▶</span> Top 5 Videos por Vistas</h2>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>Descripción</th>
            <th>Fecha</th>
            <th>👁 Vistas</th>
            <th>❤ Likes</th>
            <th>💬 Comentarios</th>
          </tr>
        </thead>
        <tbody>{rows}
        </tbody>
      </table>
    </div>
  </section>"""


def build_image_sections(file_id: str) -> str:
    html_out = ""
    for section in REPORT_SECTIONS:
        imgs_html = ""
        missing_labels = []
        count = 0
        for key, label in section["images"]:
            img_path, matched_id = resolve_image_path(file_id, key)
            if img_path:
                b64 = img_to_base64(img_path)
                imgs_html += f"""
          <figure>
            <img src="data:image/png;base64,{b64}" alt="{label}" loading="lazy">
            <figcaption>{label}</figcaption>
          </figure>"""
                count += 1
                if matched_id != file_id:
                    print(f"   ✓ {key}.png  (usando prefijo '{matched_id}')")
                else:
                    print(f"   ✓ {key}.png")
            else:
                print(f"   – {key}.png  (no encontrado, se omite)")
                missing_labels.append(label)

        cols = min(section["cols"], count)
        acc  = "acc-c" if section["accent"] == "cyan" else "acc-p"

        if count == 0:
            missing_txt = ", ".join(missing_labels) if missing_labels else "imágenes"
            html_out += f"""
  <section>
    <h2><span class="{acc}">◆</span> {section['title']}</h2>
    <div class="callout">
      <strong>Sin gráficas disponibles para esta sección.</strong>
      <div class="muted">Faltan: {html.escape(missing_txt)}.</div>
      <div class="muted">Genera primero las imágenes con <code>analitica_publicaciones.py</code> y vuelve a ejecutar el informe.</div>
</div>
  </section>"""
            continue

        html_out += f"""
  <section>
    <h2><span class="{acc}">◆</span> {section['title']}</h2>
    <div class="grid cols-{cols}">{imgs_html}
    </div>
  </section>"""

    return html_out


# ---------------------------------------------------------------------------
# GENERADOR HTML PRINCIPAL
# ---------------------------------------------------------------------------

def generate_html(
    report_title: str,
    file_id: str,
    df: pd.DataFrame,
    sections_html: str,
    top_videos_html: str,
    extra_insights_html: str,
    now: str,
) -> str:

    # ── KPIs ─────────────────────────────────────────────────────────────
    total_videos   = len(df)
    total_views    = col_sum(df, "video_vistas")
    total_likes    = col_sum(df, "video_likes")
    total_comments = col_sum(df, "video_comentarios")
    total_shares   = col_sum(df, "video_compartidos")
    total_saves    = col_sum(df, "video_guardados")
    avg_views      = int(total_views / total_videos) if total_videos else 0
    # Fórmula unificada: likes + comentarios + compartidos + guardados (igual que insights)
    engagement     = (
        (total_likes + total_comments + total_shares + total_saves) / total_views * 100
        if total_views else 0
    )

    kpi_html = f"""
    <div class="kpi-grid">
      {build_kpi_card("🎬", fmt_num(total_videos),   "Videos")}
      {build_kpi_card("👁",  fmt_num(total_views),    "Vistas Totales",    highlight=True)}
      {build_kpi_card("❤️", fmt_num(total_likes),    "Likes")}
      {build_kpi_card("💬", fmt_num(total_comments), "Comentarios")}
      {build_kpi_card("↗️", fmt_num(total_shares),   "Compartidos")}
      {build_kpi_card("🔖", fmt_num(total_saves),    "Guardados")}
      {build_kpi_card("📈", fmt_num(avg_views),      "Media Vistas/Video")}
      {build_kpi_card("📊", f"{engagement:.2f}%",    "Engagement Rate",   highlight=True)}
    </div>"""

    # ── CSS (embebido) ────────────────────────────────────────────────────
    css = """
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --bg:      #010101;
  --surface: #161823;
  --card:    #1f2029;
  --border:  #2e3040;
  --primary: #fe2c55;
  --cyan:    #25f4ee;
  --text:    #ffffff;
  --muted:   #8a8b91;
  --radius:  12px;
  --shadow:  0 4px 24px rgba(0,0,0,.6);
}

body {
  background: var(--bg);
  color: var(--text);
  font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
  font-size: 15px;
  line-height: 1.6;
}

/* ── HEADER ─────────────────────────────────────────────────── */
header {
  background: linear-gradient(160deg, #0d0d0d 0%, #1a0a12 45%, #091520 100%);
  border-bottom: 1px solid var(--border);
  padding: 60px 40px 52px;
  text-align: center;
  position: relative;
  overflow: hidden;
}
header::before {
  content: '';
  position: absolute; top: -110px; left: 50%; transform: translateX(-50%);
  width: 800px; height: 400px;
  background: radial-gradient(ellipse, rgba(254,44,85,.18) 0%, transparent 65%);
  pointer-events: none;
}
header::after {
  content: '';
  position: absolute; bottom: -90px; right: 5%;
  width: 550px; height: 280px;
  background: radial-gradient(ellipse, rgba(37,244,238,.10) 0%, transparent 65%);
  pointer-events: none;
}
.eyebrow {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 4px;
  text-transform: uppercase;
  color: var(--muted);
  margin-bottom: 18px;
}
.eyebrow em { color: var(--primary); font-style: normal; }

header h1 {
  font-size: clamp(34px, 6vw, 64px);
  font-weight: 900;
  letter-spacing: -2px;
  line-height: 1.05;
  position: relative;
}
header h1 .at  { color: var(--cyan); }

.header-credit {
  position: absolute;
  right: 28px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--muted);
  font-size: 14px;
  font-weight: 600;
  letter-spacing: 1px;
  z-index: 1;
  line-height: 1.4;
  text-align: right;
}
.header-credit .at { color: var(--cyan); }

.badge {
  display: inline-block;
  margin-top: 12px;
  padding: 4px 12px;
  background: rgba(37,244,238,.12);
  border: 1px solid rgba(37,244,238,.35);
  border-radius: 20px;
  font-size: 11px;
  color: var(--cyan);
  letter-spacing: 1.2px;
  font-weight: 600;
}
.meta {
  margin-top: 16px;
  color: var(--muted);
  font-size: 13px;
}

/* ── MAIN ───────────────────────────────────────────────────── */
main {
  max-width: 1200px;
  margin: 0 auto;
  padding: 52px 24px 80px;
}
section {
  margin-bottom: 64px;
}
section h2 {
  font-size: 19px;
  font-weight: 700;
  color: var(--text);
  margin-bottom: 22px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--border);
}
.acc-p { color: var(--primary); margin-right: 9px; }
.acc-c { color: var(--cyan);    margin-right: 9px; }

/* ── KPI CARDS ──────────────────────────────────────────────── */
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 14px;
}
.kpi {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 22px 14px 18px;
  text-align: center;
  transition: transform .2s ease, border-color .2s ease, box-shadow .2s ease;
}
.kpi:hover {
  transform: translateY(-4px);
  border-color: var(--primary);
  box-shadow: 0 8px 32px rgba(254,44,85,.18);
}
.kpi.highlight {
  border-color: rgba(37,244,238,.35);
  background: linear-gradient(135deg, #1f2029 0%, #162230 100%);
}
.kpi.highlight:hover {
  border-color: var(--cyan);
  box-shadow: 0 8px 32px rgba(37,244,238,.18);
}
.kpi-icon  { font-size: 24px; margin-bottom: 9px; }
.kpi-value {
  font-size: 28px;
  font-weight: 800;
  line-height: 1;
  color: var(--text);
}
.kpi.highlight .kpi-value { color: var(--cyan); }
.kpi-label {
  font-size: 11px;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 1.2px;
  margin-top: 7px;
}

/* ── TOP VIDEOS TABLE ───────────────────────────────────────── */
.table-wrap {
  border-radius: var(--radius);
  border: 1px solid var(--border);
  overflow-x: auto;
  box-shadow: var(--shadow);
}
table  { width: 100%; border-collapse: collapse; }
thead tr { background: var(--surface); }
th, td {
  padding: 13px 16px;
  text-align: left;
  font-size: 13px;
  border-bottom: 1px solid var(--border);
}
th {
  color: var(--muted);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: .8px;
  white-space: nowrap;
}
tbody tr { background: var(--card); transition: background .15s; }
tbody tr:last-child td { border-bottom: none; }
tbody tr:hover { background: #252733; }
td.rank {
  font-weight: 900;
  font-size: 18px;
  color: var(--primary);
  width: 48px;
}
td.desc a { color: var(--text); text-decoration: none; }
td.desc a:hover { color: var(--cyan); text-decoration: underline; }
td.num   { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
td.views { color: var(--cyan); font-weight: 700; }
td.fecha { color: var(--muted); white-space: nowrap; font-size: 12px; }

/* ── INSIGHTS AVANZADOS ────────────────────────────────────── */
.insight-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}
.insight-card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 18px 18px 14px;
}
.insight-card h3 {
  font-size: 14px;
  margin-bottom: 10px;
  color: var(--cyan);
}
.insight-card p {
  margin-bottom: 7px;
  font-size: 13px;
}
.insight-card p strong { color: var(--text); }
.insight-card .muted {
  color: var(--muted);
  margin-top: 3px;
}
.span-2 { grid-column: span 2; }

.pill-wrap {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.tag-pill {
  border: 1px solid var(--border);
  background: var(--surface);
  border-radius: 999px;
  padding: 4px 10px;
  font-size: 12px;
  color: var(--text);
}
.tag-pill em {
  color: var(--cyan);
  font-style: normal;
  margin-left: 4px;
}
.callout {
  margin-top: 12px;
  background: rgba(37,244,238,.08);
  border: 1px solid rgba(37,244,238,.3);
  border-radius: 10px;
  padding: 10px 12px;
  font-size: 13px;
}

.mini-table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 4px;
}
.mini-table th,
.mini-table td {
  font-size: 12px;
  padding: 8px 10px;
  border-bottom: 1px solid var(--border);
}
.mini-table th {
  text-transform: uppercase;
  color: var(--muted);
  letter-spacing: .5px;
  text-align: left;
}
.mini-table tr:last-child td { border-bottom: none; }

/* ── IMAGE GRID ─────────────────────────────────────────────── */
.grid { display: grid; gap: 18px; }
.cols-1 { grid-template-columns: 1fr; }
.cols-2 { grid-template-columns: repeat(2, 1fr); }
.cols-3 { grid-template-columns: repeat(3, 1fr); }

figure {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
  box-shadow: var(--shadow);
  transition: border-color .25s ease, transform .25s ease, box-shadow .25s ease;
}
figure:hover {
  border-color: var(--primary);
  transform: translateY(-3px);
  box-shadow: 0 12px 40px rgba(254,44,85,.2);
}
figure img { width: 100%; display: block; }
figcaption {
  padding: 10px 14px;
  font-size: 11px;
  color: var(--muted);
  text-align: center;
  text-transform: uppercase;
  letter-spacing: 1px;
  border-top: 1px solid var(--border);
}

/* ── FOOTER ─────────────────────────────────────────────────── */
footer {
  text-align: center;
  padding: 32px 20px;
  border-top: 1px solid var(--border);
  color: var(--muted);
  font-size: 12px;
}
footer strong { color: var(--primary); }

/* ── RESPONSIVE ─────────────────────────────────────────────── */
@media (max-width: 900px) {
  .cols-3 { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 600px) {
  .cols-2, .cols-3 { grid-template-columns: 1fr; }
  .kpi-grid { grid-template-columns: repeat(2, 1fr); }
  .insight-grid { grid-template-columns: 1fr; }
  .span-2 { grid-column: span 1; }
  header { padding: 40px 20px; }
  main   { padding: 32px 16px 60px; }
}
"""

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>TikTok Analytics · {report_title}</title>
  <style>{css}</style>
</head>
<body>

<header>
  <div class="header-credit"><span class="at">@</span>barripdmx</div>
  <p class="eyebrow">Tik<em>Tok</em> Analytics Report</p>
  <h1>{report_title}</h1>
  <p class="meta">Análisis de publicaciones &middot; Generado el {now}</p>
</header>

<main>

  <!-- ── RESUMEN GENERAL ───────────────────────────────────── -->
  <section>
    <h2><span class="acc-p">★</span> Resumen General</h2>
    {kpi_html}
  </section>

  <!-- ── TOP 5 VIDEOS ──────────────────────────────────────── -->
  {top_videos_html}

  <!-- ── INSIGHTS AVANZADOS ────────────────────────────────── -->
  {extra_insights_html}

  <!-- ── SECCIONES DE GRÁFICAS ─────────────────────────────── -->
  {sections_html}

</main>

<footer>
  Informe generado automáticamente &middot;
  <strong>TikTok Analytics</strong> &middot; {now}
</footer>

</body>
</html>"""


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    args = _parse_args()

    print("=" * 52)
    print("  GENERADOR DE INFORME HTML — TikTok Analytics")
    print("=" * 52)

    csv_path = get_file_path(args.csv)
    if not csv_path:
        print("Operación cancelada.")
        return

    base_name = os.path.basename(csv_path)
    file_id   = os.path.splitext(base_name)[0]
    print(f"\n📂 Archivo : {base_name}")

    # ── Rutas de salida basadas en proyecto ───────────────────────────────
    global OUTPUT_FOLDER, INFORMES_FOLDER
    _project = file_id.split("_videos")[0] if "_videos" in file_id else file_id
    OUTPUT_FOLDER   = os.path.join(OUTPUTS_BASE, _project, "publicaciones")
    INFORMES_FOLDER = os.path.join(OUTPUTS_BASE, _project, "informes")
    os.makedirs(OUTPUT_FOLDER,   exist_ok=True)
    os.makedirs(INFORMES_FOLDER, exist_ok=True)
    print(f"   Imágenes : {OUTPUT_FOLDER}")
    print(f"   Informe  : {INFORMES_FOLDER}")

    try:
        try:
            df = pd.read_csv(csv_path, encoding="utf-8-sig")
        except Exception:
            df = pd.read_csv(csv_path, encoding="utf-8", errors="ignore")
        print(f"   {len(df)} registros cargados.")
    except Exception as e:
        print(f"❌ Error leyendo CSV: {e}")
        return

    # ── Deduplicar por video_id antes de cualquier cálculo ───────────────
    if "video_id" in df.columns:
        before_dedup = len(df)
        df = df.drop_duplicates(subset=["video_id"])
        dropped = before_dedup - len(df)
        if dropped:
            print(f"   ⚠️  {dropped} filas duplicadas eliminadas → {len(df)} videos únicos.")

    # ── Preguntar título del informe ─────────────────────────────────────
    default_title = derive_title(file_id)
    report_title = get_report_title(default_title, args.titulo)
    print(f"   Título   : {report_title}")

    # ── Generar gráficas base automáticamente ─────────────────────────────
    ensure_report_images(file_id, df)

    # ── Buscar imágenes ──────────────────────────────────────────────────
    print(f"\n📸 Buscando imágenes en '{OUTPUT_FOLDER}/'...")

    now             = fecha_es()
    sections_html   = build_image_sections(file_id)
    top_videos_html = build_top_videos(df)
    extra_insights_html = build_extra_insights(df, report_title)

    # ── Generar HTML ─────────────────────────────────────────────────────
    html_content = generate_html(
        report_title,
        file_id, df,
        sections_html, top_videos_html,
        extra_insights_html,
        now,
    )

    # ── Guardar ──────────────────────────────────────────────────────────
    os.makedirs(INFORMES_FOLDER, exist_ok=True)
    output_path = os.path.join(INFORMES_FOLDER, f"{file_id}_informe.html")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"\n✅ Informe generado: {output_path}")
    print(f"   Ábrelo directamente en tu navegador.")


if __name__ == "__main__":
    main()
