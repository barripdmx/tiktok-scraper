# -*- coding: utf-8 -*-
"""rutas.py — Fuente única de verdad para las rutas de datos y resultados.

Todos los scripts deben derivar el nombre de proyecto y las carpetas de salida
desde aquí, para evitar que cada módulo invente su propia estructura.

Estructura estándar:

    data/
     └─ {proyecto}/                          ← todos los CSV del proyecto
    outputs/
     └─ {proyecto}/
         ├─ informes/
         ├─ graficas_videos/
         │   └─ publicaciones/
         └─ graficas_comentarios/
             ├─ (nubes, hashtags, heatmaps…)  ← raíz
             ├─ graficas_multidimensionales/
             ├─ graficas_patrones_cuentas/
             └─ polaridad_ia/

Importar desde cualquier script en src/ así:
    import sys, os
    _BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    sys.path.insert(0, _BASE)
    from config.rutas import derivar_proyecto, dir_publicaciones, dataset_dir
"""

import os

# ── Bases ─────────────────────────────────────────────────────────────────────
BASE_DIR     = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_BASE    = os.path.join(BASE_DIR, "data")
OUTPUTS_BASE = os.path.join(BASE_DIR, "outputs")


# ── Derivación del nombre de proyecto ──────────────────────────────────────────
def derivar_proyecto(nombre_o_ruta: str) -> str:
    """
    Devuelve el nombre canónico de proyecto a partir de cualquier nombre de
    archivo o ruta del dataset.

    Regla: todos los datasets de un proyecto embeben '{proyecto}_videos…', así
    que basta con cortar en la primera aparición de '_videos'.

      user_adamuz_videos.csv                                   → user_adamuz
      zapatero_zp_plus_ultra_videos_api.csv                    → zapatero_zp_plus_ultra
      ..._videos_api_comentarios_api_con_sentimiento_mistral   → zapatero_zp_plus_ultra
      ..._videos_api_comentarios_api_enriquecido_fechas...     → zapatero_zp_plus_ultra

    Fallback: si no hay '_videos', devuelve el basename sin extensión.
    """
    base = os.path.basename(str(nombre_o_ruta or "").strip())
    base = os.path.splitext(base)[0]
    if "_videos" in base:
        return base.split("_videos")[0]
    return base


# ── Carpetas de datos ──────────────────────────────────────────────────────────
def dataset_dir(proyecto: str) -> str:
    """data/{proyecto}/ (creada si no existe)."""
    d = os.path.join(DATA_BASE, proyecto)
    os.makedirs(d, exist_ok=True)
    return d


def dir_datos_para(nombre_o_ruta: str) -> str:
    """Carpeta de datos del proyecto al que pertenece un archivo dado."""
    return dataset_dir(derivar_proyecto(nombre_o_ruta))


# ── Carpetas de resultados ─────────────────────────────────────────────────────
def _out(proyecto: str, *partes: str) -> str:
    d = os.path.join(OUTPUTS_BASE, proyecto, *partes)
    os.makedirs(d, exist_ok=True)
    return d


def dir_proyecto(proyecto: str) -> str:
    """outputs/{proyecto}/"""
    return _out(proyecto)


def dir_informes(proyecto: str) -> str:
    """outputs/{proyecto}/informes/"""
    return _out(proyecto, "informes")


def dir_graficas_videos(proyecto: str) -> str:
    """outputs/{proyecto}/graficas_videos/"""
    return _out(proyecto, "graficas_videos")


def dir_publicaciones(proyecto: str) -> str:
    """outputs/{proyecto}/graficas_videos/publicaciones/"""
    return _out(proyecto, "graficas_videos", "publicaciones")


def dir_graficas_comentarios(proyecto: str) -> str:
    """outputs/{proyecto}/graficas_comentarios/ (nubes, hashtags, heatmaps…)."""
    return _out(proyecto, "graficas_comentarios")


def dir_multidimensionales(proyecto: str) -> str:
    """outputs/{proyecto}/graficas_comentarios/graficas_multidimensionales/"""
    return _out(proyecto, "graficas_comentarios", "graficas_multidimensionales")


def dir_patrones(proyecto: str) -> str:
    """outputs/{proyecto}/graficas_comentarios/graficas_patrones_cuentas/"""
    return _out(proyecto, "graficas_comentarios", "graficas_patrones_cuentas")


def dir_polaridad(proyecto: str) -> str:
    """outputs/{proyecto}/graficas_comentarios/polaridad_ia/"""
    return _out(proyecto, "graficas_comentarios", "polaridad_ia")


# ── Comprobación rápida ────────────────────────────────────────────────────────
if __name__ == "__main__":
    pruebas = [
        "user_adamuz_videos.csv",
        "zapatero_zp_plus_ultra_videos_api.csv",
        "zapatero_zp_plus_ultra_videos_api_comentarios_api.csv",
        "zapatero_zp_plus_ultra_videos_api_comentarios_api_con_sentimiento_mistral.csv",
        "data/zapatero_zp_plus_ultra_videos_api_comentarios_api_enriquecido_fechas_creacion.csv",
    ]
    for p in pruebas:
        print(f"{p}\n   → {derivar_proyecto(p)}")
