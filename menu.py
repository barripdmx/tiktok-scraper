# -*- coding: utf-8 -*-
"""
TikTok OSINT & Analytics Toolkit — consola de control.

Rediseño UX (v3). Cambios frente a la versión de navegación horizontal:

  · Navegación de 3 niveles (pestaña › módulo › acción) sustituida por una
    barra lateral única agrupada por fases del flujo. Toda acción está a un
    solo clic; desaparece el scroll horizontal oculto y el salto de layout
    que provocaba la fila de nivel 3 al aparecer/desaparecer.
  · Cada paso muestra su estado real derivado de los archivos del proyecto:
    ✓ hecho · ● listo para ejecutar · ○ bloqueado por un paso previo.
  · Los archivos del proyecto se reescanean al terminar cada proceso, así el
    estado deja de quedarse obsoleto (antes había que reseleccionar proyecto).
  · Seguimiento del proceso hijo por sondeo en el hilo de UI (sin hilos ni
    callbacks cruzados), con cronómetro, botón Detener y registro de actividad.
  · Un único root Tk: los diálogos cuelgan de la ventana principal.
  · Tema claro/oscuro nativo mediante colores en tupla (claro, oscuro).

Nota de diseño: los scripts se lanzan en su propia ventana de consola porque
varios son interactivos (piden proveedor de IA, nº de vídeos, rutas…). Por eso
el panel "Actividad" registra eventos de ejecución, no la salida estándar:
capturarla con una tubería bloquearía esos prompts.

La navegación se genera a partir de GROUPS/ACTIONS; para añadir una opción
basta con declarar un dict nuevo.
"""

import os
import sys
import json
import time
import queue
import threading
import subprocess
from datetime import datetime

import customtkinter as ctk

# ---------------------------------------------------------------------------
# Paleta — cada color es (claro, oscuro); CustomTkinter conmuta solo.
# ---------------------------------------------------------------------------

BG          = ("#eef2f7", "#0f141b")
SURFACE     = ("#ffffff", "#171e28")
SURFACE_ALT = ("#e4ebf3", "#1e2733")
BORDER      = ("#d3dce7", "#2b3644")
HEADER      = ("#14293f", "#111823")
ON_HEADER   = ("#ffffff", "#e6edf5")
TEXT        = ("#0f172a", "#e6edf5")
MUTED       = ("#64748b", "#8b9bb0")
ACCENT      = ("#2563eb", "#3b82f6")
ACCENT_HOV  = ("#1d4ed8", "#2563eb")
ACCENT_SOFT = ("#dbeafe", "#1c2f4a")
OK          = ("#059669", "#34d399")
WARN        = ("#c2410c", "#fb923c")
DANGER      = ("#dc2626", "#f87171")
DANGER_SOFT = ("#fee2e2", "#3b1d1d")
DISABLED    = ("#cbd5e1", "#334155")

FONT_FAMILY = "Segoe UI" if sys.platform == "win32" else None


def _f(size=12, weight="normal"):
    """CTkFont con la familia del sistema. Tk exige un tamaño entero."""
    size = int(round(size))
    if FONT_FAMILY:
        return ctk.CTkFont(family=FONT_FAMILY, size=size, weight=weight)
    return ctk.CTkFont(size=size, weight=weight)


# ---------------------------------------------------------------------------
# Modelo declarativo del flujo
#
#   requires  claves de archivo que el paso necesita como entrada
#   produces  clave de archivo que el paso genera (sirve para marcarlo ✓)
#   arg_key   clave cuyo path se pasa como argv[1] al script
#   inputs    campos que el menú pide y pasa al script como flags
#   console   True si el script necesita teclado propio (ver nota abajo)
#
# Salida de los scripts: por defecto se captura y se muestra en el panel
# "Actividad" en directo. Solo dos pasos abren una consola aparte, porque leen
# del teclado y una tubería los dejaría bloqueados sin que se vea el prompt:
# la captura de cookies (espera a que inicies sesión) y el análisis de
# sentimiento (te hace elegir proveedor de IA).
# ---------------------------------------------------------------------------

def F(flag, label, placeholder, *, required=False, kind="text", hint=""):
    """Campo de entrada del panel; su valor viaja al script como `flag valor`."""
    return {"flag": flag, "label": label, "placeholder": placeholder,
            "required": required, "kind": kind, "hint": hint}

GROUPS = [
    ("setup",   "Configuración"),
    ("captura", "1 · Captura"),
    ("analisis", "2 · Análisis"),
    ("osint",   "3 · Investigación"),
    ("salida",  "4 · Resultados"),
]

ACTIONS = [
    dict(
        id="cookies", group="setup", icon="🔑", label="Sesión de TikTok",
        script="src/scrapers/1-guardar_sesion.py",
        requires=[], produces=None, arg_key=None, console=True,
        help="Abre un navegador para que inicies sesión en TikTok y guarda las "
             "cookies en secrets/. Es el paso 0: sin sesión válida los scrapers "
             "obtienen resultados incompletos o vacíos.",
    ),

    dict(
        id="perfil", group="captura", icon="👤", label="Perfil de usuario",
        script="src/scrapers/1_tiktok_scraper_user.py",
        requires=[], produces="videos", arg_key=None,
        help="Extrae todos los vídeos publicados por una cuenta de TikTok.",
        inputs=[
            F("--user", "Cuenta de TikTok", "sanchezcastejon", required=True,
              hint="Sin la @. Solo el nombre de usuario del perfil."),
            F("--desde", "Publicados desde", "dd-mm-aaaa", kind="date"),
            F("--hasta", "Publicados hasta", "dd-mm-aaaa", kind="date"),
        ],
    ),
    dict(
        id="hashtag", group="captura", icon="#", label="Hashtag o búsqueda",
        script="src/scrapers/2_tiktok_scraper_hastag_api.py",
        requires=[], produces="videos", arg_key=None,
        help="Busca y extrae vídeos por hashtag o palabra clave mediante la API.",
        inputs=[
            F("--query", "Términos de búsqueda", "therians, otherkin", required=True,
              hint="Sin #. Varios términos separados por coma; coincidencia literal exacta."),
            F("--desde", "Publicados desde", "dd-mm-aaaa", kind="date"),
            F("--hasta", "Publicados hasta", "dd-mm-aaaa", kind="date"),
        ],
    ),
    dict(
        id="comentarios", group="captura", icon="💬", label="Comentarios",
        script="src/scrapers/2_tiktok_scraper_comentarios_api.py",
        requires=["videos"], produces="comments", arg_key="videos",
        help="Descarga los comentarios de cada vídeo capturado. Es el paso más "
             "lento del flujo: puede tardar horas en proyectos grandes.",
    ),

    dict(
        id="publicaciones", group="analisis", icon="📈", label="Publicaciones",
        script="src/analysis/analitica_publicaciones.py",
        requires=["videos"], produces=None, arg_key="videos",
        help="Analítica de rendimiento de las publicaciones: vistas, likes, "
             "evolución temporal y vídeos destacados.",
    ),
    dict(
        id="nubes", group="analisis", icon="🗣️", label="Comentarios (nubes)",
        script="src/analysis/analitica_comentarios.py",
        requires=["comments"], produces=None, arg_key="comments",
        help="Nubes de palabras, términos frecuentes y métricas descriptivas "
             "sobre el corpus de comentarios.",
    ),
    dict(
        id="sentimiento", group="analisis", icon="🤖", label="Sentimiento IA",
        script="src/analysis/analizar_sentimiento.py",
        requires=["comments"], produces="sentiment", arg_key="comments", console=True,
        help="Clasifica cada comentario con IA. El script te dejará elegir el "
             "proveedor: RoBERTa (local), Groq o Mistral. Groq y Mistral añaden "
             "sesgo, arquetipo, intención y pain points; RoBERTa solo sentimiento.",
    ),

    dict(
        id="edad", group="osint", icon="📅", label="Edad de las cuentas",
        script="src/utils/enriquecer_csv_fechas_creacion.py",
        requires=["comments"], produces="enriched", arg_key="comments",
        help="Enriquece a cada comentarista con la fecha de creación de su "
             "cuenta. Base para la detección de cuentas sospechosas.",
    ),
    dict(
        id="patrones", group="osint", icon="🕵️", label="Patrones de cuentas",
        script="src/visualization/graficas_patrones_cuentas.py",
        requires=["enriched"], produces=None, arg_key="enriched",
        help="Detecta indicios de automatización: antigüedad anómala, ráfagas "
             "de creación, perfiles vacíos y actividad concentrada.",
    ),
    dict(
        id="grafo", group="osint", icon="🕸️", label="Grafo de redes (GEXF)",
        script="src/visualization/crear_gexf.py",
        requires=["comments"], produces=None, arg_key="comments",
        help="Genera un grafo de interacciones en formato GEXF, listo para "
             "abrir y analizar en Gephi.",
    ),

    dict(
        id="multidim", group="salida", icon="🧠", label="Gráficas multidimensión",
        script="src/visualization/grafica_multidimensional.py",
        requires=["sentiment"], produces=None, arg_key="sentiment",
        help="Set completo de gráficas sobre las dimensiones del análisis con "
             "IA: sesgo, arquetipo, intención y pain points.",
    ),
    dict(
        id="informe", group="salida", icon="📄", label="Informe HTML",
        script="src/visualization/generar_informe_html.py",
        requires=["videos"], produces=None, arg_key="videos", opens_report=True,
        help="Compila todos los resultados disponibles en un informe HTML "
             "autocontenido y lo abre en el navegador.",
    ),
]

