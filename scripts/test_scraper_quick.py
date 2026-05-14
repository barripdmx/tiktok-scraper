#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
test_scraper_quick.py — Test rápido del scraper (3-5 videos)
===============================================================
Ejecuta: python test_scraper_quick.py [CSV] [--limit 50]

Ideal para validar que el scraper funciona sin procesar cientos de videos.
"""

import os
import sys
import asyncio

BASE_DIR = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(BASE_DIR, "src", "scrapers"))

import importlib.util

script_path = os.path.join(BASE_DIR, "src", "scrapers", "2_tiktok_scraper_comentarios_api.py")

spec = importlib.util.spec_from_file_location("scraper_module", script_path)
scraper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scraper)


def main():
    print("\n" + "=" * 70)
    print("TikTok Comment Scraper — TEST RÁPIDO (3-5 videos)")
    print("=" * 70)
    print("\nUSO:")
    print("  python test_scraper_quick.py data/videos.csv")
    print("  python test_scraper_quick.py data/videos.csv --limit 100")
    print("=" * 70 + "\n")

    csv_path = None
    limit = 50

    if len(sys.argv) > 1:
        csv_path = sys.argv[1]
        if "--limit" in sys.argv:
            try:
                idx = sys.argv.index("--limit")
                limit = int(sys.argv[idx + 1])
            except:
                pass

    if csv_path is None:
        print("❌ Debes especificar un CSV: python test_scraper_quick.py data/videos.csv")
        return

    if not os.path.exists(csv_path):
        print(f"❌ No existe: {csv_path}")
        print(f"\nCSVs disponibles en data/:")
        data_dir = os.path.join(BASE_DIR, "data")
        for f in os.listdir(data_dir):
            if f.endswith(".csv") and not f.endswith("_comentarios_api.csv"):
                print(f"  • {f}")
        return

    print(f"📂 CSV: {csv_path}")
    print(f"⚙️  Config: 5 videos max, límite {limit} comentarios/video")
    print()

    sys.argv = ["test_scraper_quick.py", csv_path, "--count", "5", "--limit", str(limit)]

    asyncio.run(scraper.main())


if __name__ == "__main__":
    main()
