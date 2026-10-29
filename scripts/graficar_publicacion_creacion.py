"""Relaciona publicación y creación de cuentas de autores y comentaristas."""

from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import plotly.graph_objects as go


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "blocus" / "datos" / "comentarios_blocus_20261026"
USERS = ROOT / "data" / "blocus" / "datos" / "usuarios_fecha_creacion" / "usuarios_por_fecha_creacion.csv"
DEST = ROOT / "data" / "blocus" / "graficas" / "analisis_publicacion_creacion_20261026"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def date_from_id(value: str) -> datetime:
    return datetime.fromtimestamp(int(value) >> 32, timezone.utc)


def iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def build_points(publications: list[dict[str, str]], comments: list[dict[str, str]],
                 users: list[dict[str, str]], accounts: list[dict[str, str]]) -> tuple[list[dict], list[dict], dict]:
    by_user_id = {row["user_id"]: row for row in users}
    by_account = {}
    for row in accounts:
        for name in (row["objetivo"], row["username"], *row["aliases"].split(", ")):
            if name:
                by_account[name.lower()] = row
    publishers = []
    post_meta = {}
    for post in publications:
        pid = post["id"]
        account = post["cuenta"].lower()
        owner = by_account.get(account)
        if owner is None:
            raise ValueError(f"Cuenta publicadora sin identidad: {account}")
        published = date_from_id(pid)
        if not owner["fecha_creacion_perfil_utc"]:
            raise ValueError(f"Sin fecha confirmada para el perfil publicador: {account}")
        point = {"publicacion_id": pid, "cuenta_publicadora": account,
                 "publicacion_url": post["url"], "fecha_publicacion_estimada_utc": published.isoformat(),
                 "usuario_id": owner["user_id"], "usuario": owner["username"],
                 "fecha_creacion_utc": owner["fecha_creacion_perfil_utc"],
                 "tipo_fecha_creacion": "Confirmada por perfil"}
        publishers.append(point)
        post_meta[pid] = point

    unique: dict[tuple[str, str], dict] = {}
    invalid_comment_order = 0
    for row in comments:
        pid, uid = row["publication_id"], row["autor_id"]
        post = post_meta.get(pid)
        if post is None:
            raise ValueError(f"Comentario de publicación fuera del inventario: {pid}")
        if iso(row["creado_utc"]) < iso(post["fecha_publicacion_estimada_utc"]):
            invalid_comment_order += 1
        key = (pid, uid)
        if key not in unique:
            user = by_user_id[uid]
            unique[key] = {"publicacion_id": pid, "cuenta_publicadora": post["cuenta_publicadora"],
                           "publicacion_url": post["publicacion_url"],
                           "fecha_publicacion_estimada_utc": post["fecha_publicacion_estimada_utc"],
                           "usuario_id": uid, "usuario": user["usuario"],
                           "fecha_creacion_utc": user["fecha_orden_utc"],
                           "tipo_fecha_creacion": user["tipo_fecha"],
                           "comentarios_observados": 0,
                           "primer_comentario_utc": row["creado_utc"]}
        point = unique[key]
        point["comentarios_observados"] += 1
        point["primer_comentario_utc"] = min(point["primer_comentario_utc"], row["creado_utc"])
    commenters = list(unique.values())
    dated = [p for p in commenters if p["fecha_creacion_utc"]]
    created_after_post = sum(iso(p["fecha_creacion_utc"]) > iso(p["fecha_publicacion_estimada_utc"])
                             for p in dated)
    summary = {"publicaciones": len(publishers), "cuentas_publicadoras": len({p["cuenta_publicadora"] for p in publishers}),
               "comentarios": len(comments), "pares_publicacion_comentarista": len(commenters),
               "pares_con_fecha": len(dated),
               "pares_por_tipo_fecha": dict(Counter(p["tipo_fecha_creacion"] for p in commenters)),
               "cuentas_creadas_despues_de_publicacion": created_after_post,
               "comentarios_anteriores_a_fecha_publicacion_estimada": invalid_comment_order,
               "metodo_fecha_publicacion": "ID de publicación >> 32; estimación técnica, no campo create_time oficial"}
    return publishers, commenters, summary


