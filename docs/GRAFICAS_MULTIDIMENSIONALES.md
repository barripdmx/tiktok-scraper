# 6 Gráficas Multidimensionales — Análisis Avanzado de Sentimiento

## 📊 Overview

Tras completar el análisis multidimensional de sentimiento (Punto 6), el **Informe HTML** ahora incluye automáticamente **6 visualizaciones avanzadas** que desglosan el análisis en dimensiones políticas, psicográficas, intencionales y culturales.

Las gráficas se generan **automáticamente** si el CSV de sentimiento contiene las columnas requeridas. Si faltan columnas, se degradan elegantemente (se omiten sin error).

---

## 🎯 Las 6 Gráficas

### 1️⃣ **Heatmap: Sesgo × Sentimiento**
- **¿Qué muestra?** Distribución de sentimiento (POS/NEG/NEU) dentro de cada bloque político
- **Eje X:** Sentimiento (Positivo, Neutro, Negativo)
- **Eje Y:** Sesgo político (Conservador, Progresista, Mixto, Neutro, No inferible)
- **Uso:** Identificar qué bloques son más positivos/negativos
- **Columnas requeridas:** `sentiment`, `bias`

### 2️⃣ **Arquetipos de Comentarista (Top 8)**
- **¿Qué muestra?** Los 8 arquetipos conductuales más frecuentes
- **Colores únicos:** Cada arquetipo tiene su propio color para identificación rápida
- **Ejemplos:**
  - 🔴 Testigo indignado (high emotion)
  - 🟣 Reactor de baja señal (noise/bot-like)
  - 🔵 Fiscal del meme (joke police)
  - 🟠 Moralista punitivo (judgmental)
- **Uso:** Segmentar estrategias de respuesta por tipo de comentarista
- **Columnas requeridas:** `archetype`

### 3️⃣ **Ranking de Pain Points (Frustraciones)**
- **¿Qué muestra?** Top 8 preocupaciones/frustraciones recurrentes
- **Ejemplos:**
  - 💔 Doble rasero fiscal
  - 😤 Fatiga de corrupción
  - ⚖️ Judicialización selectiva
  - 💰 Microeconomía (bolsillo)
  - 🎭 Pérdida terreno cultural
- **Uso:** Desarrollo de contenido y protección reputacional
- **Columnas requeridas:** `pain_point`

### 4️⃣ **Heatmap: Sesgo × Pain Point**
- **¿Qué muestra?** Matriz de qué frustraciones afectan a cada bloque político
- **Uso:** "Conservadores sufren por X, Progresistas por Y"
- **Aplicación estratégica:** Personalizar mensajes por segmento
- **Columnas requeridas:** `bias`, `pain_point`

### 5️⃣ **Scatter: Volumen vs Influencia**
- **¿Qué muestra?** Relación entre nº de comentarios y suma de likes por sesgo
- **Eje X:** Nº de comentarios (volumen)
- **Eje Y:** Suma de likes (influencia)
- **Tamaño burbuja:** Varianza de likes (coherencia de influencia)
- **Uso:** Identificar "pesos pesados" (mucho volumen + muchos likes)
- **Columnas requeridas:** `bias`, `likes_count` (opcional)

### 6️⃣ **Dona: Sarcasmo dentro de NEG**
- **¿Qué muestra?** Desglose de comentarios negativos en:
  - **NEG Legítimo** (crítica genuina)
  - **Sarcasmo/Ironía** 🤨 (crítica envuelta en broma)
- **Uso:** Moderar respuestas apropiadamente (sarcasmo no siempre requiere respuesta defensiva)
- **Columnas requeridas:** `sentiment`, `sarcasm`

---

## 🔧 Cómo Usarlas

### Opción 1: Automática (Recomendado)

Después de completar el análisis multidimensional (Punto 6), simplemente:

```bash
# Opción 8 del menú: Generar Informe HTML
py menu.py
# Selecciona 8
```

