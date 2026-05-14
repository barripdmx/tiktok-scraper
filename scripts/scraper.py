#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
scraper.py — Ejecutor simplificado del scraper de comentarios
==============================================================
Uso más simple y directo.

Ejemplos:
  python scraper.py                                # Diálogo interactivo
  python scraper.py data/usuarios.csv              # Procesa CSV
  python scraper.py data/usuarios.csv 10           # Procesa 10 videos
  python scraper.py data/usuarios.csv 10 100       # 10 videos, máx 100 comentarios
  python scraper.py --test data/usuarios.csv       # Test rápido (5 videos)
  python scraper.py --help                         # Muestra ayuda
"""

import os
import sys
import asyncio
import importlib.util

BASE_DIR = os.path.dirname(__file__)
SCRAPER_PATH = os.path.join(BASE_DIR, "src", "scrapers", "2_tiktok_scraper_comentarios_api.py")


def load_scraper_module():
    """Carga el módulo del scraper dinámicamente"""
    spec = importlib.util.spec_from_file_location("scraper_module", SCRAPER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def print_help():
    """Imprime ayuda"""
    print("""
╔════════════════════════════════════════════════════════════════════════════╗
║                    TikTok Comment Scraper v2                              ║
║                    SCRAPER DE COMENTARIOS REFACTORIZADO                   ║
╚════════════════════════════════════════════════════════════════════════════╝

OPCIONES DE USO:
════════════════════════════════════════════════════════════════════════════

  1️⃣  python scraper.py
      → Abre diálogo interactivo (pregunta CSV, count, limit)

  2️⃣  python scraper.py data/videos.csv
      → Procesa el CSV especificado (diálogo para count/limit)

  3️⃣  python scraper.py data/videos.csv 10 100
      → Procesa 10 videos, máx 100 comentarios cada uno

  4️⃣  python scraper.py --test data/videos.csv
      → Test rápido: 5 videos, máx 50 comentarios (validación)

  5️⃣  python scraper.py --help
      → Muestra esta ayuda

EJEMPLOS REALES:
════════════════════════════════════════════════════════════════════════════

  # Test rápido para validar que funciona
  python scraper.py --test data/usuarios.csv

  # Procesar 50 videos
  python scraper.py data/usuarios.csv 50

  # Procesar 100 videos, máx 200 comentarios cada uno
  python scraper.py data/usuarios.csv 100 200

  # Procesar todos (diálogo interactivo para count/limit)
  python scraper.py data/usuarios.csv

SALIDA:
════════════════════════════════════════════════════════════════════════════

  ✅ CSV:     data/{nombre}_comentarios_api.csv
  📊 Resumen: videos procesados, comentarios totales, cobertura %
  📝 Log:     data/logs/comentarios_api_[fecha].log

NOTA:
════════════════════════════════════════════════════════════════════════════
  • Requiere sesión guardada (1-guardar_sesion.py)
  • Detecta automáticamente checkpoint anterior
  • Puede continuar ejecuciones incompletas

════════════════════════════════════════════════════════════════════════════
""")


def main():
    if len(sys.argv) == 1:
        print_help()
        scraper = load_scraper_module()
        asyncio.run(scraper.main())
        return

    arg1 = sys.argv[1]

    if arg1 in ("--help", "-h", "help"):
        print_help()
        return

    if arg1 == "--test":
        if len(sys.argv) < 3:
            print("❌ --test requiere un CSV: python scraper.py --test data/videos.csv")
            return
        csv_path = sys.argv[2]
        if not os.path.exists(csv_path):
            print(f"❌ No existe: {csv_path}")
            return
        print("\n🧪 TEST RÁPIDO: 5 videos, máx 50 comentarios")
        sys.argv = ["scraper.py", csv_path, "--count", "5", "--limit", "50"]
        scraper = load_scraper_module()
        asyncio.run(scraper.main())
        return

    csv_path = arg1
    if not os.path.exists(csv_path):
        print(f"❌ No existe: {csv_path}")
        print("\nArchivos CSV disponibles:")
        data_dir = os.path.join(BASE_DIR, "data")
        if os.path.exists(data_dir):
            for f in sorted(os.listdir(data_dir)):
                if f.endswith(".csv") and not f.endswith("_comentarios_api.csv"):
                    print(f"  • {f}")
        return

    count = None
    limit = None

    if len(sys.argv) >= 3:
        try:
            count = int(sys.argv[2])
        except ValueError:
            print(f"❌ Argumento inválido '{sys.argv[2]}', debe ser un número")
            return

    if len(sys.argv) >= 4:
        try:
            limit = int(sys.argv[3])
        except ValueError:
            print(f"❌ Argumento inválido '{sys.argv[3]}', debe ser un número")
            return

    args = ["scraper.py", csv_path]
    if count:
        args.extend(["--count", str(count)])
    if limit:
        args.extend(["--limit", str(limit)])

    sys.argv = args
    scraper = load_scraper_module()
    asyncio.run(scraper.main())


if __name__ == "__main__":
    main()