def draw_png(publishers: list[dict], commenters: list[dict], summary: dict) -> None:
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10})
    fig, axes = plt.subplots(2, 1, figsize=(14, 9), sharex=True,
                             gridspec_kw={"height_ratios": [1, 1.4]})
    p_x = [iso(p["fecha_publicacion_estimada_utc"]) for p in publishers]
    p_y = [iso(p["fecha_creacion_utc"]) for p in publishers]
    axes[0].scatter(p_x, p_y, s=28, color="#CF5D29", alpha=.58, edgecolors="none")
    axes[0].set_title(f"Cuentas publicadoras · {len(publishers):,} publicaciones de {summary['cuentas_publicadoras']} cuentas",
                      loc="left", fontweight="bold")

    dated = [p for p in commenters if p["fecha_creacion_utc"]]
    estimated = [p for p in dated if p["tipo_fecha_creacion"] == "Estimada por UID"]
    confirmed = [p for p in dated if p["tipo_fecha_creacion"] == "Confirmada por perfil"]
    axes[1].scatter([iso(p["fecha_publicacion_estimada_utc"]) for p in estimated],
                    [iso(p["fecha_creacion_utc"]) for p in estimated],
                    s=8, color="#2D6DA3", alpha=.13, edgecolors="none", rasterized=True,
                    label=f"Creación estimada por ID ({len(estimated):,})")
    axes[1].scatter([iso(p["fecha_publicacion_estimada_utc"]) for p in confirmed],
                    [iso(p["fecha_creacion_utc"]) for p in confirmed],
                    s=19, color="#DA6A32", alpha=.72, edgecolors="none", rasterized=True,
                    label=f"Creación confirmada ({len(confirmed):,})")
    axes[1].set_title("Cuentas que comentan · una marca por publicación y cuenta",
                      loc="left", fontweight="bold")
    axes[1].legend(loc="upper left", frameon=False, ncol=2, fontsize=9)
    for ax in axes:
        ax.grid(color="#DCE4EC", linewidth=.65, alpha=.8)
        ax.set_axisbelow(True)
        ax.set_ylabel("Creación de la cuenta · UTC")
        ax.yaxis.set_major_locator(mdates.YearLocator())
        ax.yaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    axes[-1].xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    axes[-1].set_xlabel("Publicación · UTC (fecha estimada a partir del ID)")
    fig.suptitle("Publicación y creación de cuentas en el lote Blocus", x=.07, ha="left",
                 fontsize=17, fontweight="bold")
    fig.text(.07, .01, "Fechas de publicación: ID >> 32. Fechas de creación: perfil público o estimación UID >> 32. "
             "La coincidencia temporal no demuestra coordinación.", fontsize=9, color="#4B5563")
    fig.tight_layout(rect=(0, .035, 1, .96), h_pad=2.1)
    fig.savefig(DEST / "publicacion_vs_creacion.png", dpi=180, facecolor="white")
    plt.close(fig)


def draw_html(publishers: list[dict], commenters: list[dict]) -> None:
    fig = go.Figure()
    groups = [("Publicadores · fecha confirmada", publishers, "#CF5D29", "diamond", 10, .8),
              ("Comentaristas · fecha estimada", [p for p in commenters if p["tipo_fecha_creacion"] == "Estimada por UID"],
               "#2D6DA3", "circle", 5, .25),
              ("Comentaristas · fecha confirmada", [p for p in commenters if p["tipo_fecha_creacion"] == "Confirmada por perfil"],
               "#DA6A32", "circle", 8, .8)]
    for name, points, color, symbol, size, opacity in groups:
        custom = [[f"@{p['usuario']}", p["cuenta_publicadora"], p["publicacion_url"],
                   p["tipo_fecha_creacion"]] for p in points]
        fig.add_trace(go.Scattergl(
            x=[p["fecha_publicacion_estimada_utc"] for p in points],
            y=[p["fecha_creacion_utc"] for p in points],
            mode="markers", name=name, customdata=custom,
            marker={"color": color, "symbol": symbol, "size": size, "opacity": opacity},
            hovertemplate=("Cuenta: %{customdata[0]}<br>Publica: @%{customdata[1]}<br>"
                           "Publicación: %{x}<br>Creación: %{y}<br>"
                           "%{customdata[3]}<br>%{customdata[2]}<extra></extra>")))
    fig.update_layout(title="Publicación vs. creación de cuentas · Blocus",
                      xaxis_title="Fecha de publicación estimada por ID (UTC)",
                      yaxis_title="Fecha de creación de la cuenta (UTC)",
                      template="plotly_white", width=1400, height=850,
                      legend={"orientation": "h", "y": 1.12})
    fig.write_html(DEST / "publicacion_vs_creacion_interactivo.html", include_plotlyjs=True,
                   full_html=True)


def main() -> None:
    publications = read_csv(SOURCE / "publicaciones.csv")
    comments = read_csv(SOURCE / "comentarios.csv")
    users = read_csv(USERS)
    accounts = read_csv(ROOT / "data" / "blocus" / "datos" / "grafo_blocus_20261025" / "cuentas.csv")
    publishers, commenters, summary = build_points(publications, comments, users, accounts)
    DEST.mkdir(parents=True, exist_ok=True)
    draw_png(publishers, commenters, summary)
    draw_html(publishers, commenters)
    fields = ["publicacion_id", "cuenta_publicadora", "publicacion_url",
              "fecha_publicacion_estimada_utc", "usuario_id", "usuario",
              "fecha_creacion_utc", "tipo_fecha_creacion", "comentarios_observados",
              "primer_comentario_utc"]
    with (DEST / "puntos_comentaristas.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(comments for comments in commenters)
    (DEST / "resumen.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
