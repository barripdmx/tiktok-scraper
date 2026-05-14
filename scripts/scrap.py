#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
scrap.py — Alias corto para ejecutar el scraper desde el panel
==============================================================
Uso ultra-simple:
  python scrap.py                           # Diálogo interactivo
  python scrap.py data/usuarios.csv         # Procesa CSV
  python scrap.py data/usuarios.csv 50      # 50 videos
  python scrap.py data/usuarios.csv 50 100  # 50 videos, máx 100 comentarios
"""

import sys
import os
import asyncio
import importlib.util

BASE_DIR = os.path.dirname(__file__)
SCRAPER = os.path.join(BASE_DIR, "2_tiktok_scraper_comentarios_api.py")

spec = importlib.util.spec_from_file_location("scraper", SCRAPER)
scraper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scraper)

if __name__ == "__main__":
    asyncio.run(scraper.main())