# Etiquetas legibles de cada tipo de archivo, y qué paso lo genera.
FILE_LABELS = {
    "videos":    ("CSV de vídeos", "Perfil de usuario» o «Hashtag o búsqueda"),
    "comments":  ("CSV de comentarios", "Comentarios"),
    "sentiment": ("CSV con sentimiento", "Sentimiento IA"),
    "enriched":  ("CSV con edad de cuentas", "Edad de las cuentas"),
}

# Chips que resumen el estado del proyecto en la barra superior.
PROJECT_CHIPS = [
    ("videos",    "📹", "vídeos"),
    ("comments",  "💬", "comentarios"),
    ("sentiment", "🤖", "sentimiento"),
    ("enriched",  "📅", "edad cuentas"),
]


# ---------------------------------------------------------------------------
# Utilidades de dominio
# ---------------------------------------------------------------------------

def _project_root() -> str:
    return os.path.abspath(os.path.dirname(__file__))


# Archivos auxiliares que nunca son la salida de un paso.
IGNORE_MARKERS = ("lookup_fechas_creacion", "_checkpoint")

# Nombres que delatan una prueba o un descarte: se aceptan, pero pierden
# frente a cualquier archivo equivalente que no los lleve.
JUNK_MARKERS = ("prueba", "_test", "debug", "_old", "_lite", "backup", "_bak")

# Patrones por tipo, de más específico (formato actual) a más laxo (histórico).
# Un proyecto antiguo usa «_videos.csv» / «_comments.csv»; el actual, «_api».
COMMENT_PATTERNS = (("comentarios_api", 3), ("comentarios", 2), ("comments", 1))
VIDEO_PATTERNS = (("videos_api", 3), ("videos", 1))

# Riqueza del CSV de sentimiento por proveedor: mistral/groq/gemini rellenan
# todas las dimensiones (sesgo, arquetipo…); roberta solo 'sentiment'.
SENTIMENT_PROVIDERS = (("mistral", 4), ("gemini", 3), ("groq", 2), ("roberta", 1))


def _match_score(name: str, patterns) -> int:
    """Mejor puntuación de los patrones que aparecen en el nombre; 0 si ninguno."""
    return max((score for pat, score in patterns if pat in name), default=0)


def scan_project_files(folder: str) -> dict[str, str]:
    """Clasifica los CSV de un proyecto por tipo de salida del flujo.

    Cada archivo se asigna a la categoría más específica que encaja, en este
    orden (evita falsos positivos: «sanchez_videos_comments.csv» contiene
    «videos» pero es un CSV de comentarios):

        enriched  → *enriquecido_fechas_creacion*
        sentiment → *con_sentimiento*
        comments  → *comentarios_api* > *comentarios* > *comments*
        videos    → *videos_api* > *videos*   (si no es de comentarios)

    Cuando varios archivos compiten por la misma categoría gana el de patrón
    más específico; a igualdad, el más grande, que es el dataset real frente a
    los recortes de prueba.
    """
    best: dict[str, tuple[int, int, str]] = {}   # tipo → (patrón, tamaño, ruta)

    def offer(key: str, path: str, name: str, rank: int):
        if any(j in name for j in JUNK_MARKERS):
            rank -= 100
        try:
            size = os.path.getsize(path)
        except OSError:
            size = 0
        current = best.get(key)
        if current is None or (rank, size) > (current[0], current[1]):
            best[key] = (rank, size, path)

    try:
        entries = sorted(os.listdir(folder))
    except OSError:
        return {}

    for f in entries:
        if not f.endswith(".csv"):
            continue
        nl = f.lower()
        if any(m in nl for m in IGNORE_MARKERS):
            continue
        p = os.path.join(folder, f)

        if "enriquecido_fechas_creacion" in nl:
            offer("enriched", p, nl, 1)
        elif "con_sentimiento" in nl:
            offer("sentiment", p, nl, _match_score(nl, SENTIMENT_PROVIDERS))
        elif (score := _match_score(nl, COMMENT_PATTERNS)):
            offer("comments", p, nl, score)
        elif (score := _match_score(nl, VIDEO_PATTERNS)):
            offer("videos", p, nl, score)

    return {k: v[2] for k, v in best.items()}


def open_path(path: str) -> tuple[bool, str]:
    """Abre una ruta con la aplicación del sistema. Devuelve (ok, mensaje)."""
    if not os.path.exists(path):
        return False, f"No existe: {path}"
    try:
        if os.name == "nt":
            os.startfile(path)
        else:
            subprocess.run(["open" if sys.platform == "darwin" else "xdg-open", path])
        return True, f"Abriendo {os.path.basename(path) or path}"
    except Exception as exc:
        return False, f"No se pudo abrir: {exc}"


# ---------------------------------------------------------------------------
# Tooltip ligero
# ---------------------------------------------------------------------------

