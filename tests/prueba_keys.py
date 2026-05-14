import os
import sys
from dotenv import load_dotenv

# Configuración de rutas
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CONFIG_DIR = os.path.join(BASE_DIR, "config")
load_dotenv(os.path.join(CONFIG_DIR, ".env"))

# Añadir src/analysis o donde esté gemini_pool
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src", "analysis")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src", "utils")))

from gemini_pool import GeminiPool

pool = GeminiPool(
    keys=[
        {"api_key": os.getenv("GEMINI_KEY_1"), "label": "cuenta1"},
        {"api_key": os.getenv("GEMINI_KEY_2"), "label": "cuenta2"},
        {"api_key": os.getenv("GEMINI_KEY_3"), "label": "cuenta3"},
    ],
    free_tier=True,
)

response = pool.generate("Dime el nombre de la capital de Francia en una palabra")
print(response.text)
print(pool.cost_summary())