# TikTok Comment Scraper — Guía de Uso v2

## 🚀 Ejecución Rápida

### Opción 1: Test rápido (5 videos, sin demora)
```bash
python test_scraper_quick.py data/videos.csv
```
Ideal para validar que el scraper funciona correctamente.

---

### Opción 2: Con parámetros CLI
```bash
# Procesar 10 videos, máx 100 comentarios cada uno
python src/scrapers/2_tiktok_scraper_comentarios_api.py data/videos.csv --count 10 --limit 100

# Procesar todos los videos del CSV
python src/scrapers/2_tiktok_scraper_comentarios_api.py data/videos.csv

# Reiniciar desde cero (ignorar checkpoint anterior)
python src/scrapers/2_tiktok_scraper_comentarios_api.py data/videos.csv --skip-checkpoint
```

---

### Opción 3: Menú interactivo (sin parámetros)
```bash
python src/scrapers/2_tiktok_scraper_comentarios_api.py
```
Te preguntará:
1. Ruta del CSV
2. Cuántos videos procesar
3. Límite de comentarios por video
4. Si continuar desde checkpoint anterior

---

## 📋 Parámetros

| Parámetro | Ejemplo | Descripción |
|-----------|---------|-------------|
| CSV | `data/videos.csv` | Archivo con URLs de videos (posición 1) |
| `--count` | `--count 5` | Procesa solo N primeros videos |
| `--limit` | `--limit 100` | Máximo de comentarios por video |
| `--skip-checkpoint` | (flag) | Ignora checkpoint, reinicia desde cero |
| `--help` | (flag) | Muestra esta ayuda |

---

## 📂 Estructura de archivos

```
data/
├── videos.csv                        ← Entrada: URLs de videos
├── {base}_comentarios_api.csv        ← Salida: comentarios descargados
├── {base}_checkpoint.json            ← Estado: vídeos ya procesados
└── logs/
    └── comentarios_api_[timestamp].log   ← Log de ejecución
```

---

## 🔄 Checkpoint y Reanudación

El scraper guarda automáticamente el progreso:

```bash
# Primera ejecución: procesa 50 videos
python src/scrapers/2_tiktok_scraper_comentarios_api.py data/videos.csv --count 50

# Segunda ejecución: pregunta si continuar desde donde quedó
python src/scrapers/2_tiktok_scraper_comentarios_api.py data/videos.csv
# → "♻️ Checkpoint: 50 videos ya procesados"
# → "¿Continuar? (S/n):"

# Para reiniciar desde cero:
python src/scrapers/2_tiktok_scraper_comentarios_api.py data/videos.csv --skip-checkpoint
```

---

## 📊 Estados de salida

El scraper reporta explícitamente:

| Estado | Símbolo | Significado |
|--------|---------|-------------|
| **Exitoso** | ✅ | Comentarios descargados (70%+ cobertura) |
| **Exitoso (bajo)** | ⚠️ | Comentarios descargados (<70% cobertura) |
| **Deshabilitados** | 🚫 | Video tiene comentarios cerrados |
| **Panel error** | ❌ | Botón no encontrado o UI rota |
| **Sin respuesta** | ⏱ | API silenciosa >50s |

---

## 📈 Ejemplo de resumen final

```
==================================================
RESUMEN FINAL
==================================================
✅ Exitosos:      18/20
🚫 Deshabilitados: 1
❌ Errores:       1
Comentarios:    12.547
Cobertura:      82% (12.547/15.301)
CSV:            data/usuarios_comentarios_api.csv
==================================================
```

---

## 🎯 Casos de uso comunes

### Caso 1: Procesar un pequeño lote (test)
```bash
python test_scraper_quick.py data/videos.csv --limit 50
```

### Caso 2: Procesar todos los videos, máximo 3 horas
```bash
# 100 videos × 10-15s = ~20 min por lote
python src/scrapers/2_tiktok_scraper_comentarios_api.py data/videos.csv --count 100
```

### Caso 3: Continuar ejecución anterior (dejó de funcionar)
```bash
# Detecta automáticamente el checkpoint
python src/scrapers/2_tiktok_scraper_comentarios_api.py data/videos.csv
# → Responde "S" cuando pregunte
```

### Caso 4: Analizar solo comentarios principales (sin replies)
```bash
# El CSV generado tiene columna "is_reply" (0=principal, 1=respuesta)
# Filtra en Excel o pandas después
```

---

## 🔧 Requisitos

- ✅ Python 3.8+
- ✅ Playwright (`pip install playwright`)
- ✅ Sesión guardada (`python 1-guardar_sesion.py`)
- ✅ CSV con columna `video_url`

---

## 📝 Columnas del CSV de salida

```csv
video_id,video_url,username,comment_id,fecha,autor_nombre,autor_handle,texto,likes,aweme_id_api,is_reply,parent_comment_id
7123456789,https://www.tiktok.com/@usuario/video/7123456789,...
```

---

## ⏱ Tiempo estimado

- **Videos pequeños (0-100 comentarios)**: 8-12s cada uno
- **Videos medianos (100-500)**: 15-30s cada uno
- **Videos virales (500+)**: 30-60s cada uno
- **Deshabilitados**: 5-8s cada uno (detecta rápido)

**Estimación para 100 videos**: 20-40 minutos

---

## 🚨 Troubleshooting

### "No se encontró botón de comentarios"
```bash
# Reinicia la sesión:
python 1-guardar_sesion.py
python src/scrapers/2_tiktok_scraper_comentarios_api.py data/videos.csv
```

### "Cookies no cargadas"
```bash
# Asegúrate de que exista:
data/tiktok_cookies.json
# Si no, ejecuta:
python 1-guardar_sesion.py
```

### Muchos videos "🚫 Comentarios deshabilitados"
```bash
# Normal: algunos creadores desactivan comentarios
# Revisa el resumen final para estadísticas
```

---

## 📜 Log de ejecución

Cada ejecución genera un log individual:
```
data/logs/comentarios_api_20260430_154823.log
```

Contiene toda la traza: detectores activados, triggers, respuestas API, etc.

---

**Versión**: v2 REFACTORIZADO (sin evaluación heurística de triggers)  
**Última actualización**: 2026-04-30
