# TikTok Scraper y Analizador

Herramienta completa para scraping, análisis de sentimientos y visualización de datos de TikTok. Utiliza Playwright para extracción, Gemini API para análisis de sentimientos, y genera reportes HTML interactivos.

## Estructura del Proyecto

```
tiktok-scraper/
├── src/                          # Código principal organizado
│   ├── scrapers/                 # Scripts de extracción de datos
│   │   ├── 1-guardar_sesion.py
│   │   ├── 1_tiktok_scraper_user.py
│   │   ├── 1_tiktok_scraper_hastag.py
│   │   └── ...
│   ├── analysis/                 # Análisis de datos y sentimientos
│   │   ├── analitica_publicaciones.py
│   │   ├── analitica_comentarios.py
│   │   ├── analizar_sentimiento_gemini.py
│   │   └── ...
│   ├── visualization/            # Generación de gráficos e informes
│   │   ├── generar_informe_html.py
│   │   ├── crear_gexf.py
│   │   └── ...
│   └── utils/                    # Funciones utilitarias
│
├── scripts/                      # Scripts auxiliares y ejemplos
├── docs/                         # Documentación (Guides, GEMINI.md, etc.)
├── config/                       # Configuración (.env no versionado)
├── data/                         # Datos temporales (no versionado)
├── outputs/                      # Resultados y gráficas (no versionado)
├── assets/                       # Recursos (logos, etc.)
│
├── README.md                     # Este archivo
├── requirements.txt              # Dependencias Python
└── .gitignore                    # Archivos ignorados

## Configuración

1.  **Clonar el repositorio:**
    ```bash
    git clone <repository_url>
    cd TikTok
    ```

2.  **Instalar dependencias:**
    Asegúrate de tener Python 3.x instalado. Luego, instala las librerías necesarias:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Instalar el navegador de Playwright:**
    Los scripts usan `playwright` con Chromium. Instálalo con el siguiente comando:
    ```bash
    playwright install chromium
    ```

4.  **Iniciar Sesión en TikTok:**
    Para que los scrapers funcionen correctamente, necesitas una sesión de TikTok válida. Ejecuta el siguiente script, que abrirá una ventana del navegador:
    ```bash
    python 1-guardar_sesion.py
    ```
    Inicia sesión manualmente en TikTok. Una vez que hayas iniciado sesión y veas tu feed, presiona `Enter` en la terminal. Tu estado de sesión se guardará en `playwright_auth/tiktok.json`, permitiendo que los otros scripts la reutilicen.

## Descripción de los Scripts

### Scripts de Scraping

-   **`1-guardar_sesion.py`**:
    Abre un navegador para que inicies sesión manualmente en TikTok y guarda las cookies y el estado de la sesión. **Este es el primer script que debes ejecutar.**

-   **`1_tiktok_scraper_comentarios.py`**:
    Extrae comentarios de una lista de videos de TikTok proporcionada en un archivo CSV. Es robusto y maneja errores, reintentos y guardado incremental.

-   **`1_tiktok_scraper_hastag.py`**:
    Busca y extrae videos basados en un hashtag específico, con la opción de filtrar por un rango de fechas. Guarda los metadatos de los videos encontrados.

-   **`1_tiktok_scraper_user.py`**:
    Extrae todos los videos de un perfil de usuario de TikTok. Permite filtrar los videos por fecha.

### Scripts de Análisis

-   **`analitica_comentarios.py`**:
    Analiza un CSV de comentarios. Genera nubes de palabras y emojis, identifica a los comentaristas más activos, analiza la actividad a lo largo del tiempo y realiza un análisis de sentimiento. Guarda las gráficas en la carpeta `gráficas/`.

-   **`analitica_publicaciones.py`**:
    Analiza un CSV de publicaciones de videos. Crea nubes de palabras y hashtags, reportes de los videos con mejor rendimiento y gráficas de análisis temporal. Guarda los resultados en `gráficas/`.

-   **`analitica_redes.py`**:
    Genera un conjunto de gráficos y resúmenes pensados para redes sociales a partir de un CSV de videos. Incluye KPIs, evolución de vistas, heatmaps de actividad, tops de videos, hashtags y más. Los resultados se guardan en `graficas_redes/`.

-   **`comparativa_usuarios.py`**:
    Realiza un análisis de sentimiento comparativo de usuarios a través de múltiples cuentas de TikTok. Requiere varios archivos CSV de comentarios y visualiza qué usuarios son consistentemente positivos o negativos hacia ciertas cuentas.

### Scripts para Grafos (Gephi)

-   **`crear_gexf.py`**:
    Crea un archivo de red en formato GEXF a partir de archivos CSV de comentarios. El grafo representa las interacciones entre los autores de los comentarios y los autores de los videos, ideal para visualizar en [Gephi](https://gephi.org/).

-   **`grafo_comentarios.py`**:
    Genera otro tipo de archivo GEXF. Este script modela la relación donde un nodo es el autor del video y otro es el usuario que comenta, con una arista dirigida que representa el comentario. El peso de la arista indica la cantidad de comentarios.

## Uso Rápido

### 1. Instalar dependencias
```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. Guardar sesión de TikTok
```bash
python src/scrapers/1-guardar_sesion.py
```
Inicia sesión manualmente en TikTok. Se guardará en `config/` para reutilizar.

### 3. Scrapear datos
```bash
# Por usuario
python src/scrapers/1_tiktok_scraper_user.py

# Por hashtag
python src/scrapers/1_tiktok_scraper_hastag.py

# Comentarios
python src/scrapers/1_tiktok_scraper_comentarios.py
```

### 4. Análisis y visualización
```bash
# Publicaciones
python src/analysis/analitica_publicaciones.py

# Sentimientos con Gemini
python src/analysis/analizar_sentimiento_gemini.py

# Generar informe HTML
python src/visualization/generar_informe_html.py
```

## Documentación Completa

Ver `docs/` para guías detalladas:
- `QUICK_START.md` — Tutorial de inicio rápido
- `GEMINI.md` — Configuración de API Gemini
- `SCRAPER_USAGE.md` — Detalles de cada scraper