class Tooltip:
    """Globo de ayuda sobre cualquier widget, con retardo."""

    def __init__(self, widget, text: str, delay: int = 550):
        self.widget, self.text, self.delay = widget, text, delay
        self._after_id = None
        self._tip = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<Button-1>", self._hide, add="+")

    def _schedule(self, _=None):
        self._cancel()
        self._after_id = self.widget.after(self.delay, self._show)

    def _cancel(self):
        if self._after_id:
            try:
                self.widget.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def _show(self):
        if self._tip or not self.text:
            return
        try:
            x = self.widget.winfo_rootx() + 14
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        except Exception:
            return
        self._tip = tip = ctk.CTkToplevel(self.widget)
        tip.wm_overrideredirect(True)
        tip.wm_geometry(f"+{x}+{y}")
        tip.attributes("-topmost", True)
        frame = ctk.CTkFrame(tip, fg_color=SURFACE, corner_radius=6,
                             border_width=1, border_color=BORDER)
        frame.pack()
        ctk.CTkLabel(frame, text=self.text, font=_f(11), text_color=TEXT,
                     justify="left", wraplength=280).pack(padx=10, pady=6)

    def _hide(self, _=None):
        self._cancel()
        if self._tip:
            try:
                self._tip.destroy()
            except Exception:
                pass
            self._tip = None


# ---------------------------------------------------------------------------
# Aplicación
# ---------------------------------------------------------------------------

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

# Estados de un paso
DONE, READY, BLOCKED, RUNNING = "done", "ready", "blocked", "running"

STATE_GLYPH = {
    DONE:    ("✓", OK),
    READY:   ("●", ACCENT),
    BLOCKED: ("○", MUTED),
    RUNNING: ("▶", ACCENT),
}


