# Proyecto TikTok — Contexto para Claude

## Descripción
Herramienta de scraping y analítica de TikTok en `H:\TikTok`.
Stack: **Playwright, pandas, matplotlib, wordcloud, nltk/vader, networkx, mistralai, groq, pysentimiento**. Python. Windows 10.

## Estructura de carpetas
- `data_tiktok/` — Salida de CSVs y JSONs (symlink a Google Drive → `I:\Mi unidad\data_tiktok`)
- `gráficas/{project}/publicaciones/` — Gráficas de vídeos (`analitica_publicaciones.py`)
- `gráficas/{project}/comentarios/` — Gráficas de comentarios (`analitica_comentarios.py`)
- `gráficas/{project}/polaridad_ia/` — Gráficas de sentimiento IA (`analitica_comentarios.py` + `analizar_sentimiento.py`)
- `graficas_redes/` — Imágenes para redes sociales
- `assets/tiktok_logo.jpg` — Logo TikTok para watermark en gráficas
- `playwright_auth/` — Estado de sesión guardado (`tiktok.json`)
- `tiktok_profile/` — Perfil persistente de Chromium

## Scripts de scraping
| Script | Función |
|--------|---------|
| `1-guardar_sesion.py` | Guarda cookies/sesión de TikTok con Playwright |
| `1_tiktok_scraper_comentarios.py` | Extrae comentarios interceptando `/api/comment/list/` |
| `1_tiktok_scraper_hastag.py` | Busca videos por hashtag/palabra con filtro de fechas |
| `1_tiktok_scraper_user.py` | Extrae todos los videos de un perfil de usuario |

## Scripts de analítica
| Script | Función | Salida |
|--------|---------|--------|
| `analitica_publicaciones.py` | Nubes, evolución, temporal, heatmap de vídeos | `gráficas/{project}/publicaciones/` |
| `analitica_comentarios.py` | Nubes, comunidad, temporal, sentimiento, emojis | `comentarios/` y `polaridad_ia/` |
| `analizar_sentimiento.py` | Análisis multidimensional con IA (RoBERTa/Groq/Mistral) | CSV `_con_sentimiento_*.csv` |
| `analitica_redes.py` | KPIs y gráficas para redes sociales | `graficas_redes/` |
| `comparativa_usuarios.py` | Sentimiento comparativo entre múltiples cuentas | — |

### Tests de gráficas (sin re-ejecutar scraping ni API)
| Script | Qué regenera |
|--------|-------------|
| `_test_graficas_publicaciones.py` | Todas las gráficas de publicaciones |
| `_test_graficas_comentarios.py` | Todas las gráficas de comentarios |
| `_test_graficas_sentimiento.py` | Gráficas de polaridad IA |

## Scripts de grafos (Gephi)
- `crear_gexf.py` / `grafo_comentarios.py` → exportan GEXF para Gephi
- `data_tiktok/grafo_comentarios_repetidos.gexf` → comentarios repetidos ≥5 veces, nodos usuario→comentario, atributo `tipo`

## Script de informe HTML
**`generar_informe_html.py`** — Genera un informe HTML auto-contenido (offline, imágenes en base64).

### Diseño del informe
- **Paleta TikTok**: fondo `#010101`, rojo `#fe2c55`, cian `#25f4ee`
- **Título**: el hashtag o término analizado — se pregunta al inicio con `simpledialog`
- **Sin handle @username** en el header (fue eliminado)
- **@barripdmx** posicionado a la derecha del bloque header (position: absolute, right: 28px)
- **Fecha en español**: usa diccionario `MESES_ES` para evitar dependencia de locale del sistema
- **Secciones**: KPIs (8 tarjetas), Top 5 videos por vistas, Análisis de Contenido, Rendimiento Temporal, Patrones de Publicación
- **Imágenes detectadas automáticamente** desde `gráficas/{project}/publicaciones/`

