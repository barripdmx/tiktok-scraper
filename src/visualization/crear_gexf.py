# -*- coding: utf-8 -*-
"""
================================================================================
TikTok Comments to GEXF Network Generator
================================================================================

DESCRIPCIÓN:
    Genera un archivo GEXF (para Gephi) a partir de CSVs de comentarios de TikTok.
    
    Red creada:
    - Nodo A (source): autor_handle (quien comenta)
    - Nodo B (target): username (dueño del video)
    - Edge: Representa que A comentó en un video de B
    - Weight: Número de comentarios de A en videos de B

REQUISITOS:
    pip install networkx

USO:
    python tiktok_comentarios_to_gexf.py
    
    1. Selecciona uno o más archivos CSV
    2. Después de cada archivo, indica si hay más o no
    3. El GEXF se genera automáticamente

================================================================================
"""

import os
import csv
import tkinter as tk
from tkinter import filedialog, messagebox
from datetime import datetime
from collections import defaultdict
from typing import List, Dict, Tuple, Set

try:
    import networkx as nx
except ImportError:
    print("❌ Error: Se requiere networkx")
    print("   Instálalo con: pip install networkx")
    raise SystemExit(1)


def seleccionar_archivo() -> str:
    """Abre diálogo para seleccionar un CSV."""
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    
    ruta = filedialog.askopenfilename(
        title="Selecciona CSV de comentarios TikTok",
        filetypes=[("CSV files", "*.csv"), ("Todos", "*.*")]
    )
    
    root.destroy()
    return ruta


def preguntar_mas_archivos() -> bool:
    """Pregunta si hay más archivos por cargar."""
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    
    respuesta = messagebox.askyesno(
        "¿Más archivos?",
        "¿Quieres cargar otro archivo CSV?\n\n" +
        "Sí = Cargar otro archivo\n" +
        "No = Generar GEXF con los archivos cargados"
    )
    
    root.destroy()
    return respuesta