class MenuApp(ctk.CTk):

    def __init__(self):
        super().__init__()
        self.title("TikTok OSINT & Analytics Toolkit")
        self.geometry("1180x830")
        self.minsize(1000, 680)
        self.configure(fg_color=BG)

        # Estado del proyecto activo
        self._project: str | None = None
        self._files: dict[str, str] = {}

        # Estado de ejecución (sondeo en el hilo de UI, sin hilos auxiliares)
        self._proc: subprocess.Popen | None = None
        self._proc_action: dict | None = None
        self._t0: float = 0.0
        self._poll_job = None
        self._stopping = False   # parada pedida por el usuario, no un fallo

        # La salida del script la lee un hilo y la deja en esta cola; la UI la
        # vacía en su propio ciclo. El hilo nunca toca widgets.
        self._logq: queue.Queue[str] = queue.Queue()
        self._reader: threading.Thread | None = None

        # Navegación
        self._current_id: str = ACTIONS[0]["id"]
        self._rows: dict[str, dict] = {}   # id → widgets de la fila lateral

        # Valores de los campos por acción: sobreviven a la navegación y a la
        # sesión, para no reescribir la búsqueda cada vez.
        self._input_values: dict[str, dict[str, str]] = {}
        self._entries: dict[str, ctk.StringVar] = {}

        self._restore_state()
        self._build_ui()
        if self._project:
            self._project_label.configure(text=os.path.basename(self._project))
        self._render_chips()
        self._select(self._current_id)
        self._bind_shortcuts()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ==================================================================
    # Construcción de la interfaz
    # ==================================================================

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self._build_header()      # fila 0
        self._build_project_bar()  # fila 1
        self._build_body()        # fila 2
        self._build_status_bar()  # fila 3

    # ------------------------------------------------------------------
    def _build_header(self):
        hdr = ctk.CTkFrame(self, fg_color=HEADER, corner_radius=0, height=62)
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.grid_propagate(False)

        ctk.CTkLabel(hdr, text="🎵  TikTok OSINT & Analytics Toolkit",
                     font=_f(19, "bold"), text_color=ON_HEADER
                     ).pack(side="left", padx=22)

        def util(text, cmd, tip, width=118):
            b = ctk.CTkButton(hdr, text=text, command=cmd, width=width, height=34,
                              font=_f(12, "bold"), corner_radius=8,
                              fg_color=("#26415e", "#1e2a3a"),
                              hover_color=("#33526f", "#2b3b4f"),
                              text_color=ON_HEADER)
            b.pack(side="right", padx=(0, 8), pady=14)
            Tooltip(b, tip)
            return b

        self._theme_btn = util("🌙  Oscuro", self._toggle_theme,
                               "Alternar tema claro / oscuro", 112)
        util("📂  Outputs", lambda: self._open(os.path.join(_project_root(), "outputs")),
             "Abrir la carpeta de resultados generados")
        util("➕  Nuevo proyecto", self._new_project,
             "Crear una carpeta de proyecto en data/ y dejarla activa", 158)

    def _toggle_theme(self):
        dark = ctk.get_appearance_mode() == "Dark"
        ctk.set_appearance_mode("light" if dark else "dark")
        self._theme_btn.configure(text="🌙  Oscuro" if dark else "☀️  Claro")
        self._refresh_rows()

    # ------------------------------------------------------------------
    def _build_project_bar(self):
        bar = ctk.CTkFrame(self, fg_color=SURFACE_ALT, corner_radius=0, height=64)
        bar.grid(row=1, column=0, sticky="ew")
        bar.grid_propagate(False)

        ctk.CTkLabel(bar, text="📁", font=_f(18)).pack(side="left", padx=(22, 10))

        info = ctk.CTkFrame(bar, fg_color="transparent")
        info.pack(side="left", fill="both", expand=True, pady=10)

        self._project_label = ctk.CTkLabel(
            info, text="Ningún proyecto seleccionado", font=_f(14, "bold"),
            text_color=TEXT, anchor="w")
        self._project_label.pack(anchor="w")

        self._chips = ctk.CTkFrame(info, fg_color="transparent")
        self._chips.pack(anchor="w", pady=(3, 0))

        btn = ctk.CTkButton(bar, text="Cambiar proyecto  ▾",
                            command=self._select_project,
                            width=168, height=36, font=_f(12, "bold"),
                            corner_radius=8, fg_color=ACCENT, hover_color=ACCENT_HOV)
        btn.pack(side="right", padx=22)
        Tooltip(btn, "Elegir sobre qué carpeta de data/ trabajar   (Ctrl+O)")

    def _render_chips(self):
        for w in self._chips.winfo_children():
            w.destroy()
        if not self._project:
            ctk.CTkLabel(self._chips,
                         text="Elige un proyecto para ver el progreso del flujo",
                         font=_f(11), text_color=MUTED).pack(side="left")
            return
        for key, icon, label in PROJECT_CHIPS:
            has = key in self._files
            chip = ctk.CTkFrame(self._chips,
                                fg_color=ACCENT_SOFT if has else "transparent",
                                corner_radius=10, border_width=0 if has else 1,
                                border_color=BORDER)
            chip.pack(side="left", padx=(0, 6))
            ctk.CTkLabel(chip, text=f"{icon}  {label}" if has else f"○  {label}",
                         font=_f(10, "bold" if has else "normal"),
                         text_color=TEXT if has else MUTED
                         ).pack(padx=9, pady=3)

    # ------------------------------------------------------------------
    def _build_body(self):
        body = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        body.grid(row=2, column=0, sticky="nsew", padx=16, pady=14)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        self._build_sidebar(body)
        self._build_detail(body)

    # ------------------------------------------------------------------
    def _build_sidebar(self, parent):
        side = ctk.CTkScrollableFrame(parent, fg_color=SURFACE, corner_radius=12,
                                      border_width=1, border_color=BORDER, width=272)
        side.grid(row=0, column=0, sticky="nsw", padx=(0, 14))

        by_group: dict[str, list] = {}
        for a in ACTIONS:
            by_group.setdefault(a["group"], []).append(a)

        for gid, gtitle in GROUPS:
            items = by_group.get(gid, [])
            if not items:
                continue
            ctk.CTkLabel(side, text=gtitle.upper(), font=_f(10, "bold"),
                         text_color=ACCENT, anchor="w"
                         ).pack(anchor="w", padx=14, pady=(12, 3))
            for act in items:
                self._build_row(side, act)

        ctk.CTkLabel(side, text="", height=6).pack()

    def _build_row(self, parent, act: dict):
        """Fila clicable de la barra lateral: icono · etiqueta · estado."""
        row = ctk.CTkFrame(parent, fg_color="transparent", corner_radius=8, height=32)
        row.pack(fill="x", padx=8)
        row.pack_propagate(False)

        icon = ctk.CTkLabel(row, text=act["icon"], font=_f(14), width=26)
        icon.pack(side="left", padx=(8, 4))

        label = ctk.CTkLabel(row, text=act["label"], font=_f(12), text_color=TEXT,
                             anchor="w")
        label.pack(side="left", fill="x", expand=True)

        state = ctk.CTkLabel(row, text="○", font=_f(13, "bold"), text_color=MUTED,
                             width=22)
        state.pack(side="right", padx=(0, 8))

        self._rows[act["id"]] = {"row": row, "icon": icon,
                                 "label": label, "state": state}

        # Un único tooltip para toda la fila: entrar en un hijo genera <Leave>
        # en el padre, así que sin compartirlo el globo parpadearía.
        tip = Tooltip(row, act["help"])
        for w in (row, icon, label, state):
            w.bind("<Button-1>", lambda _e, i=act["id"]: self._select(i))
            w.bind("<Enter>", lambda _e, i=act["id"]: (self._hover(i, True),
                                                       tip._schedule()))
            w.bind("<Leave>", lambda _e, i=act["id"]: (self._hover(i, False),
                                                       tip._hide()))

    def _hover(self, action_id: str, entering: bool):
        if action_id == self._current_id:
            return
        self._rows[action_id]["row"].configure(
            fg_color=SURFACE_ALT if entering else "transparent")

    # ------------------------------------------------------------------
    def _build_detail(self, parent):
        panel = ctk.CTkFrame(parent, fg_color=SURFACE, corner_radius=12,
                             border_width=1, border_color=BORDER)
        panel.grid(row=0, column=1, sticky="nsew")
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(6, weight=1)

        pad = 26

        self._breadcrumb = ctk.CTkLabel(panel, text="", font=_f(11, "bold"),
                                        text_color=ACCENT, anchor="w")
        self._breadcrumb.grid(row=0, column=0, sticky="w", padx=pad, pady=(20, 2))

        self._title = ctk.CTkLabel(panel, text="", font=_f(24, "bold"),
                                   text_color=TEXT, anchor="w")
        self._title.grid(row=1, column=0, sticky="w", padx=pad, pady=(0, 6))

        self._help = ctk.CTkLabel(panel, text="", font=_f(12.5), text_color=MUTED,
                                  anchor="w", justify="left", wraplength=560)
        self._help.grid(row=2, column=0, sticky="ew", padx=pad, pady=(0, 14))

        # Campos de entrada del paso (solo los tienen las acciones de captura)
        self._inputs_holder = ctk.CTkFrame(panel, fg_color="transparent")
        self._inputs_holder.grid(row=3, column=0, sticky="ew", padx=pad)

        # Tarjeta de requisitos
        self._req_card = ctk.CTkFrame(panel, fg_color=SURFACE_ALT, corner_radius=10)
        self._req_card.grid(row=4, column=0, sticky="ew", padx=pad, pady=(0, 16))
        ctk.CTkLabel(self._req_card, text="REQUISITOS", font=_f(9, "bold"),
                     text_color=MUTED, anchor="w"
                     ).pack(anchor="w", padx=14, pady=(9, 2))
        self._req_body = ctk.CTkFrame(self._req_card, fg_color="transparent")
        self._req_body.pack(fill="x", padx=14, pady=(0, 10))

        # Acciones
        actions = ctk.CTkFrame(panel, fg_color="transparent")
        actions.grid(row=5, column=0, sticky="ew", padx=pad, pady=(0, 16))

        self._run_btn = ctk.CTkButton(actions, text="▶   Ejecutar",
                                      command=self._run_current,
                                      width=190, height=46, font=_f(14, "bold"),
                                      corner_radius=10, fg_color=ACCENT,
                                      hover_color=ACCENT_HOV)
        self._run_btn.pack(side="left")
        Tooltip(self._run_btn, "Lanzar este paso   (Ctrl+R)")

        self._stop_btn = ctk.CTkButton(actions, text="■   Detener",
                                       command=self._stop_proc,
                                       width=140, height=46, font=_f(13, "bold"),
                                       corner_radius=10, fg_color=DANGER_SOFT,
                                       hover_color=("#fca5a5", "#4c2626"),
                                       text_color=DANGER, state="disabled")
        self._stop_btn.pack(side="left", padx=10)
        Tooltip(self._stop_btn, "Terminar el proceso en curso y su árbol   (Esc)")

        self._timer = ctk.CTkLabel(actions, text="", font=_f(12, "bold"),
                                   text_color=ACCENT)
        self._timer.pack(side="left", padx=12)

        self._hint = ctk.CTkLabel(actions, text="", font=_f(11), text_color=WARN,
                                  anchor="w", justify="left", wraplength=320)
        self._hint.pack(side="left", padx=4)

        # Registro de actividad
        logbox = ctk.CTkFrame(panel, fg_color="transparent")
        logbox.grid(row=6, column=0, sticky="nsew", padx=pad, pady=(0, 20))
        logbox.grid_columnconfigure(0, weight=1)
        logbox.grid_rowconfigure(1, weight=1)

        head = ctk.CTkFrame(logbox, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        ctk.CTkLabel(head, text="ACTIVIDAD", font=_f(9, "bold"),
                     text_color=MUTED).pack(side="left")
        self._log_mode = ctk.CTkLabel(head, text="", font=_f(9), text_color=MUTED)
        self._log_mode.pack(side="left", padx=8)

        ctk.CTkButton(head, text="Limpiar", command=self._clear_log,
                      width=68, height=22, font=_f(10), corner_radius=6,
                      fg_color="transparent", border_width=1, border_color=BORDER,
                      text_color=MUTED, hover_color=SURFACE_ALT).pack(side="right")

        self._log = ctk.CTkTextbox(logbox, font=ctk.CTkFont(family="Consolas", size=11),
                                   fg_color=SURFACE_ALT, text_color=TEXT,
                                   corner_radius=8, border_width=0, wrap="word",
                                   activate_scrollbars=True)
        self._log.grid(row=1, column=0, sticky="nsew")
        self._log.configure(state="disabled")

    # ------------------------------------------------------------------
    def _build_status_bar(self):
        bar = ctk.CTkFrame(self, fg_color=SURFACE_ALT, corner_radius=0, height=34)
        bar.grid(row=3, column=0, sticky="ew")
        bar.grid_propagate(False)

        self._status_var = ctk.StringVar(
            value="Listo. Elige un proyecto y un paso del flujo.")
        ctk.CTkLabel(bar, textvariable=self._status_var, font=_f(11),
                     text_color=MUTED, anchor="w"
                     ).pack(side="left", padx=18, fill="x", expand=True)

        ctk.CTkButton(bar, text="Salir", command=self._on_close, width=76, height=24,
                      font=_f(11), corner_radius=6, fg_color="transparent",
                      border_width=1, border_color=BORDER, text_color=MUTED,
                      hover_color=DANGER_SOFT).pack(side="right", padx=14)

    def _bind_shortcuts(self):
        self.bind("<Control-o>", lambda _e: self._select_project())
        self.bind("<Control-r>", lambda _e: self._run_current())
        self.bind("<Escape>", lambda _e: self._stop_proc())

    # ==================================================================
    # Estado y refresco
    # ==================================================================

    def _action(self, action_id: str) -> dict:
        return next(a for a in ACTIONS if a["id"] == action_id)

    def _current(self) -> dict:
        return self._action(self._current_id)

    def _state_of(self, act: dict) -> str:
        """Estado del paso: running / blocked / done / ready."""
        if self._proc_action and self._proc_action["id"] == act["id"] and self._busy():
            return RUNNING
        if not self._project:
            return READY
        missing = [k for k in act["requires"] if k not in self._files]
        if missing:
            return BLOCKED
        if act["produces"] and act["produces"] in self._files:
            return DONE
        return READY

    def _select(self, action_id: str):
        self._current_id = action_id
        self._save_state()
        self._refresh_rows()
        self._refresh_detail()

    def _refresh_rows(self):
        for act in ACTIONS:
            r = self._rows[act["id"]]
            st = self._state_of(act)
            glyph, color = STATE_GLYPH[st]
            active = act["id"] == self._current_id
            r["row"].configure(fg_color=ACCENT_SOFT if active else "transparent")
            r["label"].configure(text_color=TEXT if active or st != BLOCKED else MUTED,
                                 font=_f(12, "bold" if active else "normal"))
            r["state"].configure(text=glyph, text_color=color)

    def _refresh_detail(self):
        act = self._current()
        group = dict(GROUPS)[act["group"]]
        self._breadcrumb.configure(text=f"{group}   ›   {act['label']}")
        self._title.configure(text=f"{act['icon']}   {act['label']}")
        self._help.configure(text=act["help"])
        self._render_inputs(act)
        self._render_requirements(act)
        self._log_mode.configure(
            text="este paso abre una consola aparte porque te pide datos por teclado"
            if act.get("console") else "la salida del script se muestra aquí en directo")
        self._refresh_buttons()

    # ------------------------------------------------------------------
    # Campos de entrada del paso
    # ------------------------------------------------------------------

    def _render_inputs(self, act: dict):
        """Dibuja los campos del paso. Los valores se conservan al navegar."""
        for w in self._inputs_holder.winfo_children():
            w.destroy()
        self._entries = {}

        specs = act.get("inputs") or []
        if not specs:
            # grid_remove y no solo pady=0: un CTkFrame vacío conserva su
            # altura por defecto y dejaba un hueco muerto en el panel.
            self._inputs_holder.grid_remove()
            return
        self._inputs_holder.grid()
        self._inputs_holder.grid_configure(pady=(0, 14))

        store = self._input_values.setdefault(act["id"], {})

        card = ctk.CTkFrame(self._inputs_holder, fg_color=SURFACE_ALT, corner_radius=10)
        card.pack(fill="x")
        ctk.CTkLabel(card, text="PARÁMETROS DE LA BÚSQUEDA", font=_f(9, "bold"),
                     text_color=MUTED, anchor="w"
                     ).pack(anchor="w", padx=14, pady=(10, 6))

        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="x", padx=14, pady=(0, 12))

        # Las fechas comparten fila; el resto ocupa el ancho completo.
        dates = [s for s in specs if s["kind"] == "date"]
        main = [s for s in specs if s["kind"] != "date"]

        def make_entry(parent, spec, width=None):
            box = ctk.CTkFrame(parent, fg_color="transparent")
            star = "  *" if spec["required"] else "   (opcional)"
            ctk.CTkLabel(box, text=spec["label"] + star, font=_f(11, "bold"),
                         text_color=TEXT, anchor="w").pack(anchor="w", pady=(0, 3))
            # Sin textvariable: CustomTkinter oculta el placeholder cuando el
            # campo está atado a uno, y el ejemplo de formato es justo lo que
            # hace falta ver en un campo vacío.
            entry = ctk.CTkEntry(
                box, placeholder_text=spec["placeholder"],
                height=38, font=_f(13), corner_radius=8,
                fg_color=SURFACE, border_color=BORDER, text_color=TEXT,
                **({"width": width} if width else {}))
            entry.pack(fill="x" if not width else "none", anchor="w")
            previo = store.get(spec["flag"], "")
            if previo:
                entry.insert(0, previo)
            if spec["hint"]:
                ctk.CTkLabel(box, text=spec["hint"], font=_f(10), text_color=MUTED,
                             anchor="w", justify="left", wraplength=520
                             ).pack(anchor="w", pady=(3, 0))
            entry.bind("<KeyRelease>",
                       lambda _e, f=spec["flag"], w=entry: self._on_input_change(
                           act["id"], f, w))
            entry.bind("<FocusOut>",
                       lambda _e, f=spec["flag"], w=entry: self._on_input_change(
                           act["id"], f, w))
            entry.bind("<Return>", lambda _e: self._run_current())
            self._entries[spec["flag"]] = entry
            return box

        for spec in main:
            make_entry(body, spec).pack(fill="x", pady=(0, 10))

        if dates:
            row = ctk.CTkFrame(body, fg_color="transparent")
            row.pack(fill="x")
            for spec in dates:
                make_entry(row, spec, width=150).pack(side="left", padx=(0, 14))
            ctk.CTkLabel(row, text="Déjalas vacías para no filtrar por fecha.",
                         font=_f(10), text_color=MUTED
                         ).pack(side="left", pady=(18, 0))

    def _on_input_change(self, action_id: str, flag: str, entry):
        self._input_values.setdefault(action_id, {})[flag] = entry.get()
        self._refresh_buttons()

    @staticmethod
    def _valid_date(text: str) -> bool:
        try:
            datetime.strptime(text.strip(), "%d-%m-%Y")
            return True
        except ValueError:
            return False

    def _collect_inputs(self, act: dict) -> dict[str, str]:
        """Valores vigentes de los campos del paso.

        Lee los widgets cuando son los del paso mostrado, en lugar de confiar
        en que el evento de tecleo haya sincronizado la caché: así validar y
        ejecutar usan siempre lo que el usuario tiene delante.
        """
        store = self._input_values.setdefault(act["id"], {})
        if act["id"] == self._current_id:
            for spec in act.get("inputs") or []:
                widget = self._entries.get(spec["flag"])
                if widget is not None:
                    store[spec["flag"]] = widget.get()
        return store

    def _check_inputs(self, act: dict) -> str | None:
        """Devuelve el motivo por el que no se puede ejecutar, o None si todo va bien."""
        store = self._collect_inputs(act)
        for spec in act.get("inputs") or []:
            value = store.get(spec["flag"], "").strip()
            if not value:
                if spec["required"]:
                    return f"Rellena «{spec['label']}» para poder ejecutar."
                continue
            if spec["kind"] == "date" and not self._valid_date(value):
                return f"«{spec['label']}» debe tener el formato dd-mm-aaaa."
        return None

    def _render_requirements(self, act: dict):
        for w in self._req_body.winfo_children():
            w.destroy()

        def line(text, color):
            ctk.CTkLabel(self._req_body, text=text, font=_f(11.5), text_color=color,
                         anchor="w", justify="left", wraplength=560
                         ).pack(anchor="w", pady=1)

        if not act["requires"]:
            line("✓  Este paso no depende de ningún archivo previo.", OK)
        elif not self._project:
            for key in act["requires"]:
                label, _ = FILE_LABELS[key]
                line(f"•  Necesita el {label}.", MUTED)
            line("ℹ  Sin proyecto activo el script abrirá su propio selector.", MUTED)
        else:
            for key in act["requires"]:
                label, origin = FILE_LABELS[key]
                path = self._files.get(key)
                if path:
                    line(f"✓  {label}:  {os.path.basename(path)}", OK)
                else:
                    line(f"✗  Falta el {label} — ejecuta antes «{origin}».", WARN)

    def _refresh_buttons(self):
        act = self._current()
        st = self._state_of(act)
        busy = self._busy()
        blocked = st == BLOCKED
        pending = None if busy else self._check_inputs(act)

        if busy:
            running_here = self._proc_action and self._proc_action["id"] == act["id"]
            text = "⏳   En ejecución…" if running_here else "⏳   Ocupado"
        elif st == DONE:
            text = "▶   Volver a ejecutar"
        else:
            text = "▶   Ejecutar"

        # Motivo visible junto al botón cuando falta o falla un campo.
        self._hint.configure(text=pending or "", text_color=WARN)

        disabled = busy or blocked or pending is not None
        self._run_btn.configure(
            text=text,
            state="disabled" if disabled else "normal",
            fg_color=DISABLED if disabled else ACCENT,
        )
        self._stop_btn.configure(state="normal" if busy else "disabled")

    # ==================================================================
    # Registro de actividad
    # ==================================================================

    MAX_LOG_LINES = 3000   # recorta el principio para no crecer sin límite

    def _log_line(self, text: str):
        self._append(f"{datetime.now():%H:%M:%S}  {text}")

    def _append(self, *lines: str):
        self._log.configure(state="normal")
        for line in lines:
            self._log.insert("end", line + "\n")
        total = int(self._log.index("end-1c").split(".")[0])
        if total > self.MAX_LOG_LINES:
            self._log.delete("1.0", f"{total - self.MAX_LOG_LINES}.0")
        self._log.see("end")
        self._log.configure(state="disabled")

    def _read_output(self, proc):
        """Hilo lector: vuelca la salida del script en la cola, línea a línea."""
        try:
            for line in proc.stdout:
                self._logq.put(line.rstrip("\r\n"))
        except Exception:
            pass
        finally:
            try:
                proc.stdout.close()
            except Exception:
                pass

    def _drain_log(self):
        """Pasa a la caja de texto lo que el hilo lector haya acumulado."""
        pendientes = []
        try:
            while True:
                pendientes.append(self._logq.get_nowait())
        except queue.Empty:
            pass
        if pendientes:
            self._append(*pendientes)

    def _clear_log(self):
        self._log.configure(state="normal")
        self._log.delete("1.0", "end")
        self._log.configure(state="disabled")

    def _status(self, msg: str):
        self._status_var.set(msg)

    # ==================================================================
    # Ejecución de procesos (sondeo, sin hilos)
    # ==================================================================

    def _busy(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def _run_current(self):
        act = self._current()
        if self._busy():
            self._status("Ya hay un proceso en marcha; espera a que termine.")
            return
        if self._state_of(act) == BLOCKED:
            self._status("Faltan archivos de entrada para este paso.")
            return
        problema = self._check_inputs(act)
        if problema:
            self._status(problema)
            return

        script = os.path.join(_project_root(), act["script"])
        if not os.path.isfile(script):
            self._log_line(f"❌ No se encuentra el script: {act['script']}")
            self._status("Script no encontrado.")
            return

        cmd = [sys.executable, script]
        arg_path = None
        arg_key = act.get("arg_key")
        if arg_key and self._project:
            path = self._files.get(arg_key)
            if path:
                cmd.append(path)
                arg_path = path

        # Parámetros recogidos en el panel. --no-prompt evita que el script
        # vuelva a preguntar por consola los campos que se hayan dejado vacíos.
        specs = act.get("inputs") or []
        if specs:
            store = self._collect_inputs(act)
            for spec in specs:
                value = store.get(spec["flag"], "").strip()
                if value:
                    cmd += [spec["flag"], value]
            cmd.append("--no-prompt")

        capture = not act.get("console")
        kwargs: dict = {}

        if capture:
            # -u y PYTHONUNBUFFERED: sin ellos Python bufferiza al escribir a
            # una tubería y el log llegaría a golpes al terminar, no en directo.
            cmd.insert(1, "-u")
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
            env["PYTHONIOENCODING"] = "utf-8"
            # stdin como tubería que se cierra acto seguido, NO DEVNULL: en
            # Windows el dispositivo NUL se reporta como terminal, así que
            # sys.stdin.isatty() daría True, los scripts entrarían en sus
            # input() de cortesía y morirían con EOFError y código 1 pese a
            # haber terminado bien. Con una tubería cerrada isatty() es False
            # y esas ramas se saltan, que es justo lo que buscamos.
            kwargs.update(
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                stdin=subprocess.PIPE, text=True,
                encoding="utf-8", errors="replace", bufsize=1, env=env,
            )
            if os.name == "nt":
                kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        elif os.name == "nt":
            # Consola propia: el script lee del teclado.
            kwargs["creationflags"] = subprocess.CREATE_NEW_CONSOLE

        try:
            self._proc = subprocess.Popen(cmd, cwd=_project_root(), **kwargs)
        except Exception as exc:
            self._log_line(f"❌ No se pudo lanzar «{act['label']}»: {exc}")
            self._status("Error al lanzar el proceso.")
            return

        if capture:
            if self._proc.stdin:
                self._proc.stdin.close()
            self._reader = threading.Thread(target=self._read_output,
                                            args=(self._proc,), daemon=True)
            self._reader.start()

        self._proc_action = act
        self._t0 = time.time()
        self._save_state()
        self._log_line(f"▶ {act['label']} — {os.path.basename(act['script'])}"
                       + (f"  ←  {os.path.basename(arg_path)}" if arg_path else ""))
        self._status(f"Ejecutando «{act['label']}» en una ventana de consola aparte.")
        self._refresh_rows()
        self._refresh_buttons()
        self._poll()

    def _poll(self):
        if self._proc is None:
            return
        self._drain_log()
        rc = self._proc.poll()
        if rc is None:
            elapsed = int(time.time() - self._t0)
            self._timer.configure(text=f"⏱  {elapsed // 60:02d}:{elapsed % 60:02d}")
            self._poll_job = self.after(200, self._poll)
            return
        self._on_finished(rc)

    def _on_finished(self, rc: int):
        # El lector puede llevar líneas en vuelo cuando el proceso ya ha salido.
        if self._reader is not None:
            self._reader.join(timeout=2)
            self._reader = None
        self._drain_log()

        act = self._proc_action
        elapsed = int(time.time() - self._t0)
        dur = f"{elapsed // 60:02d}:{elapsed % 60:02d}"
        self._proc = None
        self._proc_action = None
        self._poll_job = None
        self._timer.configure(text="")

        label = act["label"] if act else "proceso"
        if self._stopping:
            # El código de salida tras un taskkill no informa de nada útil.
            self._stopping = False
            self._log_line(f"⏹ {label} — detenido por ti tras {dur}")
            self._status(f"«{label}» detenido.")
        elif rc == 0:
            self._log_line(f"✅ {label} — completado en {dur}")
            self._status(f"«{label}» completado en {dur}.")
        else:
            self._log_line(f"❌ {label} — terminó con código {rc} tras {dur}")
            self._status(f"«{label}» terminó con errores (código {rc}). "
                         "Revisa la ventana de consola.")

        # Reescanear: el paso puede haber generado archivos nuevos.
        before = set(self._files)
        if self._project:
            self._files = scan_project_files(self._project)
            nuevos = set(self._files) - before
            if nuevos:
                nombres = ", ".join(FILE_LABELS[k][0] for k in nuevos if k in FILE_LABELS)
                self._log_line(f"   ↳ nuevo en el proyecto: {nombres}")
            self._render_chips()

        if act and act.get("opens_report") and rc == 0:
            self._open_report()

        self._refresh_rows()
        self._refresh_detail()

    def _stop_proc(self):
        if not self._busy():
            return
        self._stopping = True
        try:
            if os.name == "nt":
                # /T mata también los nietos (Chromium de Playwright).
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(self._proc.pid)],
                               capture_output=True)
            else:
                self._proc.terminate()
            self._status("Deteniendo el proceso…")
        except Exception as exc:
            self._stopping = False
            self._log_line(f"⚠ No se pudo detener el proceso: {exc}")

    def _open_report(self):
        """Localiza y abre el informe HTML recién generado."""
        videos = self._files.get("videos")
        if not videos:
            return
        base = os.path.splitext(os.path.basename(videos))[0]
        proyecto_id = base.split("_videos")[0]
        informe = os.path.join(_project_root(), "outputs", proyecto_id,
                               "informes", f"{base}_informe.html")
        if os.path.exists(informe):
            ok, msg = open_path(informe)
            self._log_line(("🌐 " if ok else "⚠ ") + msg)
        else:
            self._log_line("⚠ Informe generado pero no encontrado en la ruta esperada; "
                           "ábrelo desde Outputs.")

    def _open(self, path: str):
        ok, msg = open_path(path)
        self._status(msg)
        if not ok:
            self._log_line(f"⚠ {msg}")

    # ==================================================================
    # Proyecto activo
    # ==================================================================

    def _set_project(self, folder: str):
        self._project = folder
        self._files = scan_project_files(folder)
        self._project_label.configure(text=os.path.basename(folder))
        self._render_chips()
        self._save_state()
        self._log_line(f"📁 Proyecto activo: {os.path.basename(folder)} "
                       f"({len(self._files)} archivos reconocidos)")
        self._status(f"Proyecto activo: {os.path.basename(folder)}")
        self._refresh_rows()
        self._refresh_detail()

    # Caracteres que Windows no admite en un nombre de carpeta, y nombres
    # reservados por el sistema que fallarían al crearla.
    _INVALID_CHARS = '<>:"/\\|?*'
    _RESERVED = {"con", "prn", "aux", "nul",
                 *(f"com{i}" for i in range(1, 10)),
                 *(f"lpt{i}" for i in range(1, 10))}

    @classmethod
    def _safe_name(cls, raw: str) -> str:
        """Nombre de carpeta utilizable a partir de lo que escriba el usuario."""
        name = raw.strip()
        for ch in cls._INVALID_CHARS:
            name = name.replace(ch, "")
        name = "_".join(name.split())        # espacios → guiones bajos
        return name.strip("._")

    def _new_project(self):
        """Crea una carpeta de proyecto en data/ y la deja activa."""
        data_dir = os.path.join(_project_root(), "data")

        dlg = ctk.CTkToplevel(self)
        dlg.title("Nuevo proyecto")
        dlg.geometry("560x360")
        dlg.resizable(False, False)
        dlg.configure(fg_color=BG)
        dlg.transient(self)
        dlg.after(120, dlg.grab_set)

        ctk.CTkLabel(dlg, text="Crear un proyecto nuevo", font=_f(16, "bold"),
                     text_color=TEXT).pack(anchor="w", padx=24, pady=(22, 2))
        ctk.CTkLabel(dlg, text="Una carpeta dentro de data/ para agrupar los CSV "
                              "de una investigación.",
                     font=_f(11), text_color=MUTED, justify="left", wraplength=500
                     ).pack(anchor="w", padx=24, pady=(0, 14))

        ctk.CTkLabel(dlg, text="Nombre", font=_f(11, "bold"), text_color=TEXT
                     ).pack(anchor="w", padx=24, pady=(0, 3))
        entry = ctk.CTkEntry(dlg, placeholder_text="therians_2024", height=38,
                             font=_f(13), corner_radius=8, fg_color=SURFACE,
                             border_color=BORDER, text_color=TEXT)
        entry.pack(fill="x", padx=24)

        preview = ctk.CTkLabel(dlg, text="", font=_f(11), text_color=MUTED,
                               anchor="w", justify="left", wraplength=500)
        preview.pack(anchor="w", padx=24, pady=(6, 0))

        aviso = ctk.CTkFrame(dlg, fg_color=SURFACE_ALT, corner_radius=8)
        aviso.pack(fill="x", padx=24, pady=(14, 0))
        ctk.CTkLabel(aviso, text="Los pasos de captura crean su propia carpeta a partir "
                                 "de la cuenta o los términos que busques (por ejemplo "
                                 "user_vodafone_es). Esto sirve para organizar o para "
                                 "traer CSV de fuera.",
                     font=_f(10), text_color=MUTED, justify="left", wraplength=470
                     ).pack(padx=12, pady=9)

        # La fila de botones se crea antes que el botón para poder ser su padre:
        # empaquetarlo con in_= en un contenedor posterior lo dejaba sin pintar.
        row = ctk.CTkFrame(dlg, fg_color="transparent")
        row.pack(fill="x", padx=24, pady=(18, 20), side="bottom")

        crear_btn = ctk.CTkButton(row, text="Crear y activar", width=150, height=38,
                                  font=_f(12, "bold"), corner_radius=8,
                                  fg_color=ACCENT, hover_color=ACCENT_HOV)
        crear_btn.pack(side="right")

        # revisar() solo informa; nunca deshabilita el botón. Un botón apagado
        # sin explicación es un callejón sin salida si el aviso en vivo falla,
        # así que la validación de verdad ocurre al pulsar Crear.
        def revisar(*_):
            name = self._safe_name(entry.get())
            if not name:
                preview.configure(text="Escribe un nombre.", text_color=MUTED)
                return None
            if name.lower() in self._RESERVED:
                preview.configure(text=f"«{name}» es un nombre reservado por Windows.",
                                  text_color=WARN)
                return None
            if os.path.isdir(os.path.join(data_dir, name)):
                preview.configure(text=f"Ya existe data/{name}/ — elige otro nombre.",
                                  text_color=WARN)
                return None
            preview.configure(text=f"Se creará:  data/{name}/", text_color=OK)
            return name

        def crear():
            name = revisar()
            if not name:
                return
            folder = os.path.join(data_dir, name)
            try:
                os.makedirs(folder)
            except OSError as exc:
                preview.configure(text=f"No se pudo crear: {exc}", text_color=WARN)
                return
            dlg.destroy()
            self._log_line(f"➕ Proyecto creado: data/{name}/")
            self._set_project(folder)

        crear_btn.configure(command=crear)
        entry.bind("<KeyRelease>", revisar)
        entry.bind("<Return>", lambda _e: crear())

        ctk.CTkButton(row, text="Cancelar", command=dlg.destroy, width=110, height=38,
                      font=_f(12), corner_radius=8, fg_color="transparent",
                      border_width=1, border_color=BORDER, text_color=MUTED,
                      hover_color=SURFACE_ALT).pack(side="left")

        dlg.bind("<Escape>", lambda _e: dlg.destroy())
        revisar()
        dlg.after(220, entry.focus_set)

    def _select_project(self):
        data_dir = os.path.join(_project_root(), "data")
        try:
            proyectos = sorted(
                (d for d in os.listdir(data_dir)
                 if os.path.isdir(os.path.join(data_dir, d))),
                key=str.lower)
        except OSError:
            proyectos = []

        if not proyectos:
            self._pick_folder(data_dir)
            return

        dlg = ctk.CTkToplevel(self)
        dlg.title("Seleccionar proyecto")
        dlg.geometry("560x480")
        dlg.minsize(460, 380)
        dlg.configure(fg_color=BG)
        dlg.transient(self)
        # grab_set inmediato falla en Windows si la ventana aún no es visible.
        dlg.after(120, dlg.grab_set)

        ctk.CTkLabel(dlg, text="Elige el proyecto sobre el que trabajar",
                     font=_f(15, "bold"), text_color=TEXT
                     ).pack(anchor="w", padx=22, pady=(20, 2))
        ctk.CTkLabel(dlg, text="Los iconos indican qué pasos del flujo ya tienen datos.",
                     font=_f(11), text_color=MUTED
                     ).pack(anchor="w", padx=22, pady=(0, 10))

        search_var = ctk.StringVar()
        ctk.CTkEntry(dlg, textvariable=search_var, placeholder_text="Filtrar…",
                     height=34, font=_f(12), corner_radius=8,
                     fg_color=SURFACE, border_color=BORDER
                     ).pack(fill="x", padx=22, pady=(0, 8))

        scroll = ctk.CTkScrollableFrame(dlg, fg_color=SURFACE, corner_radius=10,
                                        border_width=1, border_color=BORDER)
        scroll.pack(fill="both", expand=True, padx=22)

        current = os.path.basename(self._project) if self._project else ""
        selected = ctk.StringVar(value=current if current in proyectos else proyectos[0])

        # El escaneo de cada carpeta se cachea: evita releer en cada filtrado.
        cache: dict[str, dict] = {}

        def render(_=None):
            for w in scroll.winfo_children():
                w.destroy()
            needle = search_var.get().strip().lower()
            shown = [p for p in proyectos if needle in p.lower()]
            if not shown:
                ctk.CTkLabel(scroll, text="Sin coincidencias", font=_f(11),
                             text_color=MUTED).pack(pady=16)
                return
            for p in shown:
                if p not in cache:
                    cache[p] = scan_project_files(os.path.join(data_dir, p))
                files = cache[p]
                marks = "  ".join(
                    icon if key in files else "○"
                    for key, icon, _lbl in PROJECT_CHIPS)
                ctk.CTkRadioButton(
                    scroll, text=f"  {marks}    {p}", variable=selected, value=p,
                    font=_f(12), text_color=TEXT, radiobutton_width=17,
                    radiobutton_height=17, border_width_unchecked=2,
                ).pack(anchor="w", pady=4, padx=12)

        search_var.trace_add("write", lambda *_: render())
        render()

        ctk.CTkLabel(dlg, text="📹 vídeos    💬 comentarios    🤖 sentimiento    "
                              "📅 edad de cuentas    ○ pendiente",
                     font=_f(9.5), text_color=MUTED).pack(pady=(8, 2))

        row = ctk.CTkFrame(dlg, fg_color="transparent")
        row.pack(fill="x", padx=22, pady=(4, 18))

        def confirm():
            name = selected.get()
            dlg.destroy()
            if name:
                self._set_project(os.path.join(data_dir, name))

        def manual():
            dlg.destroy()
            self._pick_folder(data_dir)

        ctk.CTkButton(row, text="Aceptar", command=confirm, width=120, height=36,
                      font=_f(12, "bold"), corner_radius=8,
                      fg_color=ACCENT, hover_color=ACCENT_HOV).pack(side="right")
        ctk.CTkButton(row, text="Otra carpeta…", command=manual, width=140, height=36,
                      font=_f(12), corner_radius=8, fg_color="transparent",
                      border_width=1, border_color=BORDER, text_color=TEXT,
                      hover_color=SURFACE_ALT).pack(side="right", padx=8)
        ctk.CTkButton(row, text="Cancelar", command=dlg.destroy, width=110, height=36,
                      font=_f(12), corner_radius=8, fg_color="transparent",
                      border_width=1, border_color=BORDER, text_color=MUTED,
                      hover_color=SURFACE_ALT).pack(side="left")

        dlg.bind("<Return>", lambda _e: confirm())
        dlg.bind("<Escape>", lambda _e: dlg.destroy())

    def _pick_folder(self, initial_dir: str):
        """Selector nativo de carpeta, colgado del root existente."""
        from tkinter import filedialog
        folder = filedialog.askdirectory(
            parent=self,
            title="Selecciona la carpeta del proyecto",
            initialdir=initial_dir if os.path.isdir(initial_dir) else _project_root(),
        )
        if folder:
            self._set_project(folder)

    # ==================================================================
    # Persistencia ligera de la sesión
    # ==================================================================

    def _state_path(self) -> str:
        return os.path.join(_project_root(), "data", ".menu_state.json")

    def _restore_state(self):
        try:
            with open(self._state_path(), encoding="utf-8") as f:
                st = json.load(f)
        except Exception:
            return
        if any(a["id"] == st.get("action") for a in ACTIONS):
            self._current_id = st["action"]
        folder = st.get("project")
        if folder and os.path.isdir(folder):
            self._project = folder
            self._files = scan_project_files(folder)
        if isinstance(st.get("inputs"), dict):
            self._input_values = st["inputs"]

    def _save_state(self):
        try:
            os.makedirs(os.path.dirname(self._state_path()), exist_ok=True)
            with open(self._state_path(), "w", encoding="utf-8") as f:
                json.dump({"action": self._current_id, "project": self._project,
                           "inputs": self._input_values}, f)
        except Exception:
            pass

    # ==================================================================
    def _on_close(self):
        if self._busy():
            from tkinter import messagebox
            resp = messagebox.askyesnocancel(
                "Proceso en marcha",
                "Hay un proceso ejecutándose.\n\n"
                "Sí = terminarlo y salir\n"
                "No = salir dejándolo en segundo plano\n"
                "Cancelar = no salir",
                parent=self,
            )
            if resp is None:
                return
            if resp:
                self._stop_proc()
        if self._poll_job:
            try:
                self.after_cancel(self._poll_job)
            except Exception:
                pass
        self._save_state()
        self.destroy()


# ---------------------------------------------------------------------------

def main():
    MenuApp().mainloop()


if __name__ == "__main__":
    main()
