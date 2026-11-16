# -*- coding: utf-8 -*-
"""Informe forense de publicaciones o comentarios: resume las columnas nuevas y señala lo anómalo.

    python src/analysis/informe_forense.py [archivo.csv] [--archivo ruta.csv] [--tipo publicaciones|comentarios]

El tipo se deduce de las columnas (video_vistas → publicaciones, comment_id → comentarios).
Escribe data/{proyecto}/informes/{nombre}_forense.html (autocontenido) y un resumen por consola.
Cada hallazgo es un INDICIO a revisar, no una conclusión: las etiquetas de infraestructura (cluster/bucket CDN)
no son ubicación (ver CLAUDE.md).
"""
import argparse
import html
import os
import sys
from datetime import datetime

import numpy as np
import pandas as pd

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, RAIZ)
from config.rutas import derivar_proyecto, dir_informes  # noqa: E402

MESES_ES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
            "octubre", "noviembre", "diciembre"]
VERDADERO = {"true", "1", "1.0", "si", "sí"}


def miles(n) -> str:
    return f"{int(n):,}".replace(",", ".")


def pct(a, b) -> str:
    return f"{100 * a / b:.1f}".replace(".", ",") + " %" if b else "—"


def col(df: pd.DataFrame, nombre: str) -> pd.Series:
    """Columna como texto; vacía si el archivo no la trae (capturas anteriores a las columnas nuevas)."""
    return df[nombre].fillna("").astype(str) if nombre in df.columns else pd.Series([""] * len(df), index=df.index)


def num(df, nombre) -> pd.Series:
    return pd.to_numeric(col(df, nombre).str.replace(",", ".", regex=False), errors="coerce")


def fecha(df, nombre) -> pd.Series:
    return pd.to_datetime(col(df, nombre), format="%Y-%m-%d %H:%M:%S", errors="coerce")


def es_si(s: pd.Series) -> pd.Series:
    return s.str.strip().str.lower().isin(VERDADERO)


def atipicos(s: pd.Series, k: float = 3.5) -> pd.Series:
    """True donde el valor se sale mucho de la mediana (z robusto con MAD) sobre log1p."""
    x = np.log1p(s.astype(float).clip(lower=0))
    med = x.median()
    mad = (x - med).abs().median()
    if not mad or pd.isna(mad):
        return pd.Series(False, index=s.index)
    return ((x - med).abs() * 0.6745 / mad) > k


class Informe:
    def __init__(self, titulo: str, total: int):
        self.titulo, self.total = titulo, total
        self.resumen: list = []   # (etiqueta, valor)
        self.hallazgos: list = []  # (severidad, titulo, texto, DataFrame|None)
        self.tablas: list = []     # (titulo, DataFrame)

    def dato(self, etiqueta, valor):
        self.resumen.append((etiqueta, valor))

    def hallazgo(self, sev: str, titulo: str, texto: str, filas: pd.DataFrame | None = None):
        self.hallazgos.append((sev, titulo, texto, filas))

    def tabla(self, titulo: str, df: pd.DataFrame):
        self.tablas.append((titulo, df))


def distribucion(s: pd.Series, top: int = 8) -> pd.DataFrame:
    s = s[s != ""]
    c = s.value_counts().head(top)
    return pd.DataFrame({"valor": c.index, "n": c.values, "%": [pct(v, len(s)) for v in c.values]})


def minoritarios(s: pd.Series, umbral: float = 0.05) -> list:
    s = s[s != ""]
    c = s.value_counts()
    return [v for v, n in c.items() if n / max(len(s), 1) < umbral] if len(s) >= 20 else []


# ---------------------------------------------------------------------------
# Publicaciones
# ---------------------------------------------------------------------------

