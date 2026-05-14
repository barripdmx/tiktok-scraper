"""
Runner para regenerar solo la nube de palabras de sanchezcastejon
sin diálogos tkinter. Usa el CSV existente adaptando nombres de columnas.
"""
import os
import sys
# Añadir ruta para importar analitica_comentarios
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(BASE_DIR, "src", "analysis"))

import pandas as pd
from analitica_comentarios import generar_nubes, create_output_folder

CSV = os.path.join(BASE_DIR, "data", "user_sanchezcastejon_videos_comentarios_mobile.csv")
FILE_ID = "user_sanchezcastejon_videos_comentarios_mobile"
COLOR = "darkred"

df = pd.read_csv(CSV)

print(f"Cargados {len(df):,} comentarios.")
create_output_folder(FILE_ID)
generar_nubes(df, FILE_ID, COLOR, COLOR)
print("Nube generada.")
