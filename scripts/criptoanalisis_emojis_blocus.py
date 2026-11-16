"""Análisis criptográfico/estadístico de los comentarios de «combinación atípica de emojis» de @teamblocus.

Busca: (1) canales ocultos (variation selectors, ZWJ, tags, espacios de ancho cero), (2) si los emojis siguen
un reparto uniforme sobre un repertorio grande (generación aleatoria) o uno humano, (3) estructura interna
(orden, pares y tríos repetidos), (4) mensajes codificados (índice de coincidencia con varias asignaciones),
(5) coherencia de metadatos (ID del comentario frente a su fecha).
Todo con pruebas de permutación o Monte Carlo reproducibles (semilla fija).
"""

import math
import random
import re
import statistics
from collections import Counter
from datetime import datetime, timezone
from itertools import combinations

from scripts.analisis_emojis_blocus import cargar, resumen

SEMILLA = 20261028
FUENTE = re.compile(
    "(?:[\U0001F1E6-\U0001F1FF]{2}|[\U0001F000-\U0001F1E5\U0001F200-\U0001FAFF☀-➿⬀-⯿"
    "←-⇿⌀-⏿■-◿‼⁉™ℹ〰〽㊗㊙])"
    "️?(?:‍[\U0001F000-\U0001FAFF☀-➿⬀-⯿←-⇿]️?)*")
OCULTOS = {0x200B, 0x200C, 0x200D, 0x2060, 0xFEFF, 0x00AD, 0x2061, 0x2062, 0x2063, 0x2064}


def tokens(texto):
    """Emojis como unidades (las secuencias con ZWJ cuentan como uno) y sin selector de variación."""
    return [t.replace("️", "") for t in FUENTE.findall(re.sub("[\U0001F3FB-\U0001F3FF]", "", texto))]


def canales_ocultos(filas):
    c = Counter()
    for r in filas:
        grupo = "atípicos" if r.get("atipico") else ("@teamblocus otros" if r["cuenta_publicadora"] == "teamblocus" else "resto")
        for ch in r["texto"]:
            o = ord(ch)
            if o in OCULTOS or 0xFE00 <= o <= 0xFE0F or 0xE0000 <= o <= 0xE007F or 0xE0100 <= o <= 0xE01EF:
                c[(grupo, f"U+{o:04X}")] += 1
    return c


def espectro(apar):
    n, d = sum(apar.values()), len(apar)
    f1 = sum(v == 1 for v in apar.values())
    f2 = sum(v == 2 for v in apar.values())
    return n, d, f1, f2, d + f1 * f1 / (2 * f2)


def simular_uniforme(n_draws, N, rng):
    c = Counter(rng.randrange(N) for _ in range(n_draws))
    return len(c), sum(v == 1 for v in c.values()), sum(v == 2 for v in c.values()), max(c.values())


def ajustar_N(n, d, f1, rng, reps=200):
    """Tamaño de repertorio uniforme cuyo nº de distintos y de singletons se parece más al observado."""
    mejor = None
    for N in range(500, 4001, 50):
        sim = [simular_uniforme(n, N, rng) for _ in range(reps)]
        e = abs(statistics.mean(s[0] for s in sim) - d) / d + abs(statistics.mean(s[1] for s in sim) - f1) / f1
        if mejor is None or e < mejor[1]:
            mejor = (N, e, statistics.mean(s[3] for s in sim))
    return mejor


def spearman(a, b):
    def rangos(x):
        orden = sorted(range(len(x)), key=lambda i: x[i])
        r = [0] * len(x)
        for k, i in enumerate(orden):
            r[i] = k
        return r
    ra, rb = rangos(a), rangos(b)
    ma, mb = statistics.mean(ra), statistics.mean(rb)
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    return num / math.sqrt(sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb))


def indice_coincidencia(seq, k):
    c = Counter(seq)
    n = len(seq)
    return sum(v * (v - 1) for v in c.values()) / (n * (n - 1)), 1 / k


