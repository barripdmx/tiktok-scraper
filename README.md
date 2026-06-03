# 🎵 TikTok OSINT & Analytics Toolkit

Herramienta completa para extraer, analizar y visualizar datos de TikTok: vídeos, comentarios, hashtags, sentimiento con IA y generación de informes HTML periodísticos.

---

## 📋 Índice

1. [Qué hace esta herramienta](#-qué-hace-esta-herramienta)
2. [Cuentas que necesitas crear](#-cuentas-que-necesitas-crear)
3. [APIs que necesitas configurar](#-apis-que-necesitas-configurar)
4. [Instalación paso a paso](#-instalación-paso-a-paso)
5. [Configurar las claves API](#-configurar-las-claves-api)
6. [Primera ejecución](#-primera-ejecución)
7. [Estructura del proyecto](#-estructura-del-proyecto)

---

## 🔍 Qué hace esta herramienta

| Fase | Qué hace |
|---|---|
| **Scraping** | Extrae todos los vídeos de un perfil o hashtag, con sus métricas (vistas, likes, comentarios, fecha) |
| **Análisis** | Genera +15 gráficas de rendimiento, nubes de palabras, heatmaps de actividad, curvas Pareto |
| **Sentimiento IA** | Clasifica comentarios como positivo/negativo/neutro usando 3 modelos de IA en pipeline |
| **Informe HTML** | Genera un informe periodístico autocontenido (sin servidor web) con todas las gráficas embebidas |
| **Menú visual** | Interfaz gráfica para lanzar todo sin tocar la terminal |

---

## 👤 Cuentas que necesitas crear

Necesitas cuenta en **4 plataformas**. Todas tienen plan gratuito suficiente para empezar.

### 1. TikTok
> Para poder hacer scraping necesitas una cuenta activa de TikTok con la que iniciar sesión.

- **Crear cuenta:** https://www.tiktok.com/signup
- Puede ser una cuenta nueva creada solo para esto (no uses tu cuenta personal principal)
- Solo se usa una vez al inicio para guardar la sesión

---

### 2. Groq
> Proporciona el modelo `llama-3.3-70b-versatile` (muy rápido, gratuito). Plan gratuito: 14.400 peticiones/día.

- **Crear cuenta:** https://console.groq.com
  - Pulsa **"Sign Up"** — puedes registrarte con Google
- **Obtener API Key:** https://console.groq.com/keys
  - Pulsa **"Create API Key"**
  - Ponle un nombre (ej: `tiktok-scraper`)
  - Copia la clave (empieza por `gsk_...`)

---

### 3. Mistral AI
> Proporciona el modelo `open-mistral-nemo`. Plan gratuito: 1.000 millones de tokens/mes (≈ 3.000 análisis).

- **Crear cuenta:** https://console.mistral.ai
  - Pulsa **"Sign up"** — puedes registrarte con Google o GitHub
- **Obtener API Key:** https://console.mistral.ai/api-keys
  - Pulsa **"Create new key"**
  - Copia la clave (empieza por `...`)
  - ⚠️ Solo se muestra **una vez** — cópiala antes de cerrar

---

## 🔑 APIs que necesitas configurar

Resumen de las 2 claves que necesitas:

| API | Para qué sirve | Límite gratuito | URL para obtenerla |
|---|---|---|---|
| **MISTRAL_API_KEY** | Análisis de sentimiento (principal) | 1B tokens/mes | https://console.mistral.ai/api-keys |
| **GROQ_API_KEY** | Análisis de sentimiento (rápido) | 14.400 req/día | https://console.groq.com/keys |

> **¿Para qué sirven 2 APIs de sentimiento?** El sistema puede usar RoBERTa (local, sin internet) o un proveedor LLM. Para el análisis multidimensional se usa **Mistral** (principal); Groq queda como alternativa rápida. Si una falla o alcanza su límite, puedes cambiar a la otra.

---

## 💻 Instalación paso a paso

### Paso 1 — Instalar Python

Si no tienes Python instalado:

1. Ve a https://www.python.org/downloads/
2. Descarga la versión **3.11** o superior (pulsa el botón amarillo grande)
3. Durante la instalación, **marca la casilla "Add Python to PATH"** (importante)
4. Completa la instalación

Para verificar que se instaló bien, abre el terminal (`cmd` en Windows) y escribe:
```
python --version
```
Debes ver algo como `Python 3.11.x`

---

### Paso 2 — Descargar el proyecto

Tienes dos opciones:

**Opción A — Con Git (recomendado):**
```bash
git clone https://github.com/barripdmx/tiktok-scraper.git
cd tiktok-scraper
```

**Opción B — Sin Git:**
1. Ve a https://github.com/barripdmx/tiktok-scraper
2. Pulsa el botón verde **"Code"** → **"Download ZIP"**
3. Descomprime el ZIP en la carpeta que quieras
4. Abre esa carpeta en el terminal

---

### Paso 3 — Instalar las dependencias Python

Dentro de la carpeta del proyecto, ejecuta:
```bash
pip install -r requirements.txt
```
Esto instala todas las librerías necesarias. Puede tardar 2-5 minutos la primera vez.

---

### Paso 4 — Instalar el navegador Chromium (para el scraper)

El scraper controla un navegador real para extraer datos de TikTok. Instala el navegador así:
```bash
playwright install chromium
```

---

### Paso 5 — Instalar el modelo de IA local (RoBERTa)

La primera vez que ejecutes el análisis de sentimiento, se descargará automáticamente el modelo RoBERTa (~500MB). No necesitas hacer nada, pero ten conexión a internet la primera vez.

---

## ⚙️ Configurar las claves API

### Crear el archivo de configuración

1. Entra a la carpeta `config/` del proyecto
2. Crea un archivo nuevo llamado **`.env`** (con el punto al principio)
3. Copia y pega este contenido, sustituyendo los valores por tus claves reales:

```env
MISTRAL_API_KEY=aquí_tu_clave_de_mistral
GROQ_API_KEY=aquí_tu_clave_de_groq
```

**Ejemplo real (con claves inventadas):**
```env
MISTRAL_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

> ⚠️ **Importante:** El archivo `.env` **nunca se sube a GitHub** (está en `.gitignore`). Tus claves son privadas y solo están en tu ordenador.

### ¿Cómo crear un archivo `.env` en Windows?

1. Abre el Bloc de notas
2. Pega el contenido con tus claves
3. Ve a **Archivo → Guardar como**
4. En "Nombre de archivo" escribe: `.env`
5. En "Tipo" selecciona: **Todos los archivos (\*.\*)**
6. Navega a la carpeta `config/` del proyecto
7. Pulsa **Guardar**

---

## 🚀 Primera ejecución

### Opción A — Menú visual (recomendado para principiantes)

Ejecuta el menú gráfico:
```bash
python menu.py
```

Se abrirá una ventana con todos los módulos. El orden recomendado es:

1. **Configuración (botón 0)** — Inicia sesión en TikTok. Se abrirá Chrome, inicia sesión manualmente y pulsa Enter en el terminal.
2. **Scraper de Usuario (botón 1)** — Escribe el nombre de una cuenta (sin @) y extrae todos sus vídeos.
3. **Analítica Publicaciones (botón 4)** — Genera las gráficas de rendimiento.
4. **Sentimiento con IA (botón 6)** — Clasifica los comentarios.
5. **Informe HTML (botón 8)** — Genera el informe final y lo abre en el navegador.

### Opción B — Terminal

```bash
# 1. Guardar sesión TikTok (solo la primera vez)
python src/scrapers/1-guardar_sesion.py

# 2. Extraer vídeos de un usuario
python src/scrapers/1_tiktok_scraper_user.py

# 3. Analizar publicaciones (genera gráficas)
python src/analysis/analitica_publicaciones.py

# 4. Analizar sentimiento de comentarios
python src/analysis/analizar_sentimiento.py

# 5. Generar informe HTML
python src/visualization/generar_informe_html.py
```

Los resultados se guardan en `outputs/nombre_cuenta/`.

---

## 📁 Estructura del proyecto

```
tiktok-scraper/
│
├── menu.py                          ← Menú gráfico principal (empieza aquí)
├── requirements.txt                 ← Lista de librerías a instalar
│
├── config/
│   ├── .env                         ← TUS CLAVES API (crear manualmente, no se sube a GitHub)
│   └── viz_style.py                 ← Paleta de colores de los gráficos
│
├── src/
│   ├── scrapers/
│   │   ├── 1-guardar_sesion.py      ← Paso 0: login en TikTok
│   │   ├── 1_tiktok_scraper_user.py ← Extrae vídeos de un @usuario
│   │   ├── 2_tiktok_scraper_hastag_api.py  ← Extrae vídeos de un #hashtag
│   │   └── 2_tiktok_scraper_comentarios_api.py  ← Extrae comentarios
│   │
│   ├── analysis/
│   │   ├── analitica_publicaciones.py  ← +15 gráficas de rendimiento
│   │   ├── analitica_comentarios.py    ← Nubes de palabras y análisis
│   │   ├── analizar_sentimiento.py     ← Pipeline IA: RoBERTa+Groq+Mistral
│   │   └── comparativa_usuarios.py     ← Comparar múltiples cuentas
│   │
│   └── visualization/
│       ├── generar_informe_html.py  ← Informe periodístico HTML autocontenido
│       └── crear_gexf.py           ← Grafo de redes para Gephi
│
├── data/                            ← CSVs descargados (no se suben a GitHub)
└── outputs/                         ← Gráficas e informes generados (no se suben)
```

---

## 🗂️ Estructura de carpetas por proyecto

Cada búsqueda (un usuario o un hashtag) es un **proyecto**. Todos sus datos y
resultados se agrupan en una carpeta con el nombre del proyecto, para que nada se
mezcle entre búsquedas distintas.

**Datos descargados** — `data/{proyecto}/`:
```
data/
 └─ zapatero_zp_plus_ultra/
     ├─ zapatero_zp_plus_ultra_videos_api.csv                     ← vídeos
     ├─ ..._comentarios_api.csv                                   ← comentarios
     ├─ ..._con_sentimiento_mistral.csv                           ← + análisis IA
     └─ ..._enriquecido_fechas_creacion.csv                       ← + datos de cuentas
```

**Resultados generados** — `outputs/{proyecto}/`:
```
outputs/
 └─ zapatero_zp_plus_ultra/
     ├─ informes/                          ← informe HTML final
     ├─ graficas_videos/
     │   └─ publicaciones/                 ← gráficas de rendimiento de vídeos
     └─ graficas_comentarios/
         ├─ (nubes de palabras, hashtags, heatmaps…)
         ├─ graficas_multidimensionales/   ← sesgo, arquetipo, intención
         ├─ graficas_patrones_cuentas/     ← patrones de bots + cuentas_a_revisar.csv
         └─ polaridad_ia/                  ← sentimiento
```

> **¿Tienes archivos de versiones anteriores sueltos en `data/`?** Ejecuta una vez
> `python scripts/migrar_estructura.py` (muestra el plan) y luego
> `python scripts/migrar_estructura.py --aplicar` para reorganizarlo todo
> automáticamente a esta estructura.

---

## ❓ Preguntas frecuentes

**¿Necesito pagar algo?**
No. Todas las APIs usadas tienen plan gratuito. Los límites gratuitos son más que suficientes para investigación y formación.

**¿Es legal hacer scraping de TikTok?**
El scraping de datos públicos (perfiles públicos, hashtags públicos) es un área legal compleja. Esta herramienta está pensada para investigación periodística y académica. Respeta los Términos de Servicio de TikTok y la normativa de protección de datos aplicable.

**¿El scraper siempre funciona?**
TikTok actualiza continuamente su web para dificultar el scraping. Si un scraper deja de funcionar, es probable que TikTok haya cambiado algo. Revisa los issues del repositorio para ver si hay una solución.

**¿Dónde se guardan los datos?**
Todo se guarda en local, en las carpetas `data/` y `outputs/`. Nada se sube a ningún servidor externo.

**El análisis de sentimiento da error la primera vez**
Es normal — está descargando el modelo RoBERTa (~500MB). Espera a que termine y vuelve a ejecutarlo.

---

## 🛠️ Stack tecnológico

| Componente | Tecnología |
|---|---|
| Scraping web | Playwright (Chromium) |
| Análisis de datos | Pandas, NumPy |
| Gráficas | Matplotlib, Seaborn |
| IA — Sentimiento local | pysentimiento (RoBERTa) |
| IA — Sentimiento nube | RoBERTa / Groq / Mistral |
| Nubes de palabras | WordCloud |
| Grafos de redes | NetworkX → GEXF (Gephi) |
| Interfaz gráfica | CustomTkinter |
| Configuración | python-dotenv |

---

*Desarrollado para periodismo de datos e investigación en redes sociales.*
