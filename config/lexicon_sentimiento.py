# -*- coding: utf-8 -*-
"""
lexicon_sentimiento.py — Lexicon compartido de sentimiento en español.

Importar desde cualquier módulo de análisis:
    import sys, os
    _BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    sys.path.insert(0, _BASE)
    from config.lexicon_sentimiento import (
        PALABRAS_POSITIVAS, PALABRAS_NEGATIVAS,
        EMOJIS_POSITIVOS, EMOJIS_NEGATIVOS,
        clasificar_lexico,
    )

Nota: solo usar este lexicon como referencia exploratoria o como
fallback de último recurso. Para análisis riguroso, preferir
pysentimiento (RoBERTa local) o cualquier proveedor LLM.
"""

PALABRAS_POSITIVAS = [
    'gracias', 'bien', 'buen', 'buena', 'genial', 'excelente', 'increíble',
    'maravilloso', 'amo', 'me encanta', 'perfecto', 'guay', 'chulo', 'mola',
    'crack', 'jajaja', 'jejeje', 'grande', 'top', 'el mejor', 'la mejor',
    'ayuda', 'solución', 'rápido', 'eficiente', 'barato', 'económico', 'calidad',
    'brutal', 'guapo', 'guapa',
]

PALABRAS_NEGATIVAS = [
    'asco', 'odio', 'mierda', 'puta', 'puto', 'joder', 'no funciona', 'lento',
    'caro', 'estafa', 'engaño', 'problema', 'error', 'fallo', 'basura',
    'ladrones', 'robo', 'nunca más', 'pésimo', 'horrible', 'decepción',
    'malo', 'mala', 'vergüenza', 'incompetente', 'desastre', 'harto', 'harta',
    'queja', 'reclamación',
]

EMOJIS_POSITIVOS = "😂🤣❤😍😊😁👍✅👏🔥♥️🤩✨💯✔️🥰😘"
EMOJIS_NEGATIVOS = "😡😠😤🤬😒🙄😭🤦🤦‍♂️🤦‍♀️👎🤮💩"


def clasificar_lexico(texto: str) -> str:
    """Clasificador simple basado en lexicon (solo para uso exploratorio).
    Devuelve 'positivo', 'negativo' o 'neutro'.
    """
    t = str(texto).lower()
    pos = sum(1 for w in PALABRAS_POSITIVAS if w in t)
    neg = sum(1 for w in PALABRAS_NEGATIVAS if w in t)
    pos += sum(1 for c in t if c in EMOJIS_POSITIVOS)
    neg += sum(1 for c in t if c in EMOJIS_NEGATIVOS)
    if pos > neg:
        return "positivo"
    if neg > pos:
        return "negativo"
    return "neutro"
