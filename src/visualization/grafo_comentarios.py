# -*- coding: utf-8 -*-
"""
Genera un GEXF para Gephi tomando como nodos:
- user_original
- comentario_usuario_handle

Y aristas dirigidas:
- comentario_usuario_handle --> user_original

Peso = número de comentarios entre ese par (agregado).
Atributos de arista: videos_unicos, primer_comentario, ultimo_comentario.

Uso:
    python make_gephi_gexf.py
(se abrirá un diálogo para seleccionar el CSV con columnas:
 'user_original' y 'comentario_usuario_handle'. Opcional: 'video_id' y 'comentario_fecha')
"""

import os
import re
import sys
import csv
import math
import pandas as pd
import networkx as nx
from datetime import datetime
import tkinter as tk
from tkinter import filedialog

# ---- helpers ----
def parse_dt_maybe(s: str):
    """
    Intenta parsear fechas tipo 'dd/mm/yyyy HH:MM' o similares;
    si no puede, devuelve la cadena original (Gephi lo aceptará como atributo string).
    """
    if not isinstance(s, str) or not s.strip():
        return ""
    s = s.strip()
    # intenta varios formatos comunes que genera tu scraper
    for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(s, fmt)
        except:
            pass
    # si viene ISO ya
    try:
        return datetime.fromisoformat(s.replace("T", " "))
    except:
        return s  # deja la cadena tal cual

def coerce_str(x):
    if isinstance(x, (int, float)) and not isinstance(x, bool):
        # evita NaN/inf
        if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
            return ""
        return str(int(x)) if float(x).is_integer() else str(x)
    return "" if x is None else str(x)

def normalize_handle(s: str) -> str:
    """
    Limpia espacios y quita '@' sobrante.
    """
    s = coerce_str(s).strip()
    if s.startswith("@"):
        s = s[1:]
    return s

def extract_user_from_url(url: str) -> str:
    """
    Por si quieres derivar user_original de 'video_url' (no obligatorio aquí).
    """
    if not url:
        return ""
    m = re.search(r"tiktok\.com/@([^/]+)/video/", url)
    if m:
        return m.group(1)
    m = re.search(r"/@([^/?#]+)/", url)
    return m.group(1) if m else ""

