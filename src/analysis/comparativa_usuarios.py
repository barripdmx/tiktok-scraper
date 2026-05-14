# -*- coding: utf-8 -*-
"""
================================================================================
Análisis Comparativo de Sentimiento de Usuarios entre Cuentas de TikTok
================================================================================

DESCRIPCIÓN:
    Este script analiza múltiples archivos de comentarios de TikTok para encontrar
    patrones de comportamiento en los usuarios. Específicamente, identifica a
    los comentaristas que muestran un sentimiento consistentemente positivo hacia
    una cuenta y/o negativo hacia otras.

    El proceso es el siguiente:
    1. Pide al usuario que seleccione múltiples archivos CSV de comentarios.
    2. Fusiona los datos, etiquetando cada comentario con su 'cuenta de destino'.
    3. Realiza un análisis de sentimiento para cada comentario.
    4. Calcula una puntuación de "sentimiento neto" (positivos - negativos) para
       cada comentarista hacia cada cuenta de destino.
    5. Identifica a los comentaristas más polarizados y activos.
    6. Genera un gráfico de barras agrupadas que visualiza el sentimiento neto
       de estos usuarios clave a través de las diferentes cuentas.

USO:
    python comparativa_usuarios.py
    - Se abrirán ventanas para seleccionar los archivos CSV uno por uno.
    - Cuando no quieras añadir más archivos, responde "No" a la pregunta.
    - La gráfica se guardará en la carpeta 'gráficas'.
"""

import pandas as pd
import matplotlib.pyplot as plt
import tkinter as tk
from tkinter import filedialog, messagebox
import os
import re
import seaborn as sns

# --- CONFIGURACIÓN ---
BASE_DIR      = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUTPUT_FOLDER = os.path.join(BASE_DIR, "outputs", "graphics")
TOP_N_USERS   = 20  # Número de usuarios a mostrar en la gráfica final

# --- LISTAS DE SENTIMIENTO (LEXICON-BASED) ---
PALABRAS_POSITIVAS = [
    'gracias', 'bien', 'buen', 'buena', 'genial', 'excelente', 'increíble', 'maravilloso', 'amo', 'me encanta',
    'perfecto', 'guay', 'chulo', 'mola', 'crack', 'jajaja', 'jejeje', 'grande', 'top', 'el mejor', 'la mejor',
    'ayuda', 'solución', 'rápido', 'eficiente', 'barato', 'económico', 'calidad', 'brutal', 'guapo', 'guapa'
]
PALABRAS_NEGATIVAS = [
    'asco', 'odio', 'mierda', 'puta', 'puto', 'joder', 'no funciona', 'lento', 'caro', 'estafa', 'engaño',
    'problema', 'error', 'fallo', 'basura', 'ladrone', 'robo', 'nunca más', 'pésimo', 'horrible', 'decepcion',
    'malo', 'mala', 'vergüenza', 'incompetente', 'desastre', 'harto', 'harta', 'queja', 'reclamacion'
]
EMOJIS_POSITIVOS = "😂🤣❤😍😊😁👍✅👏🔥♥️🤩✨💯✔️🥰😘"
EMOJIS_NEGATIVOS = "😡😠😤🤬😒🙄😭🤦🤦‍♂️🤦‍♀️👎🤮💩"

# --- FUNCIONES AUXILIARES ---

def create_output_folder():
    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)

def seleccionar_archivo(num_archivo):
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    filepath = filedialog.askopenfilename(
        title=f"Selecciona el CSV de comentarios #{num_archivo}",
        filetypes=[("CSV Files", "*.csv")]
    )
    root.destroy()
    return filepath

def preguntar_mas_archivos():
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    respuesta = messagebox.askyesno(
        "¿Más archivos?",
        "¿Quieres añadir otro archivo CSV a la comparativa?"
    )
    root.destroy()
    return respuesta

def analizar_sentimiento_lexico(df):
    """Clasifica el sentimiento de cada comentario y lo añade como columna."""
    def clasificar(texto):
        texto = str(texto).lower()
        score_pos = sum(1 for word in PALABRAS_POSITIVAS if word in texto)
        score_neg = sum(1 for word in PALABRAS_NEGATIVAS if word in texto)
        score_pos += sum(1 for char in texto if char in EMOJIS_POSITIVOS)
        score_neg += sum(1 for char in texto if char in EMOJIS_NEGATIVOS)
        
        if score_pos > score_neg: return "positivo"
        if score_neg > score_pos: return "negativo"
        return "neutro"
        
    df['sentimiento'] = df['texto'].apply(clasificar)
    return df

def extraer_target_account(filename):
    """Extrae el nombre de la cuenta del nombre del archivo CSV."""
    # user_vodafone_es_videos_comentarios.csv -> vodafone_es
    match = re.search(r'user_([a-zA-Z0-9_]+)_videos_comentarios', filename)
    if match:
        return match.group(1)
    # fallback por si el nombre no coincide exactamente
    return os.path.splitext(os.path.basename(filename))[0]

# --- FUNCIÓN PRINCIPAL ---

