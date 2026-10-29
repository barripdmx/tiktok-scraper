"""Acabado común de las gráficas Blocus, aplicado en cada savefig (se instala al importar config.blocus).

1. Los textos de título, subtítulo, notas y títulos de panel empiezan por mayúscula.
2. Los pies (textos pequeños al fondo) no se pisan entre sí ni con la gráfica: si chocan, se apilan hacia arriba y la
   gráfica se reduce por abajo hasta que quepan.
3. Una leyenda que toca el pie, otra leyenda o los datos del panel se coloca encima del panel, a la derecha,
   fuera de la zona de datos.
"""

import re

from matplotlib.figure import Figure
from matplotlib.legend import Legend
from matplotlib.transforms import Bbox

HUECO = 0.006  # separación mínima en fracción de figura
Y_PIE = 0.13  # los textos pequeños por debajo de esta altura son pies
_original = Figure.savefig


def _mayuscula(s):
    """Primera letra en mayúscula; no toca @usuarios ni #hashtags al principio."""
    m = re.match(r"^([^\w@#]*)([^\W\d_])", s)
    return s[:m.end(2) - 1] + s[m.end(2) - 1].upper() + s[m.end(2):] if m else s


def _es_pie(t):
    return t.get_fontsize() <= 9 and t.get_position()[1] < Y_PIE and t.get_ha() != "right" and t.get_text().strip()


def _caja(artista, fig, r):
    bb = artista.get_window_extent(r)
    return bb.transformed(fig.transFigure.inverted())


def _solapa(a, b, margen=0.0):
    return a.x0 < b.x1 - margen and b.x0 < a.x1 - margen and a.y0 < b.y1 - margen and b.y0 < a.y1 - margen


def _pies_sin_pisarse(fig, r):
    pies = sorted((t for t in fig.texts if _es_pie(t)), key=lambda t: _caja(t, fig, r).y0)
    firma = [Bbox.from_extents(b.x0 - 0.012, b.y0 - 0.004, b.x1, b.y1 + 0.004) for b in (_caja(t, fig, r) for t in fig.texts if t.get_ha() == "right" and t.get_text().startswith("@") and t.get_position()[1] < Y_PIE)]
    for t in pies:  # un pie largo no debe llegar a la firma: se reduce la letra hasta que quepa
        while t.get_fontsize() > 6.5 and any(_solapa(_caja(t, fig, r), f, 0.0) for f in firma):
            t.set_fontsize(t.get_fontsize() - 0.25)
    techo = 0.0
    for t in pies:
        bb = _caja(t, fig, r)
        if bb.y0 < techo + HUECO and techo:
            t.set_y(t.get_position()[1] + (techo + HUECO - bb.y0))
            bb = _caja(t, fig, r)
        techo = max(techo, bb.y1)
    return techo


def _reducir_graficas(fig, r, techo_pies):
    if not techo_pies:
        return
    for ax in fig.axes:
        if not ax.get_visible():
            continue
        bb = ax.get_tightbbox(r).transformed(fig.transFigure.inverted())
        falta = techo_pies + HUECO - bb.y0
        if falta > 0 and bb.y0 < Y_PIE + 0.05:
            p = ax.get_position()
            ax.set_position([p.x0, p.y0 + falta, p.width, max(p.height - falta, 0.2)])


def _datos_del_panel(ax, fig, r):
    cajas = []
    for a in list(ax.patches) + list(ax.lines) + list(ax.collections) + list(ax.texts):
        if isinstance(a, Legend) or not a.get_visible():
            continue
        try:
            bb = a.get_window_extent(r)
        except Exception:
            continue
        if bb.width > 0 and bb.height > 0 and bb.width < 0.95 * fig.bbox.width:
            cajas.append(bb.transformed(fig.transFigure.inverted()))
    return cajas


def _leyendas(fig, r, techo_pies):
    for ax in fig.axes:
        leg = ax.get_legend()
        if leg is None or not leg.get_visible():
            continue
        bb = _caja(leg, fig, r)
        molesta = bb.y0 < techo_pies + HUECO or any(_solapa(bb, d, 0.002) for d in _datos_del_panel(ax, fig, r))
        molesta = molesta or any(_solapa(bb, _caja(o, fig, r)) for o in fig.axes if o is not ax and o.get_legend() is not None
                                 and o.get_legend() is not leg)
        if molesta:
            h, e = ax.get_legend_handles_labels()
            ncol = min(len(h), 4) or 1
            leg.remove()
            ax.legend(h, e, loc="lower right", bbox_to_anchor=(1.0, 1.01), ncol=ncol, frameon=False, fontsize=8.5,
                      borderaxespad=0)


def acabar(fig):
    for t in fig.texts:
        if t.get_text() and not t.get_text().startswith("@"):
            t.set_text(_mayuscula(t.get_text()))
    for ax in fig.axes:
        for lugar in ("left", "center", "right"):
            s = ax.get_title(loc=lugar)
            if s:
                ax.set_title(_mayuscula(s), loc=lugar, fontsize=ax.title.get_fontsize(), fontweight=ax.title.get_fontweight())
    r = fig.canvas.get_renderer()
    techo = _pies_sin_pisarse(fig, r)
    _reducir_graficas(fig, r, techo)
    _leyendas(fig, r, techo)


def _savefig(self, *args, **kw):
    if self.axes or self.texts:
        acabar(self)
    return _original(self, *args, **kw)


def instalar():
    if Figure.savefig is not _savefig:
        Figure.savefig = _savefig