def analizar_publicaciones(df: pd.DataFrame, rep: Informe) -> None:
    n = len(df)
    cols_vis = [c for c in ("video_id", "video_fecha", "video_vistas", "video_likes", "username") if c in df.columns]
    rep.dato("Publicaciones", miles(n))
    rep.dato("Cuentas distintas", miles(col(df, "username").nunique()))
    d = fecha(df, "video_fecha_utc")
    if d.notna().any():
        rep.dato("Periodo (UTC)", f"{d.min():%d-%m-%Y} a {d.max():%d-%m-%Y}")

    desfase = num(df, "desfase_subida_seg")
    m = (desfase > 86400) | es_si(col(df, "inferencia_programado"))
    if m.any():
        rep.hallazgo("medio", "Publicados mucho después de crearse el vídeo",
                     f"{int(m.sum())} de {n}: la fecha de publicación es más de un día posterior a la de creación del id "
                     "(borrador, programado o subida tardía).",
                     df.loc[m, cols_vis].assign(desfase_horas=(desfase[m] / 3600).round(1)))

    estado = pd.DataFrame({"retirado": es_si(col(df, "retirado")), "prohibido": es_si(col(df, "prohibido")),
                           "en_revision": es_si(col(df, "en_revision"))})
    m = estado.any(axis=1)
    if m.any():
        rep.hallazgo("alto", "Moderación: retirados, prohibidos o en revisión",
                     f"{int(m.sum())} publicaciones con alguna marca activa.",
                     df.loc[m, cols_vis].join(estado[m]))
    m = col(df, "banner_institucional_key") != ""
    if m.any():
        rep.hallazgo("medio", "Banner institucional o aviso de TikTok",
                     f"{int(m.sum())} publicaciones muestran un aviso.", df.loc[m, cols_vis + ["banner_institucional_key"]])
    lat = num(df, "latencia_moderacion_seg")
    m = atipicos(lat.where(lat > 0)).fillna(False)
    if m.any():
        rep.hallazgo("bajo", "Latencia de moderación atípica",
                     "Segundos entre la creación y la conclusión de la moderación, fuera de lo habitual del archivo.",
                     df.loc[m, cols_vis].assign(latencia_horas=(lat[m] / 3600).round(1)))

    m = es_si(col(df, "es_aigc")) | (col(df, "aviso_ia") != "")
    if m.any():
        rep.hallazgo("medio", "Contenido marcado como generado con IA", f"{int(m.sum())} publicaciones.", df.loc[m, cols_vis])
    m = es_si(col(df, "es_anuncio"))
    if m.any():
        rep.hallazgo("medio", "Anuncios", f"{int(m.sum())} publicaciones marcadas como anuncio.", df.loc[m, cols_vis])

    vistas, likes = num(df, "video_vistas"), num(df, "video_likes")
    com, comp = num(df, "video_comentarios"), num(df, "video_compartidos")
    for nombre, serie in (("likes / vistas", likes / vistas), ("comentarios / vistas", com / vistas),
                          ("compartidos / vistas", comp / vistas)):
        serie = serie.replace([float("inf")], pd.NA).astype(float)
        m = atipicos(serie * 1000).fillna(False)
        if m.any():
            rep.hallazgo("bajo", f"Ratio atípico: {nombre}",
                         f"{int(m.sum())} publicaciones con un ratio muy distinto de la mediana (posible impulso o compra de interacción, "
                         "o un vídeo realmente viral).",
                         df.loc[m, cols_vis].assign(ratio=(serie[m] * 100).round(2).astype(str) + " %"))
    reposts = num(df, "video_reposts")
    if reposts.notna().any():
        rep.dato("Reposts totales", miles(reposts.sum()))

    if "autor_fecha_creacion_cuenta" in df.columns:
        cr = fecha(df, "autor_fecha_creacion_cuenta")
        m = cr.notna() & d.notna() & (cr > d)
        if m.any():
            rep.hallazgo("alto", "Vídeo anterior a la creación de la cuenta",
                         "La fecha de creación de la cuenta es posterior a la del vídeo: cuenta recreada o dato incoherente.",
                         df.loc[m, cols_vis].assign(cuenta_creada=cr[m].astype(str)))
        reciente = cr.notna() & d.notna() & ((d - cr).dt.days < 30)
        if reciente.any():
            rep.hallazgo("medio", "Publicaciones de cuentas de menos de 30 días",
                         f"{int(reciente.sum())} publicaciones de cuentas creadas el mes anterior.",
                         df.loc[reciente, cols_vis].assign(cuenta_creada=cr[reciente].astype(str)))
        c = cr.dt.year.value_counts().sort_index()
        rep.tabla("Cohorte: año de creación de la cuenta del autor",
                  pd.DataFrame({"año": c.index.astype(int), "publicaciones": c.values}))

    for nombre, etiqueta in (("cdn_cluster_video", "Clúster CDN del vídeo"), ("video_bucket_suffix", "Sufijo de bucket del vídeo"),
                             ("cdn_cluster_audio", "Clúster CDN del audio")):
        s = col(df, nombre)
        if (s != "").any():
            rep.tabla(etiqueta + " (etiqueta de infraestructura, no ubicación)", distribucion(s))
            raros = minoritarios(s)
            if raros:
                rep.hallazgo("bajo", f"Valores minoritarios en «{nombre}»",
                             f"Menos del 5 % del archivo: {', '.join(raros)}. Solo es útil como contraste dentro de una misma cohorte.",
                             df.loc[s.isin(raros), cols_vis + [nombre]])
    for nombre, etiqueta in (("pais_creacion", "País atribuido por TikTok"), ("idioma_texto", "Idioma del texto")):
        if (col(df, nombre) != "").any():
            rep.tabla(etiqueta, distribucion(col(df, nombre)))
    dup = col(df, "video_desc").str.strip()
    dup = dup[dup != ""]
    rep_desc = dup[dup.duplicated(keep=False)]
    if len(rep_desc):
        top = rep_desc.value_counts().head(10)
        rep.hallazgo("medio", "Descripciones idénticas en varios vídeos", f"{len(rep_desc)} publicaciones comparten texto.",
                     pd.DataFrame({"descripción": [t[:90] for t in top.index], "veces": top.values}))
    mus = col(df, "music_id")
    mus = mus[mus != ""]
    if len(mus):
        top = mus.value_counts().head(5)
        if top.iloc[0] >= max(5, 0.2 * len(mus)):
            rep.hallazgo("bajo", "Un mismo audio concentra muchas publicaciones",
                         f"El audio {top.index[0]} aparece en {top.iloc[0]} de {len(mus)} publicaciones.", None)