def main():
    create_output_folder()
    print("--- INICIANDO ANÁLISIS COMPARATIVO DE USUARIOS ---")
    
    archivos_cargados = []
    df_list = []
    num_archivo = 1

    # 1. Carga Múltiple de Archivos
    while True:
        filepath = seleccionar_archivo(num_archivo)
        if not filepath:
            if not df_list:
                print("No se seleccionó ningún archivo. Saliendo.")
                return
            else:
                break

        print(f"Cargando archivo #{num_archivo}: {os.path.basename(filepath)}")
        try:
            temp_df = pd.read_csv(filepath)
            
            # Valida columnas necesarias
            required_cols = ['autor_handle', 'texto']
            if not all(col in temp_df.columns for col in required_cols):
                print(f"  -> Error: El archivo debe contener las columnas: {', '.join(required_cols)}. Omitiendo.")
                continue

            # 2. Identificación y Fusión
            target_account = extraer_target_account(os.path.basename(filepath))
            temp_df['target_account'] = target_account
            print(f"  -> Cuenta de destino identificada: '{target_account}'")
            df_list.append(temp_df)
            archivos_cargados.append(os.path.basename(filepath))
            num_archivo += 1
        except Exception as e:
            print(f"  -> Error al leer el archivo: {e}. Omitiendo.")

        if not preguntar_mas_archivos():
            break
            
    if not df_list:
        print("No se cargaron datos válidos. Saliendo.")
        return

    print(f"\nFusionando {len(df_list)} archivos...")
    df_full = pd.concat(df_list, ignore_index=True)
    print(f"Total de comentarios a analizar: {len(df_full)}")

    # 3. Análisis de Sentimiento
    print("Realizando análisis de sentimiento...")
    df_full = analizar_sentimiento_lexico(df_full)

    # 4. Cálculo de "Polaridad"
    print("Calculando sentimiento neto por usuario...")
    df_polar = df_full[df_full['sentimiento'] != 'neutro'].copy()
    
    # Cuenta comentarios positivos y negativos por separado
    sentiment_counts = df_polar.groupby(['autor_handle', 'target_account', 'sentimiento']).size().unstack(fill_value=0)
    sentiment_counts['net_sentiment'] = sentiment_counts.get('positivo', 0) - sentiment_counts.get('negativo', 0)
    sentiment_counts['total_polar'] = sentiment_counts.get('positivo', 0) + sentiment_counts.get('negativo', 0)
    
    # 5. Identificar usuarios más relevantes
    # Sumamos todos los comentarios polarizados que ha hecho un usuario
    top_users = sentiment_counts.groupby('autor_handle')['total_polar'].sum().nlargest(TOP_N_USERS).index
    
    if top_users.empty:
        print("\nNo se encontraron usuarios con comentarios positivos o negativos para comparar.")
        return
        
    print(f"\nTop {TOP_N_USERS} usuarios más polarizados seleccionados para la gráfica.")
    
    # Prepara los datos para el gráfico
    data_to_plot = sentiment_counts.loc[sentiment_counts.index.get_level_values('autor_handle').isin(top_users)]
    
    # Pivot table para el gráfico: usuarios en el eje X, sentimiento neto en Y, agrupado por cuenta
    plot_pivot = data_to_plot.reset_index().pivot(index='autor_handle', columns='target_account', values='net_sentiment')
    
    # Reordena las filas según la lista de top_users para mantener el orden
    plot_pivot = plot_pivot.loc[top_users]
    
    # 6. Visualización Comparativa
    print("Generando gráfico comparativo...")
    
    # Usar una paleta de colores atractiva
    num_accounts = len(plot_pivot.columns)
    palette = sns.color_palette("viridis", num_accounts)
    
    ax = plot_pivot.plot(
        kind='bar',
        figsize=(20, 12),
        width=0.8,
        color=palette,
        edgecolor='black'
    )

    # Añadir línea en y=0 para claridad
    ax.axhline(0, color='grey', linewidth=1.2, linestyle='--')

    # Mejorar estética
    plt.title(f'Análisis Comparativo de Sentimiento de los {TOP_N_USERS} Usuarios más Activos', fontsize=20, fontweight='bold', pad=20)
    plt.xlabel('Comentarista', fontsize=14, labelpad=15)
    plt.ylabel('Sentimiento Neto (Positivos - Negativos)', fontsize=14, labelpad=15)
    plt.xticks(rotation=45, ha='right', fontsize=12)
    plt.yticks(fontsize=12)
    
    # Leyenda
    plt.legend(title='Cuenta de Destino', fontsize=12, title_fontsize=14)
    
    plt.grid(axis='y', linestyle=':', alpha=0.6)
    
    # Guardar la figura
    output_filename = os.path.join(OUTPUT_FOLDER, 'comparativa_sentimiento_usuarios.png')
    plt.savefig(output_filename, bbox_inches='tight')
    plt.close()
    
    print(f"\n¡PROCESO COMPLETADO!")
    print(f"Gráfica guardada en: {output_filename}")

if __name__ == "__main__":
    main()
