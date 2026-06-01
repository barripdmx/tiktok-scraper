# -*- coding: utf-8 -*-
"""
taxonomia_ia.py — Taxonomía cerrada para el análisis multidimensional del Punto 6.

Centraliza las listas de valores válidos (enums) que el modelo de lenguaje debe
usar y la detección de ruido/homónimos del scraping. Ajusta estas listas por
proyecto sin tocar el pipeline (src/analysis/analizar_sentimiento.py).

Dimensiones (además del POS/NEG/NEU clásico):
  - bias        : sesgo político del autor del comentario
  - archetype   : arquetipo conductual (taxonomía psicográfica)
  - intent      : intención de acción detectada
  - pain_point  : frustración/dolor expresado
  - sarcasm     : booleano (ironía/burla)
  - noise       : booleano (sticker, solo-emoji u homónimo no relacionado)
"""

import re

# ─── Enums cerrados ──────────────────────────────────────────────────────────

SENTIMIENTOS = ["POS", "NEG", "NEU"]

SESGOS = ["conservador", "progresista", "neutro", "mixto", "no_inferible"]

INTENCIONES = ["compra", "info", "difusion", "castigo", "ninguna"]

# Arquetipos conductuales (psicografía). Nombre interno → descripción para el prompt.
ARQUETIPOS = {
    "testigo_indignado":    "indignación moral, comparte la noticia como prueba",
    "reactor_bajo_senal":   "solo emoji/risas/aplausos, sin argumento explícito",
    "meme_fiscal":          "convierte el tema en burla castigadora (memes)",
    "moralista_punitivo":   "pide sanción, cárcel, dimisión o vergüenza pública",
    "amplificador":         "apoya a un narrador/figura percibida como valiente",
    "redirector_partidista":"desvía el foco hacia el bando contrario",
    "defensor_esceptico":   "defiende por presunción de inocencia / lawfare / falta de pruebas",
    "igualador_antisistema":"rechaza a ambos bandos, 'todos iguales'",
    "expansor_conspirativo":"expande hacia teorías conspirativas",
    "buscador_contexto":    "pide cronología, pruebas o explicación de los hechos",
    "otro":                 "no encaja en los anteriores",
}

# Pain points (frustraciones). Nombre interno → descripción para el prompt.
PAIN_POINTS = {
    "doble_rasero_fiscal":     "percepción de que la élite no rinde cuentas como el ciudadano",
    "fatiga_corrupcion":       "cansancio por corrupción política en cadena",
    "judicializacion_selectiva":"miedo a persecución política/mediático-judicial",
    "microeconomia":           "preocupación por el bolsillo (precios, sueldos)",
    "perdida_terreno_cultural":"temor a perder la batalla cultural",
    "sobreproduccion_falsedad":"percepción de marketing vacío / contenido artificial",
    "ninguno":                 "no expresa un dolor concreto",
    "otro":                    "expresa un dolor no listado",
}

# ─── Detección de ruido / homónimos ──────────────────────────────────────────

# Tokens que delatan contaminación del scraping (homónimos no relacionados con el
# tema). Amplía esta lista por proyecto. Se comparan en minúsculas como palabra.
RUIDO_HOMONIMOS = [
    "plus ultra", "plusultra", "mha", "my hero", "myheroacademia",
    "boku no hero", "deku", "allmight", "all might", "bakugo", "todoroki",
    "anime", "manga", "mathe", "zp10", "nrw", "examen aleman", "klausur",
]

# Marcadores de sticker / contenido vacío
_MARCADORES_STICKER = ["[sticker]", "[gif]", "[imagen]", "[emoji]"]

# Caracteres "con contenido": letras y dígitos (incluye acentos y ñ/ü).
_RE_CONTENIDO = re.compile(r"[0-9A-Za-zÁÉÍÓÚÜÑáéíóúüñ]")


def es_ruido(texto) -> bool:
    """True si el comentario es ruido (sticker, solo-emoji u homónimo no relacionado).

    Permite saltarse la llamada al LLM para estos comentarios (ahorra tokens) y
    evita que inflen artificialmente el porcentaje 'neutro' del análisis.
    """
    if texto is None:
        return True
    t = str(texto).strip().lower()
    if not t:
        return True
    if any(m in t for m in _MARCADORES_STICKER):
        return True
    # Sin ninguna letra ni dígito → solo emojis/puntuación/stickers
    if not _RE_CONTENIDO.search(t):
        return True
    # Homónimos: el token aparece delimitado por límites de palabra
    for h in RUIDO_HOMONIMOS:
        if re.search(r"(?<![\w])" + re.escape(h) + r"(?![\w])", t):
            return True
    return False


def descripcion_arquetipos() -> str:
    """Lista formateada de arquetipos para inyectar en el prompt."""
    return "\n".join(f"  - {k}: {v}" for k, v in ARQUETIPOS.items())


def descripcion_pain_points() -> str:
    """Lista formateada de pain points para inyectar en el prompt."""
    return "\n".join(f"  - {k}: {v}" for k, v in PAIN_POINTS.items())
