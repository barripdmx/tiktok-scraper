"""Acabado común de las gráficas Blocus: mayúscula inicial, pies que no pisan la gráfica y leyendas fuera de los datos."""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from config.acabado_graficas import _caja, _mayuscula, acabar


def test_mayuscula_inicial():
    assert _mayuscula("cuentas") == "Cuentas"
    assert _mayuscula("¿qué? sí") == "¿Qué? sí"
    assert _mayuscula("@blocus") == "@blocus"
    assert _mayuscula("#tag") == "#tag"
    assert _mayuscula("12 cuentas") == "12 cuentas"


def test_pie_no_pisa_la_grafica_y_se_capitaliza():
    fig, ax = plt.subplots(figsize=(16, 9))
    fig.subplots_adjust(bottom=0.05)  # el eje llega hasta abajo: choca con el pie
    ax.bar([0, 1], [3, 5], label="serie")
    ax.legend(loc="lower right")  # tapa las barras
    ax.set_title("título de panel", loc="left")
    pie = fig.text(0.04, 0.02, "pie de página", fontsize=8.5)
    fig.canvas.draw()
    acabar(fig)
    r = fig.canvas.get_renderer()
    assert pie.get_text() == "Pie de página" and ax.get_title(loc="left") == "Título de panel"
    assert ax.get_tightbbox(r).transformed(fig.transFigure.inverted()).y0 >= _caja(pie, fig, r).y1
    leg = _caja(ax.get_legend(), fig, r)
    assert leg.y0 >= _caja(pie, fig, r).y1  # la leyenda tampoco toca el pie
    plt.close(fig)


def test_margen_en_blanco_del_5_por_ciento():
    fig, ax = plt.subplots(figsize=(16, 9))
    fig.subplots_adjust(left=0.02, right=0.99, top=0.9, bottom=0.04)
    ax.bar([0, 1], [3, 5])
    fig.text(0.04, 0.96, "título", fontsize=17, fontweight="bold")
    fig.text(0.04, 0.9, "subtítulo largo " * 6, fontsize=10.5)
    fig.text(0.04, 0.01, "pie muy largo " * 18, fontsize=8.5)
    fig.text(0.985, 0.005, "@barripdmx", ha="right", fontsize=8)
    fig.canvas.draw()
    acabar(fig)
    r = fig.canvas.get_renderer()
    cajas = [_caja(t, fig, r) for t in fig.texts] + [ax.get_tightbbox(r).transformed(fig.transFigure.inverted())]
    for bb in cajas:
        assert bb.x0 >= 0.05 - 1e-3 and bb.y0 >= 0.05 - 1e-3 and bb.x1 <= 0.95 + 1e-3 and bb.y1 <= 0.95 + 1e-3, bb
    plt.close(fig)
