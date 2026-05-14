"""Script de prueba: genera todas las gráficas de publicaciones con datos existentes."""
import sys
import os; sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src', 'analysis')))

from analitica_publicaciones import (
    create_output_folder,
    apply_estilo_periodistico,
    graf_nube_palabras,
    graf_nube_hashtags,
    graf_nube_emoticonos,
    graf_evolucion_vistas,
    graf_publicaciones_por_mes,
    graf_publicaciones_por_dia,
    graf_publicaciones_por_hora,
    graf_heatmap,
    graf_timeline,
)
import pandas as pd

CSV = "os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')), 'data', '')user_sanchezcastejon_videos.csv"
FILE_ID = "user_sanchezcastejon_videos"
COLOR = "#A93226"

print("Cargando CSV...")
df = pd.read_csv(CSV, low_memory=False)
print(f"Publicaciones: {len(df):,}")

# Parsear fechas y columnas derivadas (como hace main())
df['video_fecha_dt'] = pd.to_datetime(df['video_fecha'], dayfirst=True)
df = df.sort_values('video_fecha_dt')
df['dia_semana'] = df['video_fecha_dt'].dt.dayofweek
df['hora'] = df['video_fecha_dt'].dt.hour

create_output_folder(FILE_ID)
print("\nGenerando gráficas con estilo periodístico...")

graf_nube_palabras(df, FILE_ID, COLOR)
graf_nube_hashtags(df, FILE_ID, COLOR)
graf_nube_emoticonos(df, FILE_ID, COLOR)
graf_evolucion_vistas(df, FILE_ID, COLOR)
graf_publicaciones_por_mes(df, FILE_ID, COLOR)
graf_publicaciones_por_dia(df, FILE_ID, COLOR)
graf_publicaciones_por_hora(df, FILE_ID, COLOR)
graf_heatmap(df, FILE_ID)
graf_timeline(df, FILE_ID, COLOR)

print("\n¡Listo! Revisa la carpeta gráficas/")
