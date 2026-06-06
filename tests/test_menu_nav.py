# -*- coding: utf-8 -*-
"""
Pruebas de la configuración de navegación del menú (menu.py).

No prueban el render de CustomTkinter (requiere display), sino la integridad de
la estructura declarativa MODULES/TABS y del dispatch de acciones:
  - cada acción referencia un script que existe en disco (o usa run="informe"),
  - el módulo "captura" cubre todas las pestañas (per_tab),
  - los file_key usados son válidos.
"""

import os
import sys

import pytest

# Permitir importar menu.py desde la raíz del proyecto
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

ctk = pytest.importorskip("customtkinter")  # salta si no hay entorno GUI instalado
import menu  # noqa: E402

VALID_FILE_KEYS = {None, "videos", "comments", "sentiment", "enriched"}
TAB_IDS = {t[0] for t in menu.TABS}


def _iter_actions():
    """Genera (module_id, action) para todas las acciones, resolviendo per_tab."""
    for mod in menu.MODULES:
        if "per_tab" in mod:
            for act in mod["per_tab"].values():
                yield mod["id"], act
        else:
            for act in mod["actions"]:
                yield mod["id"], act


def test_tabs_no_vacias():
    assert len(menu.TABS) >= 2
    assert "usuario" in TAB_IDS and "hashtag" in TAB_IDS


def test_modules_ids_unicos():
    ids = [m["id"] for m in menu.MODULES]
    assert len(ids) == len(set(ids)), "Hay ids de módulo duplicados"


def test_captura_cubre_todas_las_pestanas():
    captura = next(m for m in menu.MODULES if m["id"] == "captura")
    assert "per_tab" in captura
    assert set(captura["per_tab"].keys()) == TAB_IDS


def test_cada_modulo_tiene_al_menos_una_accion():
    for mod in menu.MODULES:
        acciones = mod.get("actions") or list(mod.get("per_tab", {}).values())
        assert acciones, f"El módulo {mod['id']} no tiene acciones"


def test_file_keys_validos():
    for mid, act in _iter_actions():
        assert act["file_key"] in VALID_FILE_KEYS, (
            f"file_key inválido en {mid}: {act['file_key']}"
        )


def test_scripts_existen_en_disco():
    for mid, act in _iter_actions():
        if act.get("run") == "informe":
            continue  # usa generar_informe(), no un script suelto
        script = act["script"]
        assert script, f"Acción sin script en módulo {mid}"
        ruta = os.path.join(ROOT, script)
        assert os.path.isfile(ruta), f"No existe el script: {script}"


def test_accion_informe_bien_definida():
    informe = next(m for m in menu.MODULES if m["id"] == "informe")
    act = informe["actions"][0]
    assert act["run"] == "informe"
    assert act["file_key"] == "videos"
