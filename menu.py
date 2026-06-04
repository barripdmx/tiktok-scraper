# -*- coding: utf-8 -*-
"""
Menú principal — CustomTkinter, modo claro, layout apaisado.
Configuración ocupa todo el ancho; barra de proyecto activo; debajo 4 columnas.
"""

import os
import sys
import threading
import subprocess
import customtkinter as ctk

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
        self.minsize(800, 640)
        self.configure(fg_color=self.BG)
        self.resizable(True, True)

        # Estado del proyecto activo
        self._active_project: str | None = None      # ruta a data/{proyecto}/
        self._project_files: dict[str, str] = {}     # clave → ruta absoluta

        self._build_ui()

    # ------------------------------------------------------------------
    def _build_ui(self):
        self._build_header()
        self._build_config_row()
        self._build_project_bar()
        self._build_grid()
        self._build_footer()

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

        ctk.CTkLabel(
            hdr,
            text="Scraping · Análisis · Visualización",
            font=ctk.CTkFont(size=12),
            text_color="#93c5fd",
        ).pack(side="right", padx=24)

    # ------------------------------------------------------------------
    def _build_config_row(self):
        row = ctk.CTkFrame(self, fg_color=self.BG)
        row.pack(fill="x", padx=16, pady=(14, 4))

        self._wide_card(
            row,
            emoji="🔑",
            num="0",
            title="Configuración — Iniciar sesión y guardar cookies",
            subtitle="Haz esto primero para evitar bloqueos de TikTok",
            cmd=lambda: run_script("src/scrapers/1-guardar_sesion.py",
                                   status_cb=self._status),
            accent=True,
        )

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
    def _build_grid(self):
        grid = ctk.CTkFrame(self, fg_color=self.BG)
        grid.pack(fill="both", expand=True, padx=16, pady=(0, 4))

        for col in range(4):
            grid.columnconfigure(col, weight=1, uniform="col")
        grid.rowconfigure(0, weight=1)

        # ---- Fase 1 ----
        col1 = self._column(grid, "📥  Fase 1 — Captura de datos", 0)
        self._card(col1, "1", "👤", "Scraper de Usuario",
                   "Perfil @user",
                   lambda: run_script("src/scrapers/1_tiktok_scraper_user.py",
                                      status_cb=self._status))
        self._card(col1, "2", "#️⃣", "Scraper de Hashtag",
                   "Por palabra / hashtag",
                   lambda: run_script("src/scrapers/2_tiktok_scraper_hastag_api.py",
                                      status_cb=self._status))
        self._card(col1, "3", "💬", "Scraper Comentarios",
                   "Miles de comentarios (Pro)",
                   lambda: run_script("src/scrapers/2_tiktok_scraper_comentarios_api.py",
                                      status_cb=self._status))
        self._card(col1, "4", "📅", "Edad de Cuentas",
                   "Antigüedad de comentaristas",
                   lambda: self._run_for_project(
                       "src/utils/enriquecer_csv_fechas_creacion.py", "comments"))

        # ---- Fase 2 ----
        col2 = self._column(grid, "📊  Fase 2 — Análisis", 1)
        self._card(col2, "5", "📈", "Analítica Publicaciones",
                   "Vistas y likes",
                   lambda: self._run_for_project(
                       "src/analysis/analitica_publicaciones.py", "videos"))
        self._card(col2, "6", "🗣️", "Analítica Comentarios",
                   "Nubes de palabras",
                   lambda: self._run_for_project(
                       "src/analysis/analitica_comentarios.py", "comments"))
        self._card(col2, "7", "🤖", "Sentimiento con IA (Comentarios)",
                   "RoBERTa · Groq · Mistral",
                   lambda: self._run_for_project(
                       "src/analysis/analizar_sentimiento.py", "comments"))
        self._card(col2, "8", "🧠", "Gráficas Multidimensionales de Comentarios",
                   "Sesgo · Arquetipo · Intención · Pain points",
                   lambda: self._run_for_project(
                       "src/visualization/grafica_multidimensional.py", "sentiment"))
        self._card(col2, "9", "🕵️", "Patrones de Cuentas / Bots",
                   "Antigüedad · actividad · perfiles vacíos",
                   lambda: self._run_for_project(
                       "src/visualization/graficas_patrones_cuentas.py", "enriched"))

        # ---- Fase 3 ----
        col3 = self._column(grid, "🌐  Fase 3 — Visualización", 2)
        self._card(col3, "10", "📄", "Informe HTML",
                   "Genera + abre informe del proyecto",
                   lambda: generar_informe(
                       status_cb=self._status,
                       csv_videos_preset=self._resolve("videos")))
        self._card(col3, "11", "🕸️", "Grafo de Redes",
                   "GEXF para Gephi",
                   lambda: self._run_for_project(
                       "src/visualization/crear_gexf.py", "comments"))

        # ---- Otros ----
        col4 = self._column(grid, "📁  Otros", 3)
        self._card(col4, "12", "📂", "Carpeta Outputs",
                   "Ver resultados generados",
                   lambda: abrir_carpeta(os.path.join(_project_root(), "outputs"),
                                         status_cb=self._status))
        self._card(col4, "13", "🗂️", "Carpeta Proyecto",
                   "Raíz del proyecto",
                   lambda: abrir_carpeta(_project_root(), status_cb=self._status))

    # ------------------------------------------------------------------
    def _build_footer(self):
        foot = ctk.CTkFrame(self, fg_color=self.BG)
        foot.pack(fill="x", padx=16, pady=(4, 12))

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
        """Clasifica los CSV de un proyecto por tipo."""
        result = {}
        try:
            for f in sorted(os.listdir(folder)):
                if not f.endswith(".csv"):
                    continue
                p  = os.path.join(folder, f)
                nl = f.lower()
                if "enriquecido_fechas_creacion" in nl:
                    result["enriched"] = p
                elif "con_sentimiento" in nl:
                    result["sentiment"] = p
                elif "comentarios_api" in nl:
                    result["comments"] = p
                elif "videos_api" in nl:
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

    def _column(self, parent, title: str, col_idx: int) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(parent, fg_color=self.BG, corner_radius=0)
        frame.grid(row=0, column=col_idx, sticky="nsew",
                   padx=(0 if col_idx == 0 else 6, 0))

        hdr = ctk.CTkFrame(frame, fg_color=self.SECTION_BG, corner_radius=8, height=34)
        hdr.pack(fill="x", pady=(0, 6))
        hdr.pack_propagate(False)
        ctk.CTkLabel(
            hdr, text=title,
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=self.SECTION_TXT, anchor="w",
        ).pack(padx=10, pady=0, fill="both", expand=True)

        return frame

    def _bind_card(self, widget, cmd, outer):
        widget.bind("<Button-1>", lambda _e, c=cmd: c())
        widget.bind("<Enter>",    lambda _e, f=outer: f.configure(fg_color=self.CARD_HOVER))
        widget.bind("<Leave>",    lambda _e, f=outer: f.configure(fg_color=self.CARD_BG))
        for child in widget.winfo_children():
            self._bind_card(child, cmd, outer)

    def _card(self, parent, num: str, emoji: str, title: str,
              subtitle: str, cmd):
        outer = ctk.CTkFrame(parent, fg_color=self.CARD_BG, corner_radius=8,
                             border_width=1, border_color=self.CARD_BORDER)
        outer.pack(fill="x", pady=3)

        ctk.CTkLabel(
            outer, text=emoji,
            font=ctk.CTkFont(size=18), width=32,
        ).pack(side="left", padx=(10, 4), pady=10)

        txt = ctk.CTkFrame(outer, fg_color="transparent")
        txt.pack(side="left", fill="x", expand=True, pady=8)

        ctk.CTkLabel(
            txt,
            text=f"{num}. {title}",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=self.TEXT, anchor="w",
            justify="left", wraplength=150,
        ).pack(anchor="w", fill="x")

        ctk.CTkLabel(
            txt, text=subtitle,
            font=ctk.CTkFont(size=10),
            text_color=self.SUBTITLE, anchor="w",
            justify="left", wraplength=150,
        ).pack(anchor="w", fill="x")

        ctk.CTkLabel(
            outer, text="›",
            font=ctk.CTkFont(size=16),
            text_color=self.SUBTITLE, width=20,
        ).pack(side="right", padx=8)

        self._bind_card(outer, cmd, outer)

    def _wide_card(self, parent, emoji: str, num: str, title: str,
                   subtitle: str, cmd, accent: bool = False):
        bg     = "#1e3a5f" if accent else self.CARD_BG
        bg_hov = "#2563eb" if accent else self.CARD_HOVER
        fg     = "#ffffff" if accent else self.TEXT
        fg_sub = "#93c5fd" if accent else self.SUBTITLE

        outer = ctk.CTkFrame(parent, fg_color=bg, corner_radius=10,
                             border_width=0, height=62)
        outer.pack(fill="x")
        outer.pack_propagate(False)

        ctk.CTkLabel(
            outer, text=emoji,
            font=ctk.CTkFont(size=24), width=40,
        ).pack(side="left", padx=(16, 8))

        txt = ctk.CTkFrame(outer, fg_color="transparent")
        txt.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(
            txt, text=f"{num}. {title}",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=fg, anchor="w",
        ).pack(anchor="w")

        ctk.CTkLabel(
            txt, text=subtitle,
            font=ctk.CTkFont(size=11),
            text_color=fg_sub, anchor="w",
        ).pack(anchor="w")

        ctk.CTkLabel(
            outer, text="›",
            font=ctk.CTkFont(size=20),
            text_color=fg_sub, width=28,
        ).pack(side="right", padx=16)

        def _bind_wide(widget):
            widget.bind("<Button-1>", lambda _e, c=cmd: c())
            widget.bind("<Enter>",    lambda _e, f=outer, h=bg_hov: f.configure(fg_color=h))
            widget.bind("<Leave>",    lambda _e, f=outer, b=bg:     f.configure(fg_color=b))
            for child in widget.winfo_children():
                _bind_wide(child)
        _bind_wide(outer)

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
