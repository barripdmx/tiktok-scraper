#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script auxiliar: Generar informe HTML con gráficas multidimensionales automaticamente.

USAGE:
  python scripts/generar_informe_con_graficas.py <csv_videos> [csv_sentimiento]

Si no se proporciona csv_sentimiento, intenta encontrarlo automáticamente buscando
archivos con patrón *_con_sentimiento_*.csv en la carpeta data/.

Esto es un wrapper que llama a generar_informe_html.py pero asegura que las
6 gráficas multidimensionales estén disponibles.
"""

import sys
import os
import subprocess
import glob

def main():
    if len(sys.argv) < 2:
        print("Usage: python generar_informe_con_graficas.py <csv_videos> [csv_sentimiento]")
        print("\nEjemplo:")
        print("  python generar_informe_con_graficas.py data/usuario_videos.csv")
        print("\nSi se omite csv_sentimiento, se busca automáticamente en data/")
        sys.exit(1)

    csv_videos = sys.argv[1]
    csv_sentimiento = sys.argv[2] if len(sys.argv) > 2 else None

    # Verificar que csv_videos existe
    if not os.path.exists(csv_videos):
        print(f"❌ Archivo no encontrado: {csv_videos}")
        sys.exit(1)

    # Si no se proporciona csv_sentimiento, buscarlo
    if not csv_sentimiento:
        base_name = os.path.splitext(os.path.basename(csv_videos))[0].replace("_videos", "")
        data_dir = os.path.dirname(csv_videos) or "data"

        candidates = glob.glob(os.path.join(data_dir, f"{base_name}*_con_sentimiento*.csv"))
        if candidates:
            csv_sentimiento = candidates[0]
            print(f"📋 CSV de sentimiento encontrado: {os.path.basename(csv_sentimiento)}")
        else:
            print(f"⚠️  No se encontró CSV de sentimiento para {base_name}")
            print("   (el informe se generará pero sin análisis multidimensional)")
            csv_sentimiento = None

    # Llamar a generar_informe_html.py
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    script_path = os.path.join(project_root, "src", "visualization", "generar_informe_html.py")

    cmd = [sys.executable, script_path, csv_videos]
    if csv_sentimiento:
        cmd.append(csv_sentimiento)

    print(f"\n🚀 Ejecutando: {os.path.basename(script_path)}")
    print(f"   Videos: {os.path.basename(csv_videos)}")
    if csv_sentimiento:
        print(f"   Sentimiento: {os.path.basename(csv_sentimiento)}")
    print("-" * 60)

    try:
        result = subprocess.run(cmd, check=True)
        print("\n✅ Informe HTML generado exitosamente.")
        print("   Abre el archivo HTML en tu navegador para ver las gráficas multidimensionales.")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Error al generar el informe: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
