# -*- coding: utf-8 -*-
"""
Menú principal — CustomTkinter, modo claro, navegación horizontal multinivel.

Niveles de navegación:
  Nivel 1  Pestaña principal   👤 Usuario | #️⃣ Hashtag  (segmented button)
  Nivel 2  Módulos compartidos del flujo (solo "Captura" cambia según pestaña)
  Nivel 3  Acciones del módulo activo (solo si tiene más de una)
  Panel    Descripción + estado del CSV requerido + botón ▶ Ejecutar

La estructura se define en la constante declarativa MODULES; la UI y el
dispatch se generan a partir de ella. Para añadir una opción nueva basta con
agregar un dict a MODULES (o una acción a su lista "actions").
"""

import os
import sys
import json
import threading
import subprocess
import customtkinter as ctk

# ---------------------------------------------------------------------------
# Configuración declarativa de la navegación
# ---------------------------------------------------------------------------

def A(label, icon, *, script=None, file_key=None, run=None, help=""):
    """Crea la definición de una acción ejecutable."""
    return {"label": label, "icon": icon, "script": script,
            "file_key": file_key, "run": run, "help": help}


# Pestañas de primer nivel (solo cambian la acción de captura)
TABS = [
    ("usuario", "Usuario", "👤"),
    ("hashtag", "Hashtag", "#"),
]

# Módulos del flujo compartido. El módulo "captura" define una acción distinta
# por pestaña (per_tab); el resto son idénticos para Usuario y Hashtag.
MODULES = [
    {"id": "captura", "label": "Captura", "icon": "📥", "per_tab": {
        "usuario": A("Extraer perfil", "👤",
                     script="src/scrapers/1_tiktok_scraper_user.py",
                     help="Extrae todos los vídeos de un perfil @usuario."),
        "hashtag": A("Buscar hashtag", "#",
                     script="src/scrapers/2_tiktok_scraper_hastag_api.py",
                     help="Busca y extrae vídeos por hashtag o palabra clave."),
    }},
    {"id": "comentarios", "label": "Comentarios", "icon": "💬", "actions": [
        A("Extraer comentarios", "💬",
          script="src/scrapers/2_tiktok_scraper_comentarios_api.py",
          help="Descarga miles de comentarios de las publicaciones (API Pro)."),
        A("Analítica (nubes)", "🗣️",
          script="src/analysis/analitica_comentarios.py", file_key="comments",
          help="Nubes de palabras y métricas sobre los comentarios."),
    ]},
    {"id": "edad", "label": "Edad de cuentas", "icon": "📅", "actions": [
        A("Calcular edades", "📅",
          script="src/utils/enriquecer_csv_fechas_creacion.py", file_key="comments",
          help="Enriquece los comentaristas con la fecha de creación de su cuenta."),
        A("Gráficas de patrones", "🕵️",
          script="src/visualization/graficas_patrones_cuentas.py", file_key="enriched",
          help="Detecta patrones de bots: antigüedad, actividad, perfiles vacíos."),
    ]},
    {"id": "grafo", "label": "Grafo de redes", "icon": "🕸️", "actions": [
        A("Generar GEXF", "🕸️",
          script="src/visualization/crear_gexf.py", file_key="comments",
          help="Crea un grafo de relaciones (GEXF) para abrir en Gephi."),
    ]},
    {"id": "sentimiento", "label": "Sentimiento IA", "icon": "🤖", "actions": [
        A("Analizar sentimiento", "🤖",
          script="src/analysis/analizar_sentimiento.py", file_key="comments",
          help="Clasifica el sentimiento de los comentarios (RoBERTa·Groq·Mistral)."),
        A("Gráficas multidim.", "🧠",
          script="src/visualization/grafica_multidimensional.py", file_key="sentiment",
          help="Sesgo · arquetipo · intención · pain points."),
    ]},
    {"id": "multidim", "label": "Gráficas multidim.", "icon": "🧠", "actions": [
        A("Generar gráficas", "🧠",
          script="src/visualization/grafica_multidimensional.py", file_key="sentiment",
          help="Genera el set completo de gráficas multidimensionales."),
    ]},
    {"id": "publicaciones", "label": "Publicaciones", "icon": "📈", "actions": [
        A("Vistas y likes", "📈",
          script="src/analysis/analitica_publicaciones.py", file_key="videos",
          help="Analítica de rendimiento de las publicaciones: vistas y likes."),
    ]},
    {"id": "informe", "label": "Informe HTML", "icon": "📄", "actions": [
        A("Generar y abrir", "📄", run="informe", file_key="videos",
          help="Genera el informe HTML del proyecto y lo abre en el navegador."),
    ]},
]


