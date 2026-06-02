#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de prueba: genera las 6 gráficas multidimensionales con datos simulados
y verifica que funcionan correctamente.
"""

import sys
import os

# Añadir src/visualization al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src", "visualization")))

import pandas as pd
import numpy as np
from grafica_multidimensional import (
    grafica_heatmap_sesgo_sentimiento,
    grafica_arquetipos,
    grafica_pain_points,
    grafica_heatmap_sesgo_pain_point,
    grafica_volumen_vs_influencia,
    grafica_sarcasmo_en_negativo,
    generar_todas_graficas,
)

# Crear dataframe de prueba con datos simulados
print("Creando dataset de prueba...")
n = 1000

data = {
    'sentiment': np.random.choice(['POS', 'NEG', 'NEU'], n, p=[0.3, 0.4, 0.3]),
    'bias': np.random.choice(['conservador', 'progresista', 'neutro', 'mixto', 'no_inferible'], n),
    'archetype': np.random.choice([
        'testigo_indignado', 'reactor_bajo_senal', 'meme_fiscal', 'moralista_punitivo',
        'amplificador', 'redirector_partidista', 'defensor_esceptico', 'igualador_antisistema',
        'expansor_conspirativo', 'buscador_contexto', 'otro'
    ], n),
    'intent': np.random.choice(['compra', 'info', 'difusion', 'castigo', 'ninguna'], n),
    'pain_point': np.random.choice([
        'doble_rasero_fiscal', 'fatiga_corrupcion', 'judicializacion_selectiva',
        'microeconomia', 'perdida_terreno_cultural', 'sobreproduccion_falsedad', 'otro', 'ninguno'
    ], n),
    'sarcasm': np.random.choice([True, False], n, p=[0.2, 0.8]),
    'noise': np.random.choice([True, False], n, p=[0.1, 0.9]),
    'likes_count': np.random.randint(0, 1000, n),
}

df = pd.DataFrame(data)

print(f"Dataset de prueba: {len(df)} comentarios")
print(f"\nDistribución de sentimiento:")
print(df['sentiment'].value_counts())
print(f"\nDistribución de sesgo:")
print(df['bias'].value_counts())

# Generar todas las gráficas
print("\n" + "="*60)
print("Generando gráficas multidimensionales...")
print("="*60)

graficas = generar_todas_graficas(df)

# Verificar resultados
for nombre, b64 in graficas.items():
    if b64:
        size_kb = len(b64) / 1024
        print(f"✅ {nombre:.<45} {size_kb:>6.1f} KB")
    else:
        print(f"⚠️  {nombre:.<45} (sin datos)")

# Crear carpeta de salida
output_dir = os.path.join(os.path.dirname(__file__), "..", "outputs", "test_graficas_multidim")
os.makedirs(output_dir, exist_ok=True)

# Guardar las gráficas como archivos PNG para inspección visual
print(f"\n✅ Guardando gráficas en: {output_dir}")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import base64

for nombre, b64 in graficas.items():
    if b64:
        # Decodificar base64 y guardar como PNG
        png_data = base64.b64decode(b64)
        filepath = os.path.join(output_dir, f"{nombre}.png")
        with open(filepath, "wb") as f:
            f.write(png_data)
        print(f"   📊 {nombre}.png")

print("\n✅ Prueba completada. Abre las imágenes PNG para verlas.")
