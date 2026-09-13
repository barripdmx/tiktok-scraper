# -*- coding: utf-8 -*-
"""
Pruebas de la configuración de navegación del menú (menu.py).

No prueban el render de CustomTkinter (requiere display), sino la integridad de
la estructura declarativa GROUPS/ACTIONS:
  - cada acción referencia un script que existe en disco,
  - cada acción pertenece a un grupo declarado,
  - los file_key usados en requires/produces son válidos,
  - el paso "informe" está bien definido.
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

GROUP_IDS = {g[0] for g in menu.GROUPS}
VALID_FILE_KEYS = {None} | set(menu.FILE_LABELS.keys())


def test_groups_no_vacios():
    assert len(menu.GROUPS) >= 2
    assert "captura" in GROUP_IDS and "analisis" in GROUP_IDS


def test_actions_ids_unicos():
    ids = [a["id"] for a in menu.ACTIONS]
    assert len(ids) == len(set(ids)), "Hay ids de acción duplicados"


def test_actions_group_valido():
    for act in menu.ACTIONS:
        assert act["group"] in GROUP_IDS, (
            f"La acción {act['id']} referencia un grupo inexistente: {act['group']}"
        )


def test_cada_grupo_tiene_al_menos_una_accion():
    grupos_usados = {act["group"] for act in menu.ACTIONS}
    for gid, _label in menu.GROUPS:
        assert gid in grupos_usados, f"El grupo {gid} no tiene ninguna acción"


def test_file_keys_validos():
    for act in menu.ACTIONS:
        for req in act.get("requires", []):
            assert req in VALID_FILE_KEYS, (
                f"requires inválido en {act['id']}: {req}"
            )
        assert act.get("produces") in VALID_FILE_KEYS, (
            f"produces inválido en {act['id']}: {act.get('produces')}"
        )
        assert act.get("arg_key") in VALID_FILE_KEYS, (
            f"arg_key inválido en {act['id']}: {act.get('arg_key')}"
        )


def test_scripts_existen_en_disco():
    for act in menu.ACTIONS:
        script = act.get("script")
        assert script, f"Acción sin script: {act['id']}"
        ruta = os.path.join(ROOT, script)
        assert os.path.isfile(ruta), f"No existe el script: {script}"


def test_accion_informe_bien_definida():
    informe = next(a for a in menu.ACTIONS if a["id"] == "informe")
    assert informe.get("opens_report") is True
    assert "videos" in informe["requires"]