def cargar_csv(ruta: str) -> List[Dict[str, str]]:
    """Carga un CSV y retorna lista de diccionarios."""
    rows = []
    try:
        with open(ruta, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
    except Exception as e:
        print(f"   ⚠️ Error leyendo {ruta}: {e}")
    return rows


def procesar_datos(all_rows: List[Dict[str, str]]) -> Tuple[Dict[Tuple[str, str], int], Dict[str, Dict]]:
    """
    Procesa todos los comentarios y genera:
    - edges: diccionario {(source, target): weight}
    - node_stats: diccionario {node_id: {stats}}
    """
    # Contador de edges: (autor_handle -> username) : count
    edge_counts = defaultdict(int)
    
    # Stats por nodo
    node_comments_made = defaultdict(int)      # Comentarios hechos por este handle
    node_comments_received = defaultdict(int)  # Comentarios recibidos (si es username)
    node_likes_given = defaultdict(int)        # Likes en comentarios hechos
    node_is_author = set()                     # Nodos que son autores de videos
    
    for row in all_rows:
        username = (row.get("username") or "").strip()
        autor_handle = (row.get("autor_handle") or "").strip()
        likes = int(row.get("likes") or 0)
        
        # Ignorar filas sin datos válidos
        if not username or not autor_handle:
            continue
        
        # Ignorar auto-comentarios (el autor comenta en su propio video)
        if username.lower() == autor_handle.lower():
            continue
        
        # Edge: autor_handle -> username
        edge_counts[(autor_handle, username)] += 1
        
        # Stats
        node_comments_made[autor_handle] += 1
        node_comments_received[username] += 1
        node_likes_given[autor_handle] += likes
        node_is_author.add(username)
    
    # Compilar stats de nodos
    all_nodes = set(node_comments_made.keys()) | set(node_comments_received.keys())
    node_stats = {}
    
    for node in all_nodes:
        node_stats[node] = {
            "comments_made": node_comments_made.get(node, 0),
            "comments_received": node_comments_received.get(node, 0),
            "likes_on_comments": node_likes_given.get(node, 0),
            "is_video_author": node in node_is_author,
        }
    
    return dict(edge_counts), node_stats


def crear_gexf(edge_counts: Dict[Tuple[str, str], int], 
               node_stats: Dict[str, Dict],
               output_path: str) -> None:
    """Crea el archivo GEXF usando NetworkX."""
    
    # Crear grafo dirigido
    G = nx.DiGraph()
    
    # Añadir nodos con atributos
    for node_id, stats in node_stats.items():
        G.add_node(
            node_id,
            label=node_id,
            comments_made=stats["comments_made"],
            comments_received=stats["comments_received"],
            likes_on_comments=stats["likes_on_comments"],
            is_video_author=stats["is_video_author"],
            # Tamaño visual basado en actividad total
            size=stats["comments_made"] + stats["comments_received"]
        )
    
    # Añadir edges con peso
    for (source, target), weight in edge_counts.items():
        G.add_edge(source, target, weight=weight)
    
    # Guardar GEXF
    nx.write_gexf(G, output_path)
    print(f"\n✅ GEXF guardado: {output_path}")


def mostrar_resumen(edge_counts: Dict, node_stats: Dict, archivos: List[str]):
    """Muestra resumen de la red generada."""
    total_edges = len(edge_counts)
    total_weight = sum(edge_counts.values())
    total_nodes = len(node_stats)
    
    # Nodos que son autores vs comentaristas puros
    authors = sum(1 for s in node_stats.values() if s["is_video_author"])
    commenters_only = total_nodes - authors
    
    # Top comentaristas
    top_commenters = sorted(
        [(n, s["comments_made"]) for n, s in node_stats.items()],
        key=lambda x: x[1],
        reverse=True
    )[:10]
    
    # Top receptores de comentarios
    top_receivers = sorted(
        [(n, s["comments_received"]) for n, s in node_stats.items() if s["comments_received"] > 0],
        key=lambda x: x[1],
        reverse=True
    )[:10]
    
    print("\n" + "=" * 60)
    print("RESUMEN DE LA RED")
    print("=" * 60)
    print(f"📂 Archivos procesados: {len(archivos)}")
    for a in archivos:
        print(f"   - {os.path.basename(a)}")
    print()
    print(f"🔵 Total nodos: {total_nodes:,}")
    print(f"   - Autores de videos: {authors:,}")
    print(f"   - Solo comentaristas: {commenters_only:,}")
    print()
    print(f"➡️  Total edges (relaciones únicas): {total_edges:,}")
    print(f"💬 Total comentarios (peso total): {total_weight:,}")
    print()
    
    if top_commenters:
        print("🏆 Top 10 comentaristas (más activos):")
        for i, (name, count) in enumerate(top_commenters, 1):
            print(f"   {i:2}. @{name}: {count:,} comentarios")
    print()
    
    if top_receivers:
        print("📥 Top 10 receptores (más comentados):")
        for i, (name, count) in enumerate(top_receivers, 1):
            print(f"   {i:2}. @{name}: {count:,} comentarios recibidos")


def main():
    print("=" * 60)
    print("TikTok Comments → GEXF Network Generator")
    print("=" * 60)
    print()
    
    archivos_cargados = []
    all_rows = []

    # Pre-carga el primer archivo si viene como argumento (del menú con proyecto activo)
    import sys as _sys
    _preload = _sys.argv[1] if len(_sys.argv) > 1 and os.path.isfile(_sys.argv[1]) else None

    while True:
        print(f"📂 Archivos cargados: {len(archivos_cargados)}")
        if _preload:
            ruta = _preload
            _preload = None  # solo la primera vez
            print(f"   Cargando automáticamente: {os.path.basename(ruta)}")
        else:
            print("   Selecciona un archivo CSV...")
            ruta = seleccionar_archivo()
        
        if not ruta:
            if not archivos_cargados:
                print("❌ No se seleccionó ningún archivo. Saliendo.")
                return
            else:
                print("⚠️ Cancelado. Generando GEXF con los archivos ya cargados...")
                break
        
        # Cargar el archivo
        print(f"\n📄 Cargando: {os.path.basename(ruta)}")
        rows = cargar_csv(ruta)
        
        if rows:
            all_rows.extend(rows)
            archivos_cargados.append(ruta)
            print(f"   ✅ {len(rows):,} filas cargadas")
            print(f"   📊 Total acumulado: {len(all_rows):,} comentarios")
        else:
            print("   ⚠️ Archivo vacío o error de lectura")
        
        # Preguntar si hay más
        print()
        if not preguntar_mas_archivos():
            break
        print()
    
    if not all_rows:
        print("❌ No hay datos para procesar.")
        return
    
    # Procesar datos
    print("\n⚙️ Procesando datos...")
    edge_counts, node_stats = procesar_datos(all_rows)
    
    if not edge_counts:
        print("❌ No se encontraron relaciones válidas (username ↔ autor_handle)")
        return
    
    # Mostrar resumen
    mostrar_resumen(edge_counts, node_stats, archivos_cargados)
    
    # Generar nombre de salida
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if len(archivos_cargados) == 1:
        base = os.path.splitext(os.path.basename(archivos_cargados[0]))[0]
        output_name = f"{base}_network.gexf"
    else:
        output_name = f"tiktok_combined_network_{timestamp}.gexf"
    
    # Guardar en el mismo directorio del primer archivo
    output_dir = os.path.dirname(archivos_cargados[0])
    output_path = os.path.join(output_dir, output_name)
    
    # Crear GEXF
    print("\n⚙️ Generando GEXF...")
    crear_gexf(edge_counts, node_stats, output_path)
    
    print("\n" + "=" * 60)
    print("✅ PROCESO COMPLETADO")
    print("=" * 60)
    print(f"\n📁 Archivo generado: {output_path}")
    print("\n💡 Abre el archivo en Gephi para visualizar la red.")
    print("   Sugerencias de layout: ForceAtlas2, Fruchterman Reingold")
    print("   Usa 'weight' en edges para grosor de líneas")
    print("   Usa 'size' en nodos para tamaño proporcional")


if __name__ == "__main__":
    main()