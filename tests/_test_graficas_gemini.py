"""Test de analizar_sentimiento_gemini.py — solo gráficas con datos existentes."""
import sys, os, json
import os; sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src', 'analysis')))
import pandas as pd

from analizar_sentimiento_gemini import (
    create_output_folder,
    generar_grafica_sentimiento,
    generar_evolucion_acumulada,
    generar_top_comentarios_sentimiento,
    generar_top_usuarios_sentimiento,
)

CSV     = "os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')), 'data', '')user_sanchezcastejon_videos_comentarios_mobile.csv"
FILE_ID = "user_sanchezcastejon_videos_comentarios_mobile"

print("Cargando CSV...")
df = pd.read_csv(CSV, low_memory=False)
df = df[df['is_reply'] == 0].reset_index(drop=True)
print(f"Comentarios directos: {len(df):,}")

checkpoint_path = CSV.replace(".csv", "_gemini_checkpoint.json")
if not os.path.exists(checkpoint_path):
    print("ERROR: No hay checkpoint de Gemini disponible.")
    sys.exit(1)

print("Cargando sentimiento desde checkpoint Gemini...")
with open(checkpoint_path) as f:
    checkpoint = json.load(f)
label_map = {"POS": "positivo", "NEG": "negativo", "NEU": "neutro"}
df['sentimiento'] = [label_map.get(checkpoint.get(str(i), "NEU"), "neutro") for i in range(len(df))]
print(f"Distribución:\n{df['sentimiento'].value_counts()}")

create_output_folder(FILE_ID)
print(f"\nGenerando gráficas Gemini en: gráficas/user_sanchezcastejon/\n")

generar_grafica_sentimiento(df, FILE_ID)
generar_evolucion_acumulada(df, FILE_ID)
generar_top_comentarios_sentimiento(df, FILE_ID)
generar_top_usuarios_sentimiento(df, FILE_ID)

print("\n¡Listo! Revisa gráficas/user_sanchezcastejon/")