Las gráficas se generarán automáticamente dentro de la sección "Análisis avanzado con IA".

### Opción 2: Manual (Script auxiliar)

```bash
python scripts/generar_informe_con_graficas.py data/usuario_videos.csv
```

Si el CSV de sentimiento existe, se detecta automáticamente.

### Opción 3: Regenerar solo las gráficas

```python
from src.visualization.grafica_multidimensional import generar_todas_graficas
import pandas as pd

df_sentimiento = pd.read_csv("data/usuario_con_sentimiento_mistral.csv")
graficas = generar_todas_graficas(df_sentimiento)

# graficas es un dict con base64 PNGs embebibles
for nombre, b64 in graficas.items():
    if b64:
        print(f"✅ {nombre}")
```

---

## 📋 Requisitos de Columnas

| Gráfica | Columnas requeridas | Qué pasa si faltan |
|---------|---------------------|-------------------|
| Heatmap Sesgo × Sentimiento | `sentiment`, `bias` | Se omite |
| Arquetipos | `archetype` | Se omite, tabla de fallback |
| Pain Points | `pain_point` | Se omite, tabla de fallback |
| Heatmap Sesgo × Pain Point | `bias`, `pain_point` | Se omite |
| Volumen vs Influencia | `bias`, (opcional `likes_count`) | Se omite |
| Sarcasmo en NEG | `sentiment`, `sarcasm` | Se omite |

**Nota:** Si ejecutaste el Punto 6 con la versión actualizada (commit 5104395+), todas las columnas estarán presentes.

---

## 🎨 Paleta de Colores

### Sesgo Político
- 🟦 **Conservador:** #2C3E50 (gris-azul oscuro)
- 🟥 **Progresista:** #A93226 (rojo oscuro)
- 🟩 **Mixto:** #8E44AD (púrpura)
- ⬜ **Neutro:** #7F8C8D (gris)
- ⬜ **No inferible:** #BDC3C7 (gris claro)

### Arquetipos
Cada uno tiene su propio color para identificación rápida. Ver `src/visualization/grafica_multidimensional.py` línea ~50.

### Sentimiento
- 🟩 **Positivo:** #1E8449 (verde)
- 🟥 **Negativo:** #A93226 (rojo)
- ⬜ **Neutro:** #4A4A4A (gris)

---

## ⚡ Rendimiento

- **Tiempo de generación:** < 2 segundos (6 gráficas)
- **Tamaño en HTML:** ~500 KB (base64 PNG embebido)
- **Compatible:** Offline, sin CDN, funciona en cualquier navegador

---

## 🐛 Troubleshooting

### Las gráficas no aparecen en el HTML

**Síntoma:** HTML generado pero sin visualizaciones multidimensionales

**Causas posibles:**
1. CSV de sentimiento no tiene las columnas esperadas
   - Solución: Re-ejecuta el Punto 6 con la versión actualizada
   
2. `grafica_multidimensional.py` no está en `src/visualization/`
   - Solución: Verifica que el archivo exista en la ubicación correcta

3. Faltan dependencias (`seaborn`, `numpy`, `matplotlib`)
   - Solución: `pip install seaborn numpy matplotlib`

### Errores de tipografía (emoji faltante)

**Síntoma:** "UserWarning: Glyph 129320 missing from font(s)"

**Impacto:** Visual solo; la gráfica se genera correctamente pero sin el emoji 🤨

**Solución:** Ignorar (es cosmético). Si molesta, usa `-c "import matplotlib; matplotlib.rcParams['font.family'] = 'Segoe UI Symbol'"` antes

---

## 📈 Roadmap

- [ ] Exportar gráficas individuales como PNG/SVG
- [ ] Temas (claro/oscuro) en gráficas
- [ ] Gráficas interactivas (Plotly)
- [ ] Dashboard embebido en lugar de HTML estático

---

## 📞 Contacto

Para reportar problemas o sugerencias sobre las gráficas, contacta al equipo de análisis.
