"""Comprueba widgets Tk reales y el comando que ejecuta el menú, sin red."""
import io
from pathlib import Path
from tkinter import TclError, filedialog

import pytest

import menu
from src.scrapers.tiktok_descargar_relaciones import parser


@pytest.fixture
def app(monkeypatch):
    # No leer ni reemplazar las preferencias reales del usuario.
    monkeypatch.setattr(menu.MenuApp, "_restore_state", lambda self: None)
    monkeypatch.setattr(menu.MenuApp, "_save_state", lambda self: None)
    try:
        root = menu.MenuApp()
    except TclError as exc:
        pytest.skip(f"No hay display Tk: {exc}")
    root.withdraw()
    yield root
    root.destroy()


def put(app, flag, value):
    widget = app._entries[flag]
    widget.delete(0, "end")
    widget.insert(0, value)
    app._on_input_change(app._current_id, flag, widget)


def buttons(parent):
    for child in parent.winfo_children():
        if isinstance(child, menu.ctk.CTkButton):
            yield child
        yield from buttons(child)


def test_single_controls_validation_and_navigation(app):
    app._select("relaciones")
    assert app._run_btn.cget("state") == "disabled"
    assert isinstance(app._entries["--lista"], menu.ctk.CTkOptionMenu)
    assert app._entries["--lista"].get() == "ambas"
    assert app._entries["--sesion"].get() == "anonima"
    put(app, "--user", "https://www.tiktok.com/@BlocusEspanol")
    assert app._run_btn.cget("state") == "normal"
    assert app._derived_project(app._current()) == "user_blocusespanol"
    put(app, "--max-cuentas", "-1")
    assert app._run_btn.cget("state") == "disabled"
    put(app, "--max-cuentas", "35")
    app._entries["--lista"].set("seguidos")
    app._refresh_buttons()
    app._select("relaciones_lote")
    assert app._run_btn.cget("state") == "disabled"
    app._select("relaciones")
    assert app._entries["--max-cuentas"].get() == "35"
    assert app._entries["--lista"].get() == "seguidos"


def test_saved_access_is_selectable_in_both_download_modes(app, monkeypatch, tmp_path):
    source = tmp_path / "cuentas.txt"
    source.write_text("blocusespanol\n", encoding="utf-8")
    for action in ("relaciones", "relaciones_lote"):
        app._select(action)
        if action == "relaciones":
            put(app, "--user", "blocusespanol")
        else:
            put(app, "--archivo", str(source))
        app._entries["--sesion"].set("secundaria")
        app._on_input_change(action, "--sesion", app._entries["--sesion"])
        launched = []
        class Process:
            stdin = io.StringIO()
            stdout = iter([])
            def __init__(self, cmd, **kwargs):
                launched.append(cmd)
            def poll(self):
                return None
        monkeypatch.setattr(menu.subprocess, "Popen", Process)
        app._run_btn.invoke()
        assert parser().parse_args(launched[0][3:]).sesion == "secundaria"
        app._on_finished(0)


def test_file_picker_preview_command_and_warning_completion(app, tmp_path, monkeypatch):
    source = tmp_path / "cuentas con espacios.csv"
    source.write_text("username;nota\n@uno;primera\ndos;segunda\nUNO;duplicada\n", encoding="utf-8-sig")
    app._select("relaciones_lote")
    monkeypatch.setattr(filedialog, "askopenfilename", lambda **kwargs: str(source))
    browse = next(w for w in buttons(app) if w.cget("text") == "Examinar…")
    browse.invoke()
    assert app._entries["--archivo"].get() == str(source)
    assert "2 cuentas distintas" in app._proj_preview.cget("text")
    assert "1 duplicados omitidos" in app._proj_preview.cget("text")
    put(app, "--max-cuentas", "35")
    app._entries["--lista"].set("seguidores")
    app._refresh_buttons()
    output = tmp_path / "salida"
    output.mkdir()
    launched = []

    class Process:
        def __init__(self, cmd, **kwargs):
            launched.append((cmd, kwargs))
            self.stdin = io.StringIO()
            self.stdout = iter([f"Salida: {output}\n", "Datos parciales conservados.\n"])
        def poll(self):
            return None

    monkeypatch.setattr(menu.subprocess, "Popen", Process)
    app._run_btn.invoke()
    assert len(launched) == 1
    cmd, kwargs = launched[0]
    assert cmd[1] == "-u" and cmd[2].endswith("tiktok_descargar_relaciones.py")
    parsed = parser().parse_args(cmd[3:])
    assert parsed.archivo == source and parsed.lista == "seguidores" and parsed.max_cuentas == 35
    assert parsed.no_prompt is True
    assert kwargs.get("shell", False) is False
    app._on_finished(2)
    assert "observaciones" in app._log.get("1.0", "end")
    assert "errores" not in app._status_var.get()
    assert app._last_result_dir == str(output)
    assert app._result_btn.cget("state") == "normal"
    opened = []
    monkeypatch.setattr(app, "_open", opened.append)
    app._result_btn.invoke()
    assert opened == [str(output)]


