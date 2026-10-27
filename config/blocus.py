"""Cuentas del lote Blocus descartadas por falso positivo.

Entraron al lote solo porque su nombre contiene «blocus» (búsqueda de usuarios), pero su contenido
no tiene relación con las convocatorias: @blocus328 parece una comunidad haitiana (criollo haitiano,
publicaciones de oct 2025 a may 2026), @luccca93 publica memes de CapCut en un contexto catalán y @blocus75000
publica vídeos sin relación con el movimiento (fitness, baño, menciones a medios de EE. UU.).
Las gráficas las excluyen y lo indican en una nota.
"""

FALSOS_POSITIVOS = ("blocus328", "luccca93", "blocus75000")
DUDOSAS = ("blocusscpmofrancia",)  # una foto sin texto y 3 seguidores: no se puede juzgar; se mantiene
NOTA_FALSOS_POSITIVOS = "Excluidas por falso positivo (solo comparten el nombre «blocus»): " + ", ".join(
    "@" + c for c in FALSOS_POSITIVOS) + ". Dudosa, se mantiene: " + ", ".join("@" + c for c in DUDOSAS) + "."
