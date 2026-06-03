# -*- coding: utf-8 -*-
"""
migrar_estructura.py — Reorganiza data/ y outputs/ a la estructura por proyecto.

Estructura objetivo:
    data/{proyecto}/                         ← todos los CSV/JSON del proyecto
    outputs/{proyecto}/
        ├─ informes/
        ├─ graficas_videos/publicaciones/
        └─ graficas_comentarios/
            ├─ (nubes, hashtags…)            ← raíz (antes 'comentarios/')
            ├─ graficas_multidimensionales/
            ├─ graficas_patrones_cuentas/
            └─ polaridad_ia/

Uso:
    python scripts/migrar_estructura.py            # DRY-RUN (solo muestra el plan)
    python scripts/migrar_estructura.py --aplicar  # ejecuta los movimientos

Es idempotente: si ya está migrado, no hace nada. data/ y outputs/ están en
.gitignore, así que esto no afecta al control de versiones.
"""

import os
import sys
import shutil

BASE_DIR     = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_BASE    = os.path.join(BASE_DIR, "data")
OUTPUTS_BASE = os.path.join(BASE_DIR, "outputs")

sys.path.insert(0, BASE_DIR)
from config.rutas import derivar_proyecto

APLICAR = "--aplicar" in sys.argv

# Archivos en data/ que NO son datasets (no se mueven)
IGNORAR_DATA = {
    "cookies.json", "cookies_backup.json", "tiktok_cookies.json",
    "headers.json", "llm_telemetry.csv", ".gitkeep",
}
IGNORAR_PREFIJOS = ("debug_", "logs")
IGNORAR_SUFIJOS  = (".log",)

# Mapeo de subcarpetas antiguas de outputs/ → nueva ruta relativa
REMAP_OUTPUTS = {
    "publicaciones":               os.path.join("graficas_videos", "publicaciones"),
    "comentarios":                 "graficas_comentarios",
    "polaridad_ia":                os.path.join("graficas_comentarios", "polaridad_ia"),
    "graficas_multidimensionales": os.path.join("graficas_comentarios", "graficas_multidimensionales"),
    "graficas_patrones_cuentas":   os.path.join("graficas_comentarios", "graficas_patrones_cuentas"),
    "informes":                    "informes",  # se queda igual
}

acciones = []   # (origen, destino) para el resumen


def _mover(origen, destino):
    acciones.append((origen, destino))
    if not APLICAR:
        return
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    if os.path.isdir(origen):
        # Fusionar contenido carpeta a carpeta
        os.makedirs(destino, exist_ok=True)
        for item in os.listdir(origen):
            shutil.move(os.path.join(origen, item), os.path.join(destino, item))
        # Eliminar carpeta vacía
        try:
            os.rmdir(origen)
        except OSError:
            pass
    else:
        if os.path.exists(destino):
            return  # ya existe, no sobrescribir
        shutil.move(origen, destino)


# ── 1) Migrar datasets de data/ (nivel raíz) → data/{proyecto}/ ────────────────
def migrar_datos():
    if not os.path.isdir(DATA_BASE):
        return
    for nombre in os.listdir(DATA_BASE):
        ruta = os.path.join(DATA_BASE, nombre)
        if os.path.isdir(ruta):
            continue  # ya es una carpeta de proyecto (o debug/logs)
        if nombre in IGNORAR_DATA:
            continue
        if nombre.startswith(IGNORAR_PREFIJOS) or nombre.endswith(IGNORAR_SUFIJOS):
            continue
        if "_videos" not in nombre:
            continue  # no es un dataset reconocible
        proyecto = derivar_proyecto(nombre)
        destino = os.path.join(DATA_BASE, proyecto, nombre)
        if os.path.abspath(ruta) == os.path.abspath(destino):
            continue
        _mover(ruta, destino)


# ── 2) Reorganizar outputs/{proyecto}/ a la nueva estructura ───────────────────
def migrar_outputs():
    if not os.path.isdir(OUTPUTS_BASE):
        return
    for proyecto_dir in os.listdir(OUTPUTS_BASE):
        ruta_proj = os.path.join(OUTPUTS_BASE, proyecto_dir)
        if not os.path.isdir(ruta_proj):
            continue

        # Carpetas mal derivadas (..._videos_api, ..._videos_api_comentarios_api)
        # se fusionan en el proyecto canónico.
        proyecto_canon = derivar_proyecto(proyecto_dir + "_videos") \
            if "_videos" in proyecto_dir else proyecto_dir
        destino_proj = os.path.join(OUTPUTS_BASE, proyecto_canon)

        for sub in list(os.listdir(ruta_proj)):
            ruta_sub = os.path.join(ruta_proj, sub)
            if not os.path.isdir(ruta_sub):
                continue
            destino_rel = REMAP_OUTPUTS.get(sub)
            if destino_rel is None:
                # Subcarpeta ya migrada (graficas_videos/graficas_comentarios) u otra
                if sub in ("graficas_videos", "graficas_comentarios") and \
                   proyecto_canon != proyecto_dir:
                    _mover(ruta_sub, os.path.join(destino_proj, sub))
                continue
            destino = os.path.join(destino_proj, destino_rel)
            if os.path.abspath(ruta_sub) == os.path.abspath(destino):
                continue
            _mover(ruta_sub, destino)

        # Si la carpeta del proyecto mal derivado quedó vacía, eliminarla
        if proyecto_canon != proyecto_dir and APLICAR:
            try:
                if not os.listdir(ruta_proj):
                    os.rmdir(ruta_proj)
            except OSError:
                pass


def main():
    print("=" * 72)
    print("  MIGRACIÓN DE ESTRUCTURA  " + ("(APLICANDO)" if APLICAR else "(DRY-RUN)"))
    print("=" * 72)

    migrar_datos()
    migrar_outputs()

    if not acciones:
        print("\n  ✅ Nada que migrar — la estructura ya está organizada.\n")
        return

    print(f"\n  {len(acciones)} movimiento(s){'  [EJECUTADOS]' if APLICAR else ''}:\n")
    for origen, destino in acciones:
        rel_o = os.path.relpath(origen, BASE_DIR)
        rel_d = os.path.relpath(destino, BASE_DIR)
        print(f"   {rel_o}\n      → {rel_d}")

    if not APLICAR:
        print("\n  ── DRY-RUN — no se ha movido nada ──")
        print("  Ejecuta con --aplicar para realizar los movimientos:")
        print("      python scripts/migrar_estructura.py --aplicar\n")
    else:
        print("\n  ✅ Migración completada.\n")


if __name__ == "__main__":
    main()
