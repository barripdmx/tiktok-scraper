# Proyecto TikTok — Contexto para Claude

## Descripción
Toolkit de scraping y analítica OSINT de TikTok en `H:\1-TikTok`. Python 3, Windows 10.
Stack: **Playwright, pandas, matplotlib, wordcloud, networkx, groq, pysentimiento, CustomTkinter**.
El punto de entrada del usuario es `menu.py` (barra lateral por fases: captura → análisis → investigación → resultados).

## Estructura de carpetas
Todo resultado de un proyecto vive bajo `data/{proyecto}/` (nombre derivado de los términos/cuenta por el scraper):
```
data/{proyecto}/
  *.csv, *.json                      ← vídeos, comentarios, sentimiento, enriquecido
  Grafo/                             ← .gexf / .gephi
  informes/                          ← informe HTML
  graficas_videos/publicaciones/
  graficas_comentarios/              ← nubes, + graficas_multidimensionales/, graficas_patrones_cuentas/, polaridad_ia/
```
- **`config/rutas.py` es la única fuente de rutas** (`derivar_proyecto`, `dir_informes`, `dir_publicaciones`, `dir_grafo`…). No escribir rutas a mano.
- `outputs/` es solo legacy: no se usa en el flujo actual.
- `secrets/` (cookies/sesión de TikTok) y `config/.env` (claves API): nunca leer, imprimir ni versionar.
- `drivers/` perfiles persistentes de Chromium (Playwright). `assets/tiktok_logo.jpg` watermark de gráficas.

## Scripts
| Carpeta | Contenido |
|---|---|
| `src/scrapers/` | `1-guardar_sesion`, `1_tiktok_scraper_user`, `2_tiktok_scraper_hastag_api`, `2_tiktok_scraper_comentarios_api` (los usados por el menú); el resto son versiones antiguas |
| `src/analysis/` | `analitica_publicaciones`, `analitica_comentarios` (nubes; NO calcula sentimiento), `analizar_sentimiento` (IA) |
| `src/utils/` | `enriquecer_csv_fechas_creacion` (edad de cuentas), `tiktok_utils` |
| `src/visualization/` | `generar_informe_html`, `grafica_multidimensional`, `graficas_patrones_cuentas`, `crear_gexf` |
| `scripts/migrar_estructura.py` | reorganiza data/ y outputs/ (dry-run por defecto, `--aplicar`) |

Tests: `pytest tests/` (deben pasar todos antes de subir).

## Convenciones y trampas conocidas
- **Hashtag/búsqueda**: los términos se separan **solo por coma**; `save_results` fusiona por `video_id` (una recaptura nunca pierde vídeos). Comentarios: `append_csv` + checkpoint por `video_id`.
- **Fechas**: el CSV de comentarios usa ISO `%Y-%m-%d %H:%M:%S`; el de vídeos `%d-%m-%Y %H:%M:%S`. Parsear cada uno con su `format=` explícito (un `dayfirst=True` global corrompe datos).
- **`input()` / diálogos Tk**: siempre bajo `if sys.stdin.isatty()` (el menú lanza los scripts en segundo plano). Al lanzar scripts desde la herramienta Bash, redirigir stdin desde un fichero vacío real (no `/dev/null` ni `0<&-`).
- **Procesos en Windows**: matar con `taskkill /F /T /PID` desde PowerShell (Git Bash corrompe `/F` y `/T`).
- **CSV**: leer con `encoding="utf-8-sig"`.
- **Sentimiento IA**: único proveedor externo = **Groq** (`openai/gpt-oss-120b`, `reasoning_effort="low"`); local = RoBERTa español (no sirve para árabe). Varias claves: `GROQ_API_KEYS=a,b,c` (rotación). Checkpoint `{csv}_{proveedor}_checkpoint.json` con clave `comment_id`. Taxonomía en `config/taxonomia_ia.py`.
- Las gráficas de sentimiento de `analitica_comentarios.py` reutilizan el CSV `_con_sentimiento_*.csv`; si no existe, se omiten.

## Diseño de gráficas — estilo periodístico
- Fondo blanco, sin spines top/right, grid `#EBEBEB`, `figsize=(16,9)`, `dpi=100`
- Paleta en `config/viz_style.py`; sentimiento: positivo verde, neutro gris, negativo rojo
- Títulos en **minúsculas** identificando la cuenta; estadística destacada con `ax.text` + `_STAT_BOX`
- Watermark TikTok con `_add_watermark(ax)` (zoom=0.05, alpha=0.2, esquina inferior derecha)
- Nubes con banda de título: `GridSpec(3, 2, height_ratios=[0.06, 0.88, 0.06])`; nunca `add_patch`/`ax.text` dentro del eje del wordcloud
- Informe HTML: autocontenido (imágenes base64), paleta TikTok (`#010101`, `#fe2c55`, `#25f4ee`), fecha en español vía `MESES_ES`

## Preferencias del usuario
- Autor/crédito: **@barripdmx**
- Idioma: español
- Números con punto como separador de miles (1.234.567)
- Meses en español forzado (no depender del locale de Windows)
- Al subir a GitHub: commits temáticos con mensaje explicando qué cambió y por qué