# ---------------------------------------------------------------------------
# Comentarios
# ---------------------------------------------------------------------------

def analizar_comentarios(df: pd.DataFrame, rep: Informe) -> None:
    n = len(df)
    rep.dato("Comentarios", miles(n))
    rep.dato("Vídeos", miles(col(df, "video_id").nunique()))
    uid = col(df, "autor_uid").where(col(df, "autor_uid") != "", col(df, "autor_handle"))
    rep.dato("Autores distintos", miles(uid.nunique()))
    f = fecha(df, "comment_fecha_utc")
    if f.notna().any():
        rep.dato("Periodo (UTC)", f"{f.min():%d-%m-%Y} a {f.max():%d-%m-%Y}")
    cv = ["video_id", "autor_handle", "comment_fecha_utc", "texto"]
    cv = [c for c in cv if c in df.columns]

    # Autores que repiten
    c = uid.value_counts()
    top = c[c >= max(5, 0.01 * n)]
    if len(top):
        rep.hallazgo("medio", "Autores con muchos comentarios",
                     f"{len(top)} autores concentran {pct(top.sum(), n)} del total.",
                     pd.DataFrame({"autor": top.index[:10], "comentarios": top.values[:10]}))

    # Texto idéntico entre autores distintos (copypasta)
    t = col(df, "texto").str.strip().str.lower()
    g = df.assign(_t=t, _u=uid)[t.str.len() >= 15].groupby("_t")["_u"].agg(["nunique", "size"])
    g = g[(g["nunique"] >= 3)].sort_values("size", ascending=False)
    if len(g):
        rep.hallazgo("alto", "Mismo texto desde cuentas distintas",
                     f"{len(g)} textos (≥15 caracteres) repetidos por 3 o más autores: posible copia coordinada.",
                     pd.DataFrame({"texto": [x[:90] for x in g.index[:10]], "autores": g["nunique"].values[:10],
                                   "veces": g["size"].values[:10]}))

    # Ráfagas: mismo minuto
    if f.notna().any():
        por_min = f.dt.floor("min").value_counts()
        base = por_min.median()
        picos = por_min[por_min >= max(10, 5 * base)]
        if len(picos):
            rep.hallazgo("medio", "Ráfagas de comentarios en un minuto",
                         f"{len(picos)} minutos con 5 veces más comentarios de lo normal (mediana {base:.0f}/min).",
                         pd.DataFrame({"minuto_utc": picos.index.astype(str)[:10], "comentarios": picos.values[:10]}))
        h = f.dt.hour.value_counts().sort_index()
        rep.tabla("Comentarios por hora UTC", pd.DataFrame({"hora": h.index, "comentarios": h.values}))

    # Fecha de la API frente a fecha del snowflake del comentario
    snow = fecha(df, "comment_snowflake_utc")
    dif = (f - snow).dt.total_seconds().abs()
    m = dif > 120
    if m.any():
        rep.hallazgo("bajo", "Fecha del comentario y de su id no coinciden",
                     f"{int(m.sum())} comentarios con más de 2 minutos de diferencia (poco habitual).",
                     df.loc[m, cv].assign(dif_seg=dif[m].round(0)))

    # Cuentas nuevas respecto del comentario
    cr = fecha(df, "autor_fecha_creacion_cuenta")
    nuevas = cr.notna() & f.notna() & ((f - cr).dt.days < 30)
    if nuevas.any():
        rep.hallazgo("medio", "Comentarios de cuentas de menos de 30 días",
                     f"{int(nuevas.sum())} comentarios ({pct(nuevas.sum(), n)}) de cuentas creadas el mes anterior.",
                     df.loc[nuevas, cv].assign(cuenta_creada=cr[nuevas].astype(str)).head(30))
    incoh = cr.notna() & f.notna() & (cr > f)
    if incoh.any():
        rep.hallazgo("alto", "Comentario anterior a la creación de la cuenta",
                     f"{int(incoh.sum())} casos: cuenta recreada o dato incoherente.",
                     df.loc[incoh, cv].assign(cuenta_creada=cr[incoh].astype(str)).head(30))
    if cr.notna().any():
        c = cr.dt.year.value_counts().sort_index()
        rep.tabla("Cohorte: año de creación de la cuenta del comentarista",
                  pd.DataFrame({"año": c.index.astype(int), "comentarios": c.values}))

    # Etiquetas de infraestructura
    cl = col(df, "autor_cluster_cdn")
    if (cl != "").any():
        rep.tabla("Clúster CDN del avatar (etiqueta de infraestructura, no ubicación)", distribucion(cl))
    leg = es_si(col(df, "autor_avatar_legacy_musically"))
    if leg.any():
        rep.hallazgo("bajo", "Avatares de la etapa Musical.ly",
                     f"{int(leg.sum())} comentarios con avatar legacy: cuenta antigua que no ha cambiado la foto.", None)
    ip = col(df, "comment_ip_label")
    if (ip != "").any():
        rep.tabla("Etiqueta de ubicación del comentario (comment_ip_label)", distribucion(ip))
    idi = col(df, "comment_idioma")
    if (idi != "").any():
        rep.tabla("Idioma del comentario", distribucion(idi))
        dom = idi[idi != ""].value_counts()
        raros = [v for v in minoritarios(idi, 0.03) if v not in ("und", "")]
        if raros and len(dom):
            rep.dato("Idioma dominante", f"{dom.index[0]} ({pct(dom.iloc[0], dom.sum())})")

    # Likes atípicos, creador, fijado
    lk = num(df, "likes")
    m = atipicos(lk).fillna(False) & (lk >= 50)
    if m.any():
        rep.hallazgo("bajo", "Comentarios con likes atípicos", f"{int(m.sum())} comentarios muy por encima de la mediana.",
                     df.loc[m, cv].assign(likes=lk[m].astype(int)).sort_values("likes", ascending=False).head(15))
    rep.dato("Con like del creador", miles(es_si(col(df, "like_del_creador")).sum()))
    rep.dato("Fijados", miles(es_si(col(df, "comentario_fijado")).sum()))
    r = num(df, "total_respuestas_hilo").fillna(0)
    if (r > 0).any():
        m = r >= r.quantile(0.99)
        rep.hallazgo("bajo", "Hilos con más respuestas",
                     "Comentarios con más respuestas del archivo (candidatos a debate o a brigada).",
                     df.loc[m & (r >= 5), cv].assign(respuestas=r[m & (r >= 5)].astype(int)).sort_values("respuestas", ascending=False).head(10))


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

