"""Script de prueba: genera solo las gráficas de sentimiento con datos existentes."""
import sys, os, json
import os; sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src', 'analysis')))
import pandas as pd

from analitica_comentarios import (
    create_output_folder,
    generar_grafica_sentimiento,
    generar_evolucion_sentimiento_acumulada,
    generar_nubes_sentimiento,
    generar_top_emojis,
)

CSV = "os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')), 'data', '')user_sanchezcastejon_videos_comentarios_mobile.csv"
FILE_ID = "user_sanchezcastejon_videos_comentarios_mobile"

print("Cargando CSV...")
df = pd.read_csv(CSV, low_memory=False)
df = df[df['is_reply'] == 0].reset_index(drop=True)
print(f"Comentarios directos: {len(df):,}")

file_id = FILE_ID + "_TEST"

# 1. CSV Mistral completo
csv_mistral = CSV.replace(".csv", "_con_sentimiento_mistral.csv")
if os.path.exists(csv_mistral):
    print("Cargando sentimiento desde CSV Mistral completo...")
    df = pd.read_csv(csv_mistral, low_memory=False)
    df = df[df['is_reply'] == 0].reset_index(drop=True)
    file_id = FILE_ID + "_mistral"

# 2. Checkpoint Mistral parcial
elif os.path.exists(CSV.replace(".csv", "_mistral_checkpoint.json")):
    print("Cargando sentimiento desde checkpoint Mistral parcial...")
    with open(CSV.replace(".csv", "_mistral_checkpoint.json")) as f:
        checkpoint = json.load(f)
    label_map = {"POS": "positivo", "NEG": "negativo", "NEU": "neutro"}
    df['sentimiento'] = [label_map.get(checkpoint.get(str(i), "NEU"), "neutro") for i in range(len(df))]
    # Quedarse solo con los que ya tienen clasificación real
    df = df[[str(i) in checkpoint for i in range(len(df))]].copy()
    print(f"Usando {len(df):,} comentarios del checkpoint")

else:
    print("ERROR: No hay datos de sentimiento disponibles.")
    sys.exit(1)

print(f"Distribución:\n{df['sentimiento'].value_counts()}")

create_output_folder(file_id)
print("\nGenerando gráficas con nuevo estilo...")
generar_grafica_sentimiento(df, file_id, 'steelblue')
generar_evolucion_sentimiento_acumulada(df, file_id)
generar_nubes_sentimiento(df, file_id)
generar_top_emojis(df, file_id)
print("\n¡Listo! Revisa la carpeta gráficas/")