# ---------------------------------------------------------------------------
# Lógica de negocio
# ---------------------------------------------------------------------------

def _project_root() -> str:
    return os.path.abspath(os.path.dirname(__file__))


def run_script(path: str, extra_args: list | None = None, status_cb=None):
    script_path = os.path.abspath(os.path.join(_project_root(), path))
    if not os.path.exists(script_path):
        if status_cb:
            status_cb(f"❌ Archivo no encontrado: {script_path}")
        return

    def _run():
        if status_cb:
            status_cb(f"🚀 Ejecutando: {os.path.basename(script_path)}…")
        try:
            cmd = [sys.executable, script_path] + (extra_args or [])
            subprocess.run(cmd, check=True)
            if status_cb:
                status_cb("✅ Listo.")
        except subprocess.CalledProcessError:
            if status_cb:
                status_cb("❌ Error al ejecutar el script.")
        except Exception as exc:
            if status_cb:
                status_cb(f"❌ Error inesperado: {exc}")

    threading.Thread(target=_run, daemon=True).start()


def abrir_carpeta(path: str, status_cb=None):
    if not os.path.exists(path):
        if status_cb:
            status_cb(f"⚠️ No existe: {path}  —  Ejecuta un análisis primero.")
        return
    try:
        if os.name == "nt":
            os.startfile(path)
        else:
            subprocess.run(["open" if sys.platform == "darwin" else "xdg-open", path])
        if status_cb:
            status_cb(f"📂 Abriendo: {path}")
    except Exception as exc:
        if status_cb:
            status_cb(f"❌ No se pudo abrir: {exc}")


def generar_informe(status_cb=None, csv_videos_preset: str | None = None):
    """Genera informe HTML. Si se pasa csv_videos_preset, omite el selector."""
    import tkinter as tk
    from tkinter import filedialog

    data_dir = os.path.join(_project_root(), "data")

    if csv_videos_preset and os.path.isfile(csv_videos_preset):
        csv_videos = csv_videos_preset
    else:
        try:
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            csv_videos = filedialog.askopenfilename(
                title="Selecciona el CSV de publicaciones del proyecto",
                initialdir=data_dir if os.path.exists(data_dir) else _project_root(),
                filetypes=[
                    ("CSV de vídeos", "*_videos.csv"),
                    ("Todos los CSV", "*.csv"),
                ],
            )
            root.destroy()
        except Exception as exc:
            if status_cb:
                status_cb(f"❌ Error abriendo selector: {exc}")
            return

    if not csv_videos:
        if status_cb:
            status_cb("❌ Cancelado — no se seleccionó ningún proyecto.")
        return

    nombre_base   = os.path.splitext(os.path.basename(csv_videos))[0]
    proyecto_id   = nombre_base.split("_videos")[0]
    cuenta        = proyecto_id.replace("user_", "")
    proyecto_label = f"@{cuenta}"

    if status_cb:
        status_cb(f"🚀 Generando informe para {proyecto_label}…")

    def _run():
        script = os.path.join(_project_root(),
                              "src", "visualization", "generar_informe_html.py")
        try:
            subprocess.run([sys.executable, script, csv_videos], check=True)
        except subprocess.CalledProcessError:
            if status_cb:
                status_cb(f"❌ Error al generar el informe de {proyecto_label}.")
            return
        except Exception as exc:
            if status_cb:
                status_cb(f"❌ Error inesperado: {exc}")
            return

        informe = os.path.join(
            _project_root(), "outputs", proyecto_id,
            "informes", f"{nombre_base}_informe.html",
        )
        if os.path.exists(informe):
            if status_cb:
                status_cb(f"✅ Informe listo — {proyecto_label} — abriendo en el navegador…")
            try:
                if os.name == "nt":
                    os.startfile(informe)
                else:
                    subprocess.run(
                        ["open" if sys.platform == "darwin" else "xdg-open", informe]
                    )
            except Exception:
                pass
        else:
            if status_cb:
                status_cb(f"✅ Generado para {proyecto_label} (no se pudo abrir automáticamente).")

    threading.Thread(target=_run, daemon=True).start()


