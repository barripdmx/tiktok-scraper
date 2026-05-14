# 🚀 Quick Start — Scraper de Comentarios

## Lo más simple posible

```bash
# 1️⃣ Test rápido (5 videos en ~1 min)
python scraper.py --test data/usuarios.csv

# 2️⃣ Procesar X videos
python scraper.py data/usuarios.csv 50

# 3️⃣ Procesar X videos, máx Y comentarios cada uno
python scraper.py data/usuarios.csv 100 200

# 4️⃣ Ver ayuda
python scraper.py --help
```

---

## Archivos de entrada / salida

```
INPUT:
  data/usuarios.csv                    (Columna: video_url)

OUTPUT:
  data/usuarios_comentarios_api.csv    (✅ Comentarios descargados)
  data/usuarios_checkpoint.json        (♻️ Progreso guardado)
  data/logs/comentarios_api_*.log      (📝 Detalles)
```

---

## Estados posibles

| Símbolo | Significado |
|---------|-------------|
| ✅ | Exitoso (70%+ cobertura) |
| ⚠️ | Exitoso (< 70% cobertura) |
| 🚫 | Comentarios deshabilitados |
| ❌ | Error (panel no encontrado) |
| ⏱ | Sin respuesta API |

---

## Ejemplos CLI

```bash
# Test (5 videos, máx 50 comentarios)
python scraper.py --test data/usuarios.csv

# 10 videos, diálogo interactivo para limit
python scraper.py data/usuarios.csv 10

# 50 videos, máx 100 comentarios cada uno
python scraper.py data/usuarios.csv 50 100

# Reanudar desde checkpoint
python scraper.py data/usuarios.csv
# → Responde "S" cuando pregunte

# Reiniciar desde cero
python src/scrapers/2_tiktok_scraper_comentarios_api.py data/usuarios.csv --skip-checkpoint
```

---

## Requisitos previos

✅ Sessión guardada:
```bash
python 1-guardar_sesion.py
```

✅ CSV con columna `video_url`

---

## Troubleshooting rápido

| Problema | Solución |
|----------|----------|
| Cookies no cargadas | `python 1-guardar_sesion.py` |
| Panel no encontrado | Reinicia sesión |
| Muchos "🚫 Deshabilitados" | Normal (creadores cierran comentarios) |

---

## Tiempos estimados

- **1 video**: ~10s
- **10 videos**: ~2 min
- **50 videos**: ~10 min
- **100 videos**: ~20 min
- **1000 videos**: ~3-4h

---

**Ver más detalles**: `SCRAPER_USAGE.md`
