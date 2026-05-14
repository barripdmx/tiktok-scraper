#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ejemplo_uso_programatico.py — Cómo usar el scraper desde Python
================================================================
Importa el scraper como módulo y lo ejecuta programáticamente.

Útil para:
  • Integrar en pipelines de análisis
  • Procesar múltiples CSVs
  • Análisis condicionales
"""

import os
import sys
import asyncio
import importlib.util

BASE_DIR = os.path.dirname(__file__)


def cargar_scraper():
    """Carga el módulo del scraper"""
    path = os.path.join(BASE_DIR, "src", "scrapers", "2_tiktok_scraper_comentarios_api.py")
    spec = importlib.util.spec_from_file_location("scraper", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def ejemplo_1_test_rapido():
    """Ejemplo 1: Test rápido de 3 videos"""
    print("\n" + "=" * 70)
    print("EJEMPLO 1: Test rápido (3 videos)")
    print("=" * 70)

    scraper = cargar_scraper()

    csv_path = "data/usuarios.csv"
    if not os.path.exists(csv_path):
        print(f"❌ {csv_path} no existe")
        return

    sys.argv = ["script", csv_path, "--count", "3", "--limit", "100"]
    await scraper.main()


async def ejemplo_2_procesamiento_completo():
    """Ejemplo 2: Procesar todos los videos sin límite"""
    print("\n" + "=" * 70)
    print("EJEMPLO 2: Procesamiento completo")
    print("=" * 70)

    scraper = cargar_scraper()

    csv_path = "data/usuarios.csv"
    if not os.path.exists(csv_path):
        print(f"❌ {csv_path} no existe")
        return

    sys.argv = ["script", csv_path]
    await scraper.main()


async def ejemplo_3_multiples_csvs():
    """Ejemplo 3: Procesar múltiples CSVs secuencialmente"""
    print("\n" + "=" * 70)
    print("EJEMPLO 3: Procesar múltiples CSVs")
    print("=" * 70)

    scraper = cargar_scraper()
    data_dir = os.path.join(BASE_DIR, "data")

    csvs = [
        f for f in os.listdir(data_dir)
        if f.endswith(".csv") and not f.endswith("_comentarios_api.csv")
    ]

    if not csvs:
        print("❌ No hay CSVs para procesar")
        return

    print(f"\n📂 Encontrados {len(csvs)} CSV(s)")

    for i, csv_file in enumerate(csvs, 1):
        csv_path = os.path.join(data_dir, csv_file)
        print(f"\n[{i}/{len(csvs)}] Procesando {csv_file}...")

        sys.argv = ["script", csv_path, "--count", "10"]
        try:
            await scraper.main()
        except Exception as e:
            print(f"❌ Error en {csv_file}: {e}")
            continue


def main():
    print("""
╔════════════════════════════════════════════════════════════════════════════╗
║              EJEMPLOS DE USO PROGRAMÁTICO DEL SCRAPER                      ║
╚════════════════════════════════════════════════════════════════════════════╝

Ejecuta los ejemplos así:

  # Ejemplo 1: Test rápido (3 videos)
  python ejemplo_uso_programatico.py 1

  # Ejemplo 2: Procesamiento completo
  python ejemplo_uso_programatico.py 2

  # Ejemplo 3: Múltiples CSVs
  python ejemplo_uso_programatico.py 3

═══════════════════════════════════════════════════════════════════════════════
""")

    if len(sys.argv) < 2:
        print("❌ Debes especificar un ejemplo (1, 2 o 3)")
        return

    ejemplo = sys.argv[1]

    if ejemplo == "1":
        asyncio.run(ejemplo_1_test_rapido())
    elif ejemplo == "2":
        asyncio.run(ejemplo_2_procesamiento_completo())
    elif ejemplo == "3":
        asyncio.run(ejemplo_3_multiples_csvs())
    else:
        print(f"❌ Ejemplo inválido: {ejemplo}")


if __name__ == "__main__":
    main()