# ---- main ----
def main():
    # selector de archivo
    root = tk.Tk(); root.withdraw()
    print("📄 Selecciona el CSV de comentarios")
    csv_path = filedialog.askopenfilename(
        title="Selecciona CSV (comments)",
        filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
    )
    if not csv_path:
        print("❌ No seleccionaste CSV.")
        return

    # lectura robusta — IDs de comentario como string para no perder precisión con float64
    id_cols = {"comment_id": str, "parent_comment_id": str}
    try:
        df = pd.read_csv(csv_path, encoding="utf-8-sig", dtype=id_cols)
    except Exception:
        df = pd.read_csv(csv_path, encoding="utf-8-sig", engine="python", sep=None, dtype=id_cols)

    # normaliza nombres de columnas a minúsculas para buscar
    cols_map = {c.lower(): c for c in df.columns}

    # columnas requeridas (acepta nombres alternativos según versión del scraper)
    col_video_author = cols_map.get("user_original") or cols_map.get("username")
    col_commenter    = cols_map.get("comentario_usuario_handle") or cols_map.get("autor_handle")
    col_comment_id   = cols_map.get("comment_id")
    col_parent_id    = cols_map.get("parent_comment_id")
    col_is_reply     = cols_map.get("is_reply")

    missing = []
    if not col_video_author:
        missing.append("user_original / username")
    if not col_commenter:
        missing.append("comentario_usuario_handle / autor_handle")
    if missing:
        raise RuntimeError(f"El CSV no tiene las columnas necesarias: {missing}. Columnas encontradas: {list(df.columns)}")

    # opcionales
    col_video_id = cols_map.get("video_id")
    col_fecha    = cols_map.get("comentario_fecha") or cols_map.get("fecha")

    # normaliza handles
    df["_commenter"]     = df[col_commenter].map(normalize_handle)
    df["_video_author"]  = df[col_video_author].map(normalize_handle)

    # quita filas sin commenter
    df = df[df["_commenter"] != ""]
    if df.empty:
        print("⚠️ No hay filas válidas. Nada que exportar.")
        return

    # construye lookup comment_id -> autor_handle para resolver destinos de replies
    # comment_id ya viene como string (dtype=str), usamos strip() para limpiar
    lookup_autor = {}
    if col_comment_id:
        lookup_autor = dict(zip(
            df[col_comment_id].astype(str).str.strip(),
            df["_commenter"]
        ))

    # determina el destino real de cada arista:
    #   - comentario directo (is_reply=False/NaN) → va al autor del vídeo
    #   - reply (is_reply=True)                   → va al autor del comentario padre
    def resolve_dst(row):
        if col_is_reply and col_parent_id:
            try:
                is_rep = row[col_is_reply]
                if str(is_rep).strip().lower() in ("true", "1"):
                    parent_id = str(row[col_parent_id]).strip()
                    parent_autor = lookup_autor.get(parent_id, "")
                    if parent_autor:
                        return parent_autor
            except Exception:
                pass
        return row["_video_author"]

    df["_dst"] = df.apply(resolve_dst, axis=1)

    # quita filas donde origen == destino (auto-loops)
    df = df[df["_commenter"] != df["_dst"]]

    # fechas opcionales
    if col_fecha:
        try:
            df["_fecha_dt"] = df[col_fecha].map(parse_dt_maybe)
        except Exception:
            df["_fecha_dt"] = df[col_fecha]

    # agrega por par (origen, destino)
    group_cols = ["_commenter", "_dst"]
    agg_parts = {"comentarios": ("_commenter", "count")}
    if col_video_id:
        agg_parts["videos_unicos"] = (col_video_id, "nunique")
    if col_fecha:
        agg_parts["primer"] = ("_fecha_dt", "min")
        agg_parts["ultimo"] = ("_fecha_dt", "max")

    grouped = df.groupby(group_cols).agg(**agg_parts).reset_index()

    n_replies  = (df[col_is_reply].astype(str).str.strip().str.lower().isin(["true","1"])).sum() if col_is_reply else 0
    n_direct   = len(df) - n_replies
    print(f"   Comentarios directos: {n_direct:,}  |  Replies resueltas: {n_replies:,}")

    # construimos el grafo dirigido
    G = nx.DiGraph()

    # roles de nodos (un usuario puede ser ambos)
    roles = {}  # node -> set{"autor_video","comentarista"}

    # añade nodos y aristas
    for _, row in grouped.iterrows():
        src = coerce_str(row["_commenter"])
        dst = coerce_str(row["_dst"])
        weight = int(row.get("comentarios", 0)) if not pd.isna(row.get("comentarios", 0)) else 0

        videos_unicos = int(row.get("videos_unicos", 0)) if not pd.isna(row.get("videos_unicos", 0)) else 0
        primer = row.get("primer", "")
        ultimo = row.get("ultimo", "")

        # convertir fechas datetime a string legible para GEXF
        if isinstance(primer, datetime):
            primer = primer.strftime("%Y-%m-%d %H:%M:%S")
        if isinstance(ultimo, datetime):
            ultimo = ultimo.strftime("%Y-%m-%d %H:%M:%S")

        if src not in G:
            G.add_node(src, label=src)
        if dst not in G:
            G.add_node(dst, label=dst)

        # roles: el destino puede ser el autor del vídeo o un comentarista receptor de reply
        roles.setdefault(src, set()).add("comentarista")
        roles.setdefault(dst, set())  # dst puede ser cualquier tipo, se decide al final

        # si ya existe arista, acumular (por si el groupby no consolidó algo raro)
        if G.has_edge(src, dst):
            G[src][dst]["weight"] += weight
            G[src][dst]["videos_unicos"] = (G[src][dst].get("videos_unicos", 0) or 0) + videos_unicos
            # ajustar primer/último por límites
            p_old = G[src][dst].get("primer")
            u_old = G[src][dst].get("ultimo")
            # comparamos strings de fecha si son ISO-like; si no, dejamos el primero no vacío
            if p_old and primer:
                G[src][dst]["primer"] = min(p_old, primer)
            elif primer and not p_old:
                G[src][dst]["primer"] = primer
            if u_old and ultimo:
                G[src][dst]["ultimo"] = max(u_old, ultimo)
            elif ultimo and not u_old:
                G[src][dst]["ultimo"] = ultimo
        else:
            G.add_edge(
                src, dst,
                weight=weight,
                videos_unicos=videos_unicos,
                primer=coerce_str(primer),
                ultimo=coerce_str(ultimo)
            )

    # el autor del vídeo (o autores si el CSV mezcla varios) son los únicos nodos "autor_video"
    autores_video = set(df["_video_author"].unique())

    # aplica rol definitivo por nodo
    for node in G.nodes():
        es_autor  = node in autores_video
        es_coment = node in roles and "comentarista" in roles[node]
        if es_autor and es_coment:
            rol = "ambos"
        elif es_autor:
            rol = "autor_video"
        else:
            rol = "comentarista"
        nx.set_node_attributes(G, {node: {"rol": rol}})

    # ruta de salida
    base = os.path.splitext(os.path.basename(csv_path))[0]
    out_path = os.path.join(os.path.dirname(csv_path), f"{base}_user_to_author.gexf")

    # escribe GEXF
    nx.write_gexf(G, out_path)
    print("\n✅ GEXF generado")
    print(f"   Nodos: {G.number_of_nodes():,}")
    print(f"   Aristas: {G.number_of_edges():,}")
    print(f"   Archivo: {out_path}")

if __name__ == "__main__":
    main()
