"""Cuentas del lote Blocus descartadas por falso positivo.

Entraron al lote solo porque su nombre contiene «blocus» (búsqueda de usuarios), pero su contenido
no tiene relación con las convocatorias: @blocus328 parece una comunidad haitiana (criollo haitiano,
publicaciones de oct 2025 a may 2026) y @luccca93 publica memes de CapCut en un contexto catalán.
Las gráficas las excluyen y lo indican en una nota.
"""

FALSOS_POSITIVOS = ("blocus328", "luccca93")
NOTA_FALSOS_POSITIVOS = "Excluidas por falso positivo (solo comparten el nombre «blocus»): " + ", ".join(
    "@" + c for c in FALSOS_POSITIVOS) + "."
