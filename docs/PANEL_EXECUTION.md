# 🎯 Ejecutar desde el Panel de Claude Code

## Opción 1: Alias corto (MÁS SIMPLE)

```bash
python scrap.py --help
python scrap.py
python scrap.py data/usuarios.csv
python scrap.py data/usuarios.csv 50
python scrap.py data/usuarios.csv 50 100
```

---

## Opción 2: Script directo (desde raíz)

```bash
python 2_tiktok_scraper_comentarios_api.py --help
python 2_tiktok_scraper_comentarios_api.py
python 2_tiktok_scraper_comentarios_api.py data/usuarios.csv
python 2_tiktok_scraper_comentarios_api.py data/usuarios.csv 50 100
```

---

## Opción 3: Script de test rápido

```bash
python test_scraper_quick.py data/usuarios.csv
```
✅ Test con 5 videos en ~1 minuto

---

## Opción 4: Interface amigable

```bash
python scraper.py
python scraper.py --help
python scraper.py data/usuarios.csv
```

---

## 📋 Ejemplos prácticos

### Test rápido para validar que funciona
```bash
python scrap.py --test data/usuarios.csv
```

### Procesar 10 videos
```bash
python scrap.py data/usuarios.csv 10
```

### Procesar 100 videos, máx 50 comentarios cada uno
```bash
python scrap.py data/usuarios.csv 100 50
```

### Diálogo interactivo
```bash
python scrap.py
```
→ Te pregunta CSV, cantidad, límite

### Procesar sin checkpoint anterior
```bash
python 2_tiktok_scraper_comentarios_api.py data/usuarios.csv --skip-checkpoint
```

---

## 🚀 Flujo típico desde panel

```bash
# 1. Test rápido (validar sesión)
python scrap.py --test data/usuarios.csv

# 2. Si funciona, procesar lote
python scrap.py data/usuarios.csv 50

# 3. Si falló, reiniciar sesión
python 1-guardar_sesion.py

# 4. Continuar desde donde quedó
python scrap.py data/usuarios.csv
```

---

## 📊 Parámetros CLI

| Comando | Resultado |
|---------|-----------|
| `python scrap.py` | Diálogo interactivo |
| `python scrap.py data/videos.csv` | Procesa CSV, diálogo para count/limit |
| `python scrap.py data/videos.csv 50` | 50 videos, diálogo para limit |
| `python scrap.py data/videos.csv 50 100` | 50 videos, máx 100 comentarios |
| `python scrap.py --help` | Ver todas las opciones |
| `python scrap.py --test data/videos.csv` | Test rápido (5 videos) |

---

## ✨ Lo que cambió

### ANTES (solo diálogo interactivo)
```bash
python 2_tiktok_scraper_comentarios_api.py
# → Pregunta CSV
# → Pregunta cuántos videos
# → Pregunta límite
```

### AHORA (CLI + diálogo)
```bash
# Opción 1: Solo CLI, sin diálogos
python scrap.py data/usuarios.csv 50 100

# Opción 2: CLI con diálogos
python scrap.py data/usuarios.csv

# Opción 3: Diálogo completo
python scrap.py
```

---

## 🎬 Próximos pasos

1. **Test**: `python scrap.py --test data/usuarios.csv`
2. **Procesar**: `python scrap.py data/usuarios.csv 10`
3. **Ver resultados**: `data/usuarios_comentarios_api.csv`

---

**Versión**: v2 REFACTORIZADO  
**Status**: ✅ Listo para panel