### Imágenes que usa (generadas por analitica_publicaciones.py)
```
{file_id}_nube_palabras.png
{file_id}_nube_hashtags.png
{file_id}_nube_emoticonos.png
{file_id}_evolucion_vistas.png
{file_id}_timeline_publicaciones.png
{file_id}_publicaciones_por_mes.png
{file_id}_publicaciones_por_dia_semana.png
{file_id}_publicaciones_por_hora.png
{file_id}_heatmap_actividad.png
```

## Diseño de gráficas — estilo periodístico
Todos los scripts comparten el mismo estilo visual:
- Fondo blanco, sin spines top/right, grid `#EBEBEB`, `figsize=(16,9)`, `dpi=100`
- Paleta: `#A93226` (positivo/principal), `#4A4A4A` (negativo/secundario), `#95a5a6` (neutro)
- Títulos en **minúsculas** identificando la cuenta: `"evolución de vistas de @usuario"`
- Estadística destacada como `ax.text` con `_STAT_BOX` dentro del gráfico (no en el título)
- Watermark TikTok: `_add_watermark(ax)` — `assets/tiktok_logo.jpg`, zoom=0.05, alpha=0.2, esquina inferior derecha
- Helpers compartidos en los tres scripts: `_get_account()`, `_STAT_BOX`, `_add_watermark()`, `_apply_estilo_periodistico()`

### Nubes de sentimiento — patrón GridSpec obligatorio
Las nubes con banda de título de color DEBEN usar `GridSpec(3, 2, height_ratios=[0.06, 0.88, 0.06])`.
**Nunca** usar `ax.add_patch(Rectangle)` ni `ax.text` dentro del eje del wordcloud — se solapa con la imagen.

## Sentimiento IA (análisis multidimensional)
- Pipeline unificado: `analizar_sentimiento.py` (RoBERTa local / Groq / Mistral). **Mistral** es el proveedor principal.
- Checkpoint: `{csv}_{proveedor}_checkpoint.json` — dict `{clave_estable: {sentiment, bias, archetype, intent, pain_point, sarcasm, noise}}`
- Clave estable = `comment_id` si existe, si no hash MD5 del texto (no posición)
- Taxonomía cerrada (enums + ruido/homónimos) en `config/taxonomia_ia.py`
- Contexto del vídeo (copy/hashtags) se inyecta por `video_id` para desambiguar ironía y sesgo

## Flujo de trabajo típico
1. `1-guardar_sesion.py` → guardar sesión
2. `1_tiktok_scraper_user.py` o `1_tiktok_scraper_hastag.py` → CSV de vídeos
3. `1_tiktok_scraper_comentarios.py` → CSV de comentarios (opcional)
4. `analitica_publicaciones.py` → gráficas de vídeos
5. `analizar_sentimiento.py` → sentimiento IA multidimensional con Mistral (puede tardar horas)
6. `analitica_comentarios.py` → gráficas de comentarios (requiere checkpoint de sentimiento)
7. `generar_informe_html.py` → informe HTML entregable

## Próximo desarrollo — scraper de fecha de creación de cuentas
**Objetivo**: obtener `create_time` de cada usuario comentarista para detectar cuentas coordinadas/bots.

**Escala (@sanchezcastejon)**:
- 109.451 usuarios únicos totales
- Target: **5.873 usuarios con ≥5 comentarios** (~4-5h de scraping)
- Prioritarios: **37 usuarios con ≥50 comentarios** (~2 min)

**Enfoque técnico**:
- Playwright intercepta `/api/user/detail/` al visitar `https://www.tiktok.com/@{handle}`
- Mismo patrón checkpoint JSON que el scraper de comentarios
- Delays 2-3s por perfil

**Pendiente**: prueba de concepto con 5 perfiles para confirmar que `create_time` existe en la respuesta antes de construir el scraper completo.

## Preferencias del usuario
- Autor/crédito: **@barripdmx**
- Idioma: español
- Números con punto como separador de miles (1.234.567)
- Meses en español forzado (no depender de locale Windows)