def test_invalid_batch_is_blocked_and_file_changes_are_rechecked(app, tmp_path):
    source = tmp_path / "cuentas.txt"
    source.write_text("uno\ndos\n", encoding="utf-8")
    app._select("relaciones_lote")
    put(app, "--archivo", str(source))
    assert app._run_btn.cget("state") == "normal"
    source.write_text("uno\nhttps://evil.example/@dos\n", encoding="utf-8")
    app._refresh_buttons()
    assert app._run_btn.cget("state") == "disabled"
    assert "fila 2" in app._hint.cget("text")
    # Revisar archivo no inicia ningún subproceso.
    assert app._proc is None


def test_single_menu_command_matches_cli(app, monkeypatch):
    app._select("relaciones")
    put(app, "--user", "@BlocusEspanol")
    launched = []
    class Process:
        stdin = io.StringIO()
        stdout = iter([])
        def __init__(self, cmd, **kwargs):
            launched.append(cmd)
        def poll(self):
            return None
    monkeypatch.setattr(menu.subprocess, "Popen", Process)
    app._run_btn.invoke()
    parsed = parser().parse_args(launched[0][3:])
    assert parsed.user == "blocusespanol" and parsed.lista == "ambas"
    assert parsed.max_cuentas == 0 and parsed.sesion == "anonima"
    app._on_finished(0)


def test_stop_requests_save_before_exit(app, monkeypatch):
    app._select("relaciones")
    put(app, "--user", "blocusespanol")
    class Process:
        stdin = io.StringIO()
        stdout = iter([])
        def __init__(self, *args, **kwargs):
            pass
        def poll(self):
            return None
    monkeypatch.setattr(menu.subprocess, "Popen", Process)
    app._run_btn.invoke()
    cancel = app._cancel_file
    assert not cancel.exists()
    app._stop_proc()
    assert cancel.exists() and app._stopping
    app._on_finished(130)
    assert not cancel.exists()
    assert "detenido" in app._status_var.get()


@pytest.mark.parametrize("action", ["relaciones", "relaciones_lote"])
@pytest.mark.parametrize("size", ["1000x680", "1180x830"])
def test_small_window_keeps_actions_visible_and_fields_reachable(app, action, size):
    app.attributes("-alpha", 0)
    app.deiconify()
    app.geometry(size)
    app._select(action)
    app.update()
    for widget in (app._run_btn, app._stop_btn, app._result_btn, app._log):
        y = widget.winfo_rooty() - app.winfo_rooty()
        assert 0 <= y < y + widget.winfo_height() <= app.winfo_height()
        assert widget.winfo_height() > 1
    canvas = app._detail_scroll._parent_canvas
    # El último campo puede alcanzarse mediante el desplazamiento del formulario.
    canvas.yview_moveto(1)
    app.update()
    last = app._entries["--max-cuentas"]
    assert canvas.winfo_rooty() <= last.winfo_rooty()
    assert last.winfo_rooty() + last.winfo_height() <= canvas.winfo_rooty() + canvas.winfo_height()