CSS = """body{font-family:Segoe UI,Arial,sans-serif;background:#fff;color:#010101;margin:0;padding:0 24px 48px}
header{background:#010101;color:#fff;padding:20px 24px;margin:0 -24px 24px;border-bottom:4px solid #fe2c55}
h1{margin:0;font-size:24px}h2{border-left:5px solid #fe2c55;padding-left:10px;margin-top:32px}
.sub{color:#25f4ee;font-size:13px;margin-top:4px}.kpi{display:flex;flex-wrap:wrap;gap:12px}
.k{border:1px solid #ebebeb;border-radius:8px;padding:10px 16px}.k b{display:block;font-size:20px}
.h{border:1px solid #ebebeb;border-left-width:6px;border-radius:6px;padding:10px 14px;margin:14px 0}
.alto{border-left-color:#fe2c55}.medio{border-left-color:#f5a623}.bajo{border-left-color:#8a8a8a}
.h h3{margin:0 0 4px;font-size:16px}.tag{font-size:11px;text-transform:uppercase;color:#666}
table{border-collapse:collapse;font-size:12px;margin-top:8px;max-width:100%}th,td{border:1px solid #ebebeb;padding:4px 8px;text-align:left;vertical-align:top}
th{background:#f6f6f6}.nota{font-size:12px;color:#555;margin-top:32px}"""