def main():
    rng = random.Random(SEMILLA)
    filas, _ = cargar()
    foco, resto = resumen(filas)
    at = sorted((r for r in foco if r["atipico"]), key=lambda r: r["creado_utc"])
    out = {}

    print("== 1. Canales ocultos (todo el corpus)")
    for (g, cp), v in sorted(canales_ocultos(filas).items()):
        print(f"  {g:18s} {cp}: {v}")

    seqs = [tokens(r["texto"]) for r in at]
    apar = Counter(e for s in seqs for e in s)
    n, d, f1, f2, chao = espectro(apar)
    print(f"\n== 2. Espectro: {n} apariciones, {d} distintos, {f1} una vez, {f2} dos veces, Chao1 ~ {chao:.0f}")
    N, err, max_esp = ajustar_N(n, d, f1, rng)
    print(f"   repertorio uniforme equivalente N ~ {N}; frecuencia máxima esperada ~ {max_esp:.1f}; observada {max(apar.values())} "
          f"({apar.most_common(1)[0][0]})")
    print("   más frecuentes:", apar.most_common(8))
    habit = Counter(e for r in resto for e in tokens(r["texto"]))
    comunes = [e for e in apar if habit[e]]
    rho = spearman([apar[e] for e in comunes], [habit[e] for e in comunes])
    print(f"   Spearman uso en atípicos vs uso habitual (emojis en ambos, n={len(comunes)}): {rho:+.3f}")
    top_h = [e for e, _ in habit.most_common(10)]
    print(f"   los 10 emojis más usados por humanos aparecen {sum(apar[e] for e in top_h)} de {n} veces ({100 * sum(apar[e] for e in top_h) / n:.1f} %); "
          f"en el uso habitual: {100 * sum(habit[e] for e in top_h) / sum(habit.values()):.1f} %")

    print("\n== 3. Estructura interna")
    asc = sum(s == sorted(s, key=lambda e: ord(e[0])) for s in seqs)
    esperado = sum(1 / math.factorial(len(s)) for s in seqs)
    sd = math.sqrt(sum((1 / math.factorial(len(s))) * (1 - 1 / math.factorial(len(s))) for s in seqs))
    print(f"   comentarios con emojis en orden creciente de código: {asc} (esperado al azar {esperado:.1f} ± {sd:.1f})")
    pares = Counter(frozenset(p) for s in seqs for p in combinations(s, 2))
    trios = Counter(frozenset(p) for s in seqs for p in combinations(s, 3))
    rep_p = sum(v > 1 for v in pares.values())
    sims = []
    for _ in range(300):
        c = Counter()
        for s in seqs:
            ch = rng.sample(range(N), len(s))
            for p in combinations(ch, 2):
                c[frozenset(p)] += 1
        sims.append(sum(v > 1 for v in c.values()))
    print(f"   pares de emojis repetidos entre comentarios: {rep_p} (esperado al azar {statistics.mean(sims):.1f} ± {statistics.pstdev(sims):.1f}); "
          f"tríos repetidos: {sum(v > 1 for v in trios.values())}")

    print("\n== 4. Mensaje codificado (índice de coincidencia; azar = 1/k, texto natural ≈ 0,066 con k=26)")
    flujo_t = [e for s in seqs for e in s]
    flujo_p = [s[0] for s in seqs]
    for nombre, flujo in (("flujo completo (orden temporal)", flujo_t), ("primer emoji de cada comentario", flujo_p)):
        for k in (26, 27, 32, 64, 128, 256):
            ic, azar = indice_coincidencia([ord(e[0]) % k for e in flujo], k)
            print(f"   {nombre:34s} mod {k:3d}: IC={ic:.4f} (azar {azar:.4f})")
    bits = [ord(e[0]) & 1 for e in flujo_t]
    print(f"   bit de menor peso del código: {sum(bits)}/{len(bits)} unos ({100 * sum(bits) / len(bits):.1f} %)")
    asc_ = [ord(e[0]) & 0x7F for e in flujo_t]
    imprim = sum(32 <= x < 127 for x in asc_)
    print(f"   código & 0x7F imprimible ASCII: {imprim}/{len(asc_)} ({100 * imprim / len(asc_):.1f} %; azar 74,2 %)")

    print("\n== 5. Metadatos")
    desfase = []
    for r in at:
        t_id = datetime.fromtimestamp(int(r["comment_id"]) >> 32, timezone.utc)
        t_c = datetime.fromisoformat(r["creado_utc"])
        desfase.append((t_c - t_id).total_seconds())
    print(f"   |fecha del comentario - fecha del ID|: mediana {statistics.median(abs(x) for x in desfase):.0f} s, máx {max(abs(x) for x in desfase):.0f} s")
    horas = Counter(datetime.fromisoformat(r["creado_utc"]).hour for r in at)
    esperado_h = len(at) / 24
    chi = sum((horas[h] - esperado_h) ** 2 / esperado_h for h in range(24))
    print(f"   distribución por hora UTC: chi² vs uniforme = {chi:.1f} (gl 23; p 0,05 ≈ 35,2)")
    nombres = re.compile(r"^[a-z.]+\d{1,3}$")
    f_at = sum(bool(nombres.match(r["autor_handle"])) for r in at) / len(at)
    f_ot = sum(bool(nombres.match(r["autor_handle"])) for r in foco if not r["atipico"]) / max(1, sum(not r["atipico"] for r in foco))
    f_rs = sum(bool(nombres.match(r["autor_handle"])) for r in resto) / len(resto)
    print(f"   usuarios con forma «letras + 1-3 dígitos»: atípicos {100 * f_at:.0f} %, otros de @teamblocus {100 * f_ot:.0f} %, resto {100 * f_rs:.0f} %")


if __name__ == "__main__":
    main()
