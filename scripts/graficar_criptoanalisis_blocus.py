"""Gráfica 11: los emojis atípicos frente a uso humano y frente a un reparto uniforme (control criptoanalítico)."""

import random
import statistics
from collections import Counter

from matplotlib.patches import Patch

from scripts.analisis_emojis_blocus import cargar, resumen
from scripts.criptoanalisis_emojis_blocus import SEMILLA, ajustar_N, simular_uniforme, tokens
from scripts.estilo_presentacion_blocus import AZUL, CLARO, ROJO, guardar, limpiar, nueva


def medidas(c):
    return len(c), sum(v == 1 for v in c.values()), max(c.values())


def main():
    rng = random.Random(SEMILLA)
    filas, _ = cargar()
    foco, resto = resumen(filas)
    observado = Counter(e for r in foco if r["atipico"] for e in tokens(r["texto"]))
    n = sum(observado.values())
    comunes = {e for e, _ in Counter(e for r in resto for e in tokens(r["texto"])).most_common(15)}
    humano = [e for r in resto for e in tokens(r["texto"]) if e not in comunes]
    N = ajustar_N(n, len(observado), medidas(observado)[1], rng)[0]
    sim_h = [medidas(Counter(rng.sample(humano, n))) for _ in range(200)]
    sim_u = [simular_uniforme(n, N, rng) for _ in range(200)]
    grupos = [("emojis de los comentarios atípicos", medidas(observado), ROJO),
              (f"{n} emojis al azar del uso humano\n(sin los 15 más usados)", tuple(statistics.mean(x[i] for x in sim_h) for i in (0, 1, 2)), CLARO),
              (f"{n} emojis al azar, reparto uniforme\nsobre ~{N} emojis", (sim_u and statistics.mean(x[0] for x in sim_u),
               statistics.mean(x[1] for x in sim_u), statistics.mean(x[3] for x in sim_u)), AZUL)]
    fig, axes = nueva("¿se eligieron los emojis como lo haría una persona?",
                      "emojis distintos, emojis que aparecen una sola vez y frecuencia del emoji más repetido, con "
                      f"{n} apariciones en cada caso",
                      "Control: se retiran de los atípicos y del uso humano los 15 emojis más frecuentes. Reparto uniforme: "
                      "simulación Monte Carlo (200 repeticiones, semilla fija). Compatible con elección aleatoria; no prueba "
                      "quién o qué la generó.", columnas=3, gridspec_kw={"wspace": 0.3})
    for ax, i, titulo in zip(axes, range(3), ("emojis distintos", "aparecen una sola vez", "frecuencia máxima de un emoji")):
        for k, (nombre, m, color) in enumerate(grupos):
            ax.bar(k, m[i], color=color)
            ax.text(k, m[i] + max(g[1][i] for g in grupos) * 0.02, f"{m[i]:.0f}", ha="center", fontsize=11, fontweight="bold")
        ax.set_xticks(range(3), ["atípicos", "uso humano", "uniforme"], fontsize=9)
        ax.set_title(titulo, loc="left", fontsize=11, fontweight="bold")
        limpiar(ax)
    axes[0].legend(handles=[Patch(color=g[2], label=g[0].replace(chr(10), " ")) for g in grupos], loc="upper left",
                   bbox_to_anchor=(0, -0.08), frameon=False, fontsize=8.5)
    guardar(fig, "11_control_criptoanalitico.png")


if __name__ == "__main__":
    main()
