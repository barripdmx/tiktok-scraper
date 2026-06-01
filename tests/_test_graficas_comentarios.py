"""Test completo de analitica_comentarios.py — todas las gráficas."""
import sys, os, json
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(BASE_DIR, "src", "analysis"))
import pandas as pd

from analitica_comentarios import (
    create_output_folder,
    generar_nubes,
    generar_analisis_comunidad,
    generar_analisis_temporal,
    generar_grafica_sentimiento,
    generar_evolucion_sentimiento_acumulada,
    generar_nubes_sentimiento,
    generar_top_emojis,
)

CSV     = os.path.join(BASE_DIR, "data", "user_sanchezcastejon_videos_comentarios_mobile.csv")
FILE_ID = "user_sanchezcastejon_videos_comentarios_mobile"
COLOR   = "#A93226"

print("Cargando CSV...")
df = pd.read_csv(CSV, low_memory=False)
df = df[df['is_reply'] == 0].reset_index(drop=True)
print(f"Comentarios directos: {len(df):,}")

# Cargar sentimiento desde checkpoint Mistral
checkpoint_path = CSV.replace(".csv", "_mistral_checkpoint.json")
if os.path.exists(checkpoint_path):
    print("Cargando sentimiento desde checkpoint Mistral...")
    with open(checkpoint_path) as f:
        checkpoint = json.load(f)
    label_map = {"POS": "positivo", "NEG": "negativo", "NEU": "neutro"}
    df['sentimiento'] = [label_map.get(checkpoint.get(str(i), "NEU"), "neutro") for i in range(len(df))]
    print(f"Distribución:\n{df['sentimiento'].value_counts()}")
else:
    print("Sin checkpoint de sentimiento — se omitirán gráficas de sentimiento.")
    df['sentimiento'] = 'neutro'

create_output_folder(FILE_ID)
print(f"\nGenerando gráficas en: outputs/graphics/user_sanchezcastejon/\n")

generar_nubes(df, FILE_ID, COLOR, COLOR)
generar_analisis_comunidad(df, FILE_ID, COLOR)
generar_analisis_temporal(df, FILE_ID, COLOR)
generar_grafica_sentimiento(df, FILE_ID, COLOR)
generar_evolucion_sentimiento_acumulada(df, FILE_ID)
generar_nubes_sentimiento(df, FILE_ID)
generar_top_emojis(df, FILE_ID)

print("\n¡Listo! Revisa gráficas/user_sanchezcastejon/")