# ---------------------------------------------------------------------------
# Interfaz gráfica — modo claro, layout apaisado
# ---------------------------------------------------------------------------

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")


class MenuApp(ctk.CTk):

    # Paleta clara
    BG          = "#f0f4f8"
    HEADER_BG   = "#1e3a5f"
    HEADER_TEXT = "#ffffff"
    SECTION_BG  = "#dbe4f0"
    SECTION_TXT = "#1e3a5f"
    CARD_BG     = "#ffffff"
    CARD_HOVER  = "#dbeafe"
    CARD_BORDER = "#cbd5e1"
    TEXT        = "#1e293b"
    SUBTITLE    = "#64748b"
    ACCENT      = "#2563eb"
    STATUS_TXT  = "#64748b"
    EXIT_BG     = "#fee2e2"
    EXIT_HOVER  = "#fca5a5"
    EXIT_TXT    = "#b91c1c"
    OK_COLOR    = "#16a34a"   # verde — archivo disponible
    WARN_COLOR  = "#d97706"   # ámbar — paso pendiente

    def __init__(self):
        super().__init__()
        self.title("TikTok OSINT & Analytics Toolkit")
        self.geometry("960x730")
        self.minsize(820, 600)
        self.configure(fg_color=self.BG)
        self.resizable(True, True)

        # Estado del proyecto activo
        self._active_project: str | None = None      # ruta a data/{proyecto}/
        self._project_files: dict[str, str] = {}     # clave → ruta absoluta

        # Estado de navegación
        self._tab: str = TABS[0][0]                  # "usuario" | "hashtag"
        self._module_id: str = MODULES[0]["id"]      # módulo activo
        self._action_idx: int = 0                    # acción activa dentro del módulo
        self._module_buttons: dict[str, ctk.CTkButton] = {}
        self._action_buttons: list[ctk.CTkButton] = []

        self._restore_state()
        self._build_ui()
        self._refresh_modules()

    # ------------------------------------------------------------------
    # Persistencia ligera del estado de navegación (equivalente de escritorio
    # a "mantener la selección"; sobrevive a reinicios sin dependencias nuevas)
    # ------------------------------------------------------------------
    def _state_path(self) -> str:
        return os.path.join(_project_root(), "data", ".menu_state.json")

    def _restore_state(self):
        try:
            with open(self._state_path(), "r", encoding="utf-8") as f:
                st = json.load(f)
            if st.get("tab") in {t[0] for t in TABS}:
                self._tab = st["tab"]
            if any(m["id"] == st.get("module") for m in MODULES):
                self._module_id = st["module"]
        except Exception:
            pass

    def _save_state(self):
        try:
            os.makedirs(os.path.dirname(self._state_path()), exist_ok=True)
            with open(self._state_path(), "w", encoding="utf-8") as f:
                json.dump({"tab": self._tab, "module": self._module_id}, f)
        except Exception:
            pass

    # ------------------------------------------------------------------
    def _build_ui(self):
        self._build_header()
        self._build_footer()          # anclado abajo primero
        self._build_tabs()
        self._build_project_bar()
        self._build_modules_row()
        self._build_actions_row()
        self._build_action_panel()

    # ------------------------------------------------------------------
    def _build_header(self):
        hdr = ctk.CTkFrame(self, fg_color=self.HEADER_BG, corner_radius=0, height=64)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        ctk.CTkLabel(
            hdr,
            text="🎵  TikTok OSINT & Analytics Toolkit",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=self.HEADER_TEXT,
        ).pack(side="left", padx=24, pady=0)

        # Botones fijos de utilidad (derecha)
        def _hbtn(text, cmd, tip):
            b = ctk.CTkButton(
                hdr, text=text, command=cmd,
                width=110, height=34,
                font=ctk.CTkFont(size=12, weight="bold"),
                fg_color="#2b517a", hover_color="#356094",
                text_color=self.HEADER_TEXT, corner_radius=8,
            )
            b.pack(side="right", padx=(0, 8), pady=14)
            return b

        _hbtn("🗂️ Proyecto",
              lambda: abrir_carpeta(_project_root(), status_cb=self._status),
              "Abrir la carpeta raíz del proyecto")
        _hbtn("📂 Outputs",
              lambda: abrir_carpeta(os.path.join(_project_root(), "outputs"),
                                    status_cb=self._status),
              "Abrir la carpeta de resultados")
        # Cookies destacado (paso 0)
        cookies = ctk.CTkButton(
            hdr, text="🔑 Cookies",
            command=lambda: run_script("src/scrapers/1-guardar_sesion.py",
                                       status_cb=self._status),
            width=120, height=34,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=self.ACCENT, hover_color="#1d4ed8",
            text_color="#ffffff", corner_radius=8,
        )
        cookies.pack(side="right", padx=(0, 14), pady=14)

    # ------------------------------------------------------------------
    def _build_tabs(self):
        """Nivel 1 — selector primario Usuario | Hashtag."""
        row = ctk.CTkFrame(self, fg_color=self.BG)
        row.pack(fill="x", padx=16, pady=(14, 4))

        self._tab_values = [f"{ico}  {lbl}" for _id, lbl, ico in TABS]
        self._tab_by_value = {f"{ico}  {lbl}": _id for _id, lbl, ico in TABS}
        self._value_by_tab = {_id: f"{ico}  {lbl}" for _id, lbl, ico in TABS}

        self._tab_seg = ctk.CTkSegmentedButton(
            row,
            values=self._tab_values,
            command=self._on_tab_change,
            font=ctk.CTkFont(size=14, weight="bold"),
            height=40,
            fg_color="#94a3b8",
            selected_color=self.HEADER_BG,      # navy — activo
            selected_hover_color="#2b517a",
            unselected_color="#64748b",          # slate — inactivo
            unselected_hover_color="#475569",
            text_color="#ffffff",                # blanco: legible en ambos estados
        )
        self._tab_seg.pack(fill="x")
        self._tab_seg.set(self._value_by_tab[self._tab])

    def _on_tab_change(self, value: str):
        self._tab = self._tab_by_value.get(value, self._tab)
        self._save_state()
        self._refresh_modules()

    # ------------------------------------------------------------------
    def _build_project_bar(self):
        """Barra de proyecto activo — selector único para todo el menú."""
        bar = ctk.CTkFrame(self, fg_color=self.SECTION_BG, corner_radius=8)
        bar.pack(fill="x", padx=16, pady=(0, 6))

        # Icono + etiqueta fija
        ctk.CTkLabel(
            bar, text="📁",
            font=ctk.CTkFont(size=14),
        ).pack(side="left", padx=(10, 2), pady=7)

        ctk.CTkLabel(
            bar, text="Proyecto activo:",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=self.SECTION_TXT,
        ).pack(side="left", padx=(0, 8))

        # Botón cambiar (derecha)
        ctk.CTkButton(
            bar,
            text="Cambiar proyecto",
            command=self._select_project,
            width=148, height=28,
            font=ctk.CTkFont(size=11),
            fg_color=self.ACCENT,
            hover_color="#1d4ed8",
            corner_radius=6,
        ).pack(side="right", padx=10, pady=6)

        # Nombre + detalle (centro, se actualizan)
        info = ctk.CTkFrame(bar, fg_color="transparent")
        info.pack(side="left", fill="x", expand=True)

        self._project_label = ctk.CTkLabel(
            info,
            text="— ninguno seleccionado —",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=self.TEXT, anchor="w",
        )
        self._project_label.pack(anchor="w")

        self._project_detail = ctk.CTkLabel(
            info,
            text='Pulsa "Cambiar proyecto" para seleccionar',
            font=ctk.CTkFont(size=9),
            text_color=self.SUBTITLE, anchor="w",
        )
        self._project_detail.pack(anchor="w")

    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # Nivel 2 — módulos (fila horizontal con scroll si no caben)
    # ------------------------------------------------------------------
    def _build_modules_row(self):
        outer = ctk.CTkFrame(self, fg_color=self.BG)
        outer.pack(fill="x", padx=16, pady=(6, 2))

        ctk.CTkLabel(
            outer, text="Módulos",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=self.SUBTITLE, anchor="w",
        ).pack(anchor="w", pady=(0, 2))

        self._modules_scroll = ctk.CTkScrollableFrame(
            outer, fg_color=self.SECTION_BG, corner_radius=8,
            orientation="horizontal", height=58,
        )
        self._modules_scroll.pack(fill="x")

        self._module_buttons = {}
        for mod in MODULES:
            has_multi = len(self._module_actions(mod)) > 1
            caret = "  ▾" if has_multi else ""
            btn = ctk.CTkButton(
                self._modules_scroll,
                text=f"{mod['icon']}  {mod['label']}{caret}",
                command=lambda mid=mod["id"]: self._select_module(mid),
                width=150, height=40,
                font=ctk.CTkFont(size=12, weight="bold"),
                fg_color=self.CARD_BG, hover_color=self.CARD_HOVER,
                text_color=self.TEXT, corner_radius=8,
                border_width=1, border_color=self.CARD_BORDER,
            )
            btn.pack(side="left", padx=4, pady=8)
            self._module_buttons[mod["id"]] = btn

    # ------------------------------------------------------------------
    # Nivel 3 — acciones del módulo activo (solo si hay más de una)
    # ------------------------------------------------------------------
    def _build_actions_row(self):
        # height=1 + pack_propagate: colapsa cuando no hay acciones (módulo de una
        # sola acción) y crece automáticamente al añadir botones de nivel 3.
        self._actions_frame = ctk.CTkFrame(self, fg_color=self.BG, height=1)
        self._actions_frame.pack(fill="x", padx=16, pady=(4, 2))
        # Su contenido se reconstruye en _refresh_actions().

    # ------------------------------------------------------------------
    # Panel central — breadcrumb + descripción + estado + Ejecutar
    # ------------------------------------------------------------------
    def _build_action_panel(self):
        panel = ctk.CTkFrame(self, fg_color=self.CARD_BG, corner_radius=12,
                             border_width=1, border_color=self.CARD_BORDER)
        panel.pack(fill="both", expand=True, padx=16, pady=(6, 4))

        self._breadcrumb = ctk.CTkLabel(
            panel, text="",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=self.ACCENT, anchor="w",
        )
        self._breadcrumb.pack(anchor="w", padx=20, pady=(16, 2))

        self._panel_title = ctk.CTkLabel(
            panel, text="",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=self.TEXT, anchor="w",
        )
        self._panel_title.pack(anchor="w", padx=20, pady=(2, 2))

        self._panel_help = ctk.CTkLabel(
            panel, text="",
            font=ctk.CTkFont(size=12),
            text_color=self.SUBTITLE, anchor="w",
            justify="left", wraplength=820,
        )
        self._panel_help.pack(anchor="w", padx=20, pady=(0, 10))

        self._panel_file = ctk.CTkLabel(
            panel, text="",
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w", justify="left", wraplength=820,
        )
        self._panel_file.pack(anchor="w", padx=20, pady=(0, 12))

        self._run_btn = ctk.CTkButton(
            panel, text="▶  Ejecutar",
            command=self._run_current_action,
            width=200, height=46,
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color=self.ACCENT, hover_color="#1d4ed8",
            corner_radius=10,
        )
        self._run_btn.pack(anchor="w", padx=20, pady=(0, 18))

    # ------------------------------------------------------------------
    # Lógica de navegación
    # ------------------------------------------------------------------
    def _module_by_id(self, mid: str) -> dict:
        return next(m for m in MODULES if m["id"] == mid)

    def _module_actions(self, mod: dict) -> list[dict]:
        """Acciones de un módulo, resolviendo per_tab según la pestaña activa."""
        if "per_tab" in mod:
            return [mod["per_tab"][self._tab]]
        return mod["actions"]

    def _current_module(self) -> dict:
        return self._module_by_id(self._module_id)

    def _current_action(self) -> dict:
        actions = self._module_actions(self._current_module())
        idx = min(self._action_idx, len(actions) - 1)
        return actions[idx]

    def _refresh_modules(self):
        """Resalta el módulo activo y refresca acciones del que cambia con la pestaña."""
        for mid, btn in self._module_buttons.items():
            mod = self._module_by_id(mid)
            active = (mid == self._module_id)
            # El módulo "captura" cambia de etiqueta según la pestaña
            if "per_tab" in mod:
                act = mod["per_tab"][self._tab]
                btn.configure(text=f"{mod['icon']}  {mod['label']}")
            btn.configure(
                fg_color=self.HEADER_BG if active else self.CARD_BG,
                text_color="#ffffff" if active else self.TEXT,
                border_color=self.ACCENT if active else self.CARD_BORDER,
            )
        self._refresh_actions()

    def _select_module(self, mid: str):
        self._module_id = mid
        self._action_idx = 0
        self._save_state()
        self._refresh_modules()

    def _refresh_actions(self):
        """Reconstruye la fila de nivel 3 según el módulo activo."""
        for w in self._actions_frame.winfo_children():
            w.destroy()
        self._action_buttons = []

        actions = self._module_actions(self._current_module())
        if len(actions) > 1:
            ctk.CTkLabel(
                self._actions_frame, text="Acciones",
                font=ctk.CTkFont(size=10, weight="bold"),
                text_color=self.SUBTITLE,
            ).pack(side="left", padx=(0, 8))
            for idx, act in enumerate(actions):
                active = (idx == min(self._action_idx, len(actions) - 1))
                b = ctk.CTkButton(
                    self._actions_frame,
                    text=f"{act['icon']}  {act['label']}",
                    command=lambda i=idx: self._select_action(i),
                    width=170, height=34,
                    font=ctk.CTkFont(size=12,
                                     weight="bold" if active else "normal"),
                    fg_color=self.ACCENT if active else self.CARD_BG,
                    hover_color="#1d4ed8" if active else self.CARD_HOVER,
                    text_color="#ffffff" if active else self.TEXT,
                    border_width=0 if active else 1,
                    border_color=self.CARD_BORDER, corner_radius=8,
                )
                b.pack(side="left", padx=4)
                self._action_buttons.append(b)
        self._refresh_panel()

    def _select_action(self, idx: int):
        self._action_idx = idx
        self._refresh_actions()

    def _refresh_panel(self):
        """Actualiza breadcrumb, descripción, estado del CSV y botón Ejecutar."""
        mod = self._current_module()
        act = self._current_action()
        tab_label = dict((t[0], t[1]) for t in TABS)[self._tab]

        crumb = f"{tab_label}  ›  {mod['label']}"
        if len(self._module_actions(mod)) > 1:
            crumb += f"  ›  {act['label']}"
        self._breadcrumb.configure(text=crumb)
        self._panel_title.configure(text=f"{act['icon']}  {act['label']}")
        self._panel_help.configure(text=act.get("help", ""))

        # Estado del archivo requerido
        file_key = act.get("file_key")
        ready = True
        if file_key:
            path = self._resolve(file_key)
            if path:
                self._panel_file.configure(
                    text=f"✓ Archivo listo: {os.path.basename(path)}",
                    text_color=self.OK_COLOR,
                )
            elif self._active_project:
                ready = False
                self._panel_file.configure(
                    text=f"⚠ Falta el archivo requerido — {self._file_hint(file_key)}",
                    text_color=self.WARN_COLOR,
                )
            else:
                self._panel_file.configure(
                    text="ℹ Sin proyecto activo: el script abrirá su propio selector de archivo.",
                    text_color=self.SUBTITLE,
                )
        else:
            self._panel_file.configure(
                text="ℹ Esta acción no necesita un proyecto seleccionado.",
                text_color=self.SUBTITLE,
            )

        self._run_btn.configure(
            state="normal" if ready else "disabled",
            fg_color=self.ACCENT if ready else "#cbd5e1",
        )

    @staticmethod
    def _file_hint(file_key: str) -> str:
        return {
            "videos":    "ejecuta primero la Captura (perfil o hashtag).",
            "comments":  "ejecuta primero «Comentarios → Extraer comentarios».",
            "sentiment": "ejecuta primero «Sentimiento IA → Analizar sentimiento».",
            "enriched":  "ejecuta primero «Edad de cuentas → Calcular edades».",
        }.get(file_key, "ejecuta el paso previo del flujo.")

    def _run_current_action(self):
        self._run_action(self._current_action())

    def _run_action(self, act: dict):
        if act.get("run") == "informe":
            generar_informe(status_cb=self._status,
                            csv_videos_preset=self._resolve("videos"))
            return
        if act.get("file_key"):
            self._run_for_project(act["script"], act["file_key"])
        else:
            run_script(act["script"], status_cb=self._status)

    # ------------------------------------------------------------------
    def _build_footer(self):
        foot = ctk.CTkFrame(self, fg_color=self.BG)
        foot.pack(side="bottom", fill="x", padx=16, pady=(4, 12))

        self._status_var = ctk.StringVar(value="Listo. Selecciona un proyecto y una opción.")
        ctk.CTkLabel(
            foot,
            textvariable=self._status_var,
            font=ctk.CTkFont(size=11),
            text_color=self.STATUS_TXT,
            anchor="w",
        ).pack(side="left", fill="x", expand=True)

        ctk.CTkButton(
            foot,
            text="❌  Salir",
            width=110, height=34,
            fg_color=self.EXIT_BG,
            hover_color=self.EXIT_HOVER,
            text_color=self.EXIT_TXT,
            font=ctk.CTkFont(size=12, weight="bold"),
            corner_radius=8,
            command=self.destroy,
        ).pack(side="right")

    # ------------------------------------------------------------------
    # Gestión del proyecto activo
    # ------------------------------------------------------------------

    def _scan_project_files(self, folder: str) -> dict[str, str]:
        """Clasifica los CSV de un proyecto por tipo.

        Orden de prioridad (más específico primero para evitar falsos positivos):
          enriched   — *enriquecido_fechas_creacion*.csv
          sentiment  — *con_sentimiento*.csv
          comments   — *comentarios_api*.csv  (excluye lookup/enriquecido/sentimiento)
          videos     — *videos_api*.csv        (excluye comentarios)
        Los archivos _lookup_fechas_creacion y _checkpoint se ignoran.
        """
        result = {}
        try:
            for f in sorted(os.listdir(folder)):
                if not f.endswith(".csv"):
                    continue
                p  = os.path.join(folder, f)
                nl = f.lower()
                # Archivos internos/auxiliares — ignorar
                if "lookup_fechas_creacion" in nl or "_checkpoint" in nl:
                    continue
                if "enriquecido_fechas_creacion" in nl:
                    result["enriched"] = p
                elif "con_sentimiento" in nl:
                    result["sentiment"] = p
                elif "comentarios_api" in nl:
                    result["comments"] = p
                elif "videos_api" in nl and "comentarios" not in nl:
                    result["videos"] = p
        except OSError:
            pass
        return result

    def _set_project(self, folder: str):
        """Establece el proyecto activo y refresca la barra."""
        self._active_project = folder
        self._project_files  = self._scan_project_files(folder)
        name = os.path.basename(folder)
        self._project_label.configure(text=name)

        # Indicadores de qué pasos están completados
        icons = []
        if "videos"    in self._project_files: icons.append("📹 vídeos")
        if "comments"  in self._project_files: icons.append("💬 comentarios")
        if "sentiment" in self._project_files: icons.append("🤖 sentimiento")
        if "enriched"  in self._project_files: icons.append("📅 edad cuentas")
        detail = "  ·  ".join(icons) if icons else "sin archivos reconocidos"
        self._project_detail.configure(text=detail)
        self._status(f"📁 Proyecto activo: {name}  ({len(self._project_files)} archivos)")
        # Refrescar el panel para actualizar el estado del archivo requerido
        if hasattr(self, "_run_btn"):
            self._refresh_panel()

    def _select_project(self):
        """Muestra diálogo para elegir proyecto de data/ o carpeta manual."""
        data_dir = os.path.join(_project_root(), "data")

        # Obtener lista de proyectos (subcarpetas de data/)
        try:
            proyectos = sorted([
                d for d in os.listdir(data_dir)
                if os.path.isdir(os.path.join(data_dir, d))
            ])
        except OSError:
            proyectos = []

        if not proyectos:
            # Sin proyectos en data/ → abrir selector de carpeta
            self._pick_folder_manually(data_dir)
            return

        # Diálogo CTK con lista de proyectos
        dlg = ctk.CTkToplevel(self)
        dlg.title("Seleccionar proyecto")
        dlg.geometry("500x360")
        dlg.resizable(False, False)
        dlg.grab_set()
        dlg.attributes("-topmost", True)
        dlg.configure(fg_color=self.BG)

        ctk.CTkLabel(
            dlg, text="Elige el proyecto sobre el que quieres trabajar:",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=self.TEXT,
        ).pack(padx=20, pady=(16, 6), anchor="w")

        # Lista scrollable con radio buttons
        scroll = ctk.CTkScrollableFrame(dlg, fg_color=self.CARD_BG,
                                        corner_radius=8, height=200)
        scroll.pack(fill="x", padx=20, pady=4)

        # Preseleccionar el activo si ya hay uno
        current_name = os.path.basename(self._active_project) if self._active_project else ""
        default = current_name if current_name in proyectos else proyectos[0]
        selected = ctk.StringVar(value=default)

        for p in proyectos:
            folder = os.path.join(data_dir, p)
            files  = self._scan_project_files(folder)
            icons  = ""
            icons += "📹" if "videos"    in files else "○ "
            icons += " 💬" if "comments" in files else " ○"
            icons += " 🤖" if "sentiment"in files else " ○"
            icons += " 📅" if "enriched" in files else " ○"
            ctk.CTkRadioButton(
                scroll,
                text=f" {icons}   {p}",
                variable=selected, value=p,
                font=ctk.CTkFont(size=11),
                text_color=self.TEXT,
            ).pack(anchor="w", pady=3, padx=8)

        # Leyenda
        ctk.CTkLabel(
            dlg,
            text="📹 vídeos  💬 comentarios  🤖 sentimiento  📅 edad de cuentas  ·  ○ = pendiente",
            font=ctk.CTkFont(size=9),
            text_color=self.SUBTITLE,
        ).pack(pady=(4, 2))

        # Botones
        btn_row = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=(6, 16))

        def _confirm():
            name = selected.get()
            if name:
                self._set_project(os.path.join(data_dir, name))
            dlg.destroy()

        def _manual():
            dlg.destroy()
            self._pick_folder_manually(data_dir)

        ctk.CTkButton(
            btn_row, text="Aceptar", command=_confirm,
            width=120, fg_color=self.ACCENT, hover_color="#1d4ed8",
        ).pack(side="right", padx=(4, 0))

        ctk.CTkButton(
            btn_row, text="Carpeta manual…", command=_manual,
            width=150, fg_color="transparent", border_width=1,
            text_color=self.TEXT, hover_color=self.CARD_HOVER,
        ).pack(side="right", padx=4)

        ctk.CTkButton(
            btn_row, text="Cancelar", command=dlg.destroy,
            width=100, fg_color="transparent", border_width=1,
            text_color=self.SUBTITLE, hover_color=self.CARD_HOVER,
        ).pack(side="left")

    def _pick_folder_manually(self, initial_dir: str):
        """Selector nativo de carpeta como fallback."""
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        folder = filedialog.askdirectory(
            title="Selecciona la carpeta del proyecto",
            initialdir=initial_dir if os.path.exists(initial_dir) else _project_root(),
        )
        root.destroy()
        if folder:
            self._set_project(folder)

    def _resolve(self, key: str) -> str | None:
        """Devuelve la ruta del archivo del tipo indicado, o None."""
        return self._project_files.get(key)

    def _run_for_project(self, script: str, file_key: str,
                         extra_args: list | None = None):
        """Ejecuta un script. Si hay proyecto activo pasa el archivo como arg.
        Si no hay proyecto, el script abre su propio selector de archivo."""
        if not self._active_project:
            # Sin proyecto → el script abre su filedialog propio
            run_script(script, extra_args=extra_args, status_cb=self._status)
            return

        path = self._resolve(file_key)
        if not path:
            _nombres = {
                "videos":    "CSV de vídeos (_videos_api.csv) — ejecuta el paso 1 o 2 primero",
                "comments":  "CSV de comentarios (_comentarios_api.csv) — ejecuta el paso 3 primero",
                "sentiment": "CSV con sentimiento — ejecuta el paso 7 (Sentimiento con IA) primero",
                "enriched":  "CSV enriquecido — ejecuta el paso 4 (Edad de Cuentas) primero",
            }
            self._status(f"⚠️  No encontrado: {_nombres.get(file_key, file_key)}")
            return

        args = [path] + (extra_args or [])
        run_script(script, extra_args=args, status_cb=self._status)

    # ------------------------------------------------------------------
    # Helpers de construcción de UI
    # ------------------------------------------------------------------

    def _status(self, msg: str):
        self.after(0, self._status_var.set, msg)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    app = MenuApp()
    app.mainloop()


if __name__ == "__main__":
    main()
