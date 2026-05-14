#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
run_scraper.py — Launcher amigable para ejecutar el scraper de comentarios
===========================================================================
Uso:
  python run_scraper.py                    # Menú interactivo
  python run_scraper.py data/videos.csv    # Procesa CSV específico
  python run_scraper.py --help             # Muestra opciones
"""

import os
import sys
import asyncio
import importlib.util

script_path = os.path.join(os.path.dirname(__file__), "src", "scrapers", "2_tiktok_scraper_comentarios_api.py")


def load_scraper():
    """Carga dinámicamente el módulo del scraper"""
    spec = importlib.util.spec_from_file_location("scraper_module", script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def list_csv_files() -> list:
    """Lista archivos CSV disponibles en data/"""
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    if not os.path.exists(data_dir):
        return []
    return [
        f for f in os.listdir(data_dir)
        if f.endswith(".csv") and not f.endswith("_comentarios_api.csv")
    ]


def main():
    print("\n" + "=" * 70)
    print("TikTok Comment Scraper Launcher")
    print("=" * 70)

    if len(sys.argv) > 1:
        if sys.argv[1] in ("--help", "-h"):
            print("\nUSO:")
            print("  python run_scraper.py                    # Menú interactivo")
            print("  python run_scraper.py data/videos.csv    # Procesa CSV")
            print("  python run_scraper.py --list             # Lista CSVs disponibles")
            print("\nOPCIONES avanzadas:")
            print("  --count N         Procesa N videos")
            print("  --limit N         Máx N comentarios por video")
            print("  --skip-checkpoint Ignora checkpoint anterior")
            print("=" * 70 + "\n")
            return
        elif sys.argv[1] == "--list":
            csvs = list_csv_files()
            if not csvs:
                print("\n❌ No se encontraron archivos CSV en data/")
                return
            print("\nArchivos CSV disponibles:")
            for i, csv_file in enumerate(csvs, 1):
                path = os.path.join("data", csv_file)
                print(f"  {i}. {csv_file}")
            print()
            return

    scraper = load_scraper()
    asyncio.run(scraper.main())


if __name__ == "__main__":
    main()