def tabla_html(df: pd.DataFrame, max_filas: int = 20) -> str:
    if df is None or df.empty:
        return ""
    df = df.head(max_filas)
    cab = "".join(f"<th>{html.escape(str(c))}</th>" for c in df.columns)
    filas = "".join("<tr>" + "".join(f"<td>{html.escape(str(v))[:160]}</td>" for v in r) + "</tr>"
                    for r in df.itertuples(index=False))
    return f"<table><tr>{cab}</tr>{filas}</table>"


def a_html(rep: Informe, nombre_csv: str) -> str:
    hoy = datetime.now()
    orden = {"alto": 0, "medio": 1, "bajo": 2}
    hs = sorted(rep.hallazgos, key=lambda h: orden[h[0]])
    kpi = "".join(f'<div class="k">{html.escape(a)}<b>{html.escape(str(v))}</b></div>' for a, v in rep.resumen)
    bloques = "".join(
        f'<div class="h {s}"><span class="tag">Prioridad {s}</span><h3>{html.escape(t)}</h3><div>{html.escape(x)}</div>{tabla_html(df)}</div>'
        for s, t, x, df in hs) or "<p>No se han detectado elementos fuera de lo habitual con estas reglas.</p>"
    tablas = "".join(f"<h3>{html.escape(t)}</h3>{tabla_html(d)}" for t, d in rep.tablas)
    return (f'<!doctype html><html lang="es"><head><meta charset="utf-8"><title>{html.escape(rep.titulo)}</title>'
            f"<style>{CSS}</style></head><body><header><h1>{html.escape(rep.titulo)}</h1>"
            f'<div class="sub">Archivo: {html.escape(nombre_csv)} · {hoy.day} de {MESES_ES[hoy.month - 1]} de {hoy.year} · @barripdmx</div></header>'
            f"<div class=\"kpi\">{kpi}</div><h2>Elementos a revisar ({len(hs)})</h2>{bloques}"
            f"<h2>Distribuciones</h2>{tablas}"
            '<p class="nota">Cada hallazgo es un indicio, no una conclusión. El clúster y el bucket CDN son etiquetas internas de '
            "almacenamiento de TikTok, sin significado geográfico documentado: sirven para comparar cohortes y detectar valores "
            "fuera de lo habitual dentro de una misma cohorte, nunca como ubicación.</p></body></html>")


def detectar_tipo(df: pd.DataFrame) -> str:
    if "comment_id" in df.columns:
        return "comentarios"
    if "video_vistas" in df.columns:
        return "publicaciones"
    raise SystemExit("No reconozco el archivo: no es un CSV de publicaciones ni de comentarios de este toolkit.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("csv", nargs="?")
    ap.add_argument("--archivo")
    ap.add_argument("--tipo", choices=["publicaciones", "comentarios"])
    ap.add_argument("--no-prompt", action="store_true")
    a = ap.parse_args()
    ruta = a.archivo or a.csv
    if not ruta or not os.path.isfile(ruta):
        print("❌ Indica un CSV existente (argumento o --archivo).")
        return 1
    df = pd.read_csv(ruta, encoding="utf-8-sig", dtype=str, keep_default_na=False)
    tipo = a.tipo or detectar_tipo(df)
    base = os.path.splitext(os.path.basename(ruta))[0]
    rep = Informe(f"Informe forense de {tipo}", len(df))
    (analizar_publicaciones if tipo == "publicaciones" else analizar_comentarios)(df, rep)
    # Junto al CSV: data/{proyecto}/... → su propia carpeta; si no, se deriva del nombre.
    partes = os.path.abspath(ruta).split(os.sep)
    datos = os.path.join(RAIZ, "data")
    if os.path.abspath(ruta).startswith(datos + os.sep) and len(partes) > len(datos.split(os.sep)) + 1:
        proyecto = partes[len(datos.split(os.sep))]
    else:
        proyecto = derivar_proyecto(base)
    salida = os.path.join(dir_informes(proyecto), f"{base}_forense.html")
    os.makedirs(os.path.dirname(salida), exist_ok=True)
    with open(salida, "w", encoding="utf-8") as f:
        f.write(a_html(rep, os.path.basename(ruta)))
    print(f"Tipo: {tipo} | filas: {len(df)}")
    for sev, t, x, _ in sorted(rep.hallazgos, key=lambda h: {"alto": 0, "medio": 1, "bajo": 2}[h[0]]):
        print(f"  [{sev.upper():5}] {t}: {x}")
    if not rep.hallazgos:
        print("  Sin elementos fuera de lo habitual.")
    print(f"📄 Informe: {salida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
