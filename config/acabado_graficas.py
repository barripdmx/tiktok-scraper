"""Acabado común de las gráficas Blocus, aplicado en cada savefig (se instala al importar config.blocus).

1. Los textos de título, subtítulo, notas y títulos de panel empiezan por mayúscula.
2. Todo el contenido (textos, logo, firma y gráficas con sus ejes) queda al menos un 5 % dentro de cada borde.
3. Título y subtítulo no se pisan entre sí ni con el logo; los pies no se pisan entre sí, con la firma ni con la gráfica:
   si chocan, la letra baja de tamaño o la gráfica se reduce.
4. Una leyenda que toca el pie, otra leyenda o los datos del panel se coloca encima del panel, a la derecha,
   fuera de la zona de datos.
"""

import re
import textwrap

from matplotlib.figure import Figure
from matplotlib.legend import Legend
from matplotlib.text import Text
from matplotlib.transforms import Bbox

MARGEN = 0.052  # (un poco más del 5 % para que el redondeo a píxeles nunca lo deje por debajo)
HUECO = 0.006  # separación mínima entre elementos
Y_PIE = 0.13  # los textos pequeños por debajo de esta altura son pies
LETRA_MIN = 6.5
_original = Figure.savefig


def _mayuscula(s):
    """Primera letra en mayúscula; no toca @usuarios ni #hashtags al principio."""
    m = re.match(r"^([^\w@#]*)([^\W\d_])", s)
    return s[:m.end(2) - 1] + s[m.end(2) - 1].upper() + s[m.end(2):] if m else s


def _es_pie(t):
    return t.get_fontsize() <= 9 and t.get_position()[1] < Y_PIE and t.get_ha() != "right" and t.get_text().strip()


def _es_firma(t):
    return t.get_ha() == "right" and t.get_text().startswith("@") and t.get_position()[1] < Y_PIE


def _caja(artista, fig, r):
    return artista.get_window_extent(r).transformed(fig.transFigure.inverted())


def _solapa(a, b, margen=0.0):
    return a.x0 < b.x1 - margen and b.x0 < a.x1 - margen and a.y0 < b.y1 - margen and b.y0 < a.y1 - margen


def _mover(a, dx, dy):
    if isinstance(a, Text):
        x, y = a.get_position()
        a.set_position((x + dx, y + dy))


def _relleno_blanco(a):
    """Fracción de marco blanco (izquierda, derecha, arriba, abajo) de la imagen del logo."""
    import numpy as np
    g = np.asarray(a.offsetbox.get_data()).astype(float)
    g = g[..., :3].mean(axis=2) if g.ndim == 3 else g
    g = g / 255 if g.max() > 1 else g
    ys, xs = np.where(g < 0.96)
    if not len(xs):
        return 0, 0, 0, 0
    h, w = g.shape
    return xs.min() / w, 1 - (xs.max() + 1) / w, ys.min() / h, 1 - (ys.max() + 1) / h


def _logos_visibles(fig, r):
    """Caja de la parte visible de cada logo, en fracción de figura."""
    cajas = []
    for a in (a for a in fig.artists if hasattr(a, "xybox")):
        bb = _caja(a, fig, r)
        pl, pr, pa, pb = _relleno_blanco(a)
        cajas.append(Bbox.from_extents(bb.x0 + pl * bb.width, bb.y0 + pb * bb.height, bb.x1 - pr * bb.width, bb.y1 - pa * bb.height))
    return cajas


def _logo_dentro(a, fig, r):
    """El logo (AnnotationBbox centrado en xybox) se coloca en una posición absoluta: su parte visible respeta el margen."""
    bb = _caja(a, fig, r)
    cx, cy = a.xybox
    w, h = bb.width, bb.height
    pl, pr, pa, pb = _relleno_blanco(a)
    nx = min(max(cx, MARGEN - pl * w + w / 2), 1 - MARGEN + pr * w - w / 2)
    ny = min(max(cy, MARGEN - pb * h + h / 2), 1 - MARGEN + pa * h - h / 2)
    a.xy = a.xybox = (nx, ny)


def _ajustar_ancho(t, fig, r, limite):
    """Un texto alineado a la izquierda que sobrepasa el límite derecho: baja la letra y, si no basta, lo parte en dos líneas."""
    while t.get_fontsize() > LETRA_MIN and _caja(t, fig, r).x1 > limite:
        t.set_fontsize(t.get_fontsize() - 0.25)
    if _caja(t, fig, r).x1 > limite and "\n" not in t.get_text():
        txt = t.get_text()
        t.set_text(textwrap.fill(txt, max(20, int(len(txt) * (limite - _caja(t, fig, r).x0) / (_caja(t, fig, r).width or 1)))))


def _margenes_de_la_figura(fig, r):
    """Mete en el margen los textos y el logo de la figura (no los de dentro de las gráficas)."""
    for a in (a for a in fig.artists if hasattr(a, "xybox")):
        _logo_dentro(a, fig, r)
    for a in (t for t in fig.texts if t.get_text().strip()):
        bb = _caja(a, fig, r)
        dx = MARGEN - bb.x0 if bb.x0 < MARGEN else min(0.0, (1 - MARGEN) - bb.x1)
        dy = (1 - MARGEN) - bb.y1 if bb.y1 > 1 - MARGEN else max(0.0, MARGEN - bb.y0)
        if isinstance(a, Text) and _es_pie(a):
            dy = 0.0  # los pies suben después, en orden, para no cambiar cuál va encima
        if dx or dy:
            _mover(a, dx, dy)
        if isinstance(a, Text) and a.get_ha() != "right" and _caja(a, fig, r).x1 > 1 - MARGEN:
            _ajustar_ancho(a, fig, r, 1 - MARGEN)


def _leyendas_de_la_figura(fig, r):
    """Las leyendas de la figura (fig.legend) también respetan el margen: se desplazan hacia dentro."""
    for leg in fig.legends:
        bb = _caja(leg, fig, r)
        dx = MARGEN - bb.x0 if bb.x0 < MARGEN else min(0.0, (1 - MARGEN) - bb.x1)
        dy = MARGEN - bb.y0 if bb.y0 < MARGEN else min(0.0, (1 - MARGEN) - bb.y1)
        if dx or dy:
            a = leg.get_bbox_to_anchor().transformed(fig.transFigure.inverted())
            leg.set_bbox_to_anchor((a.x0 + dx, a.y0 + dy))


def _cabecera(fig, r):
    """Título y subtítulo se apilan hacia abajo sin pisarse, y no tocan el logo. Devuelve el borde inferior de la cabecera."""
    textos = sorted((t for t in fig.texts if t.get_position()[1] > 0.8 and t.get_text().strip() and not _es_firma(t)),
                    key=lambda t: -_caja(t, fig, r).y1)
    logos = [_caja(a, fig, r) for a in fig.artists if hasattr(a, "xybox")]
    limite = 1 - MARGEN
    for t in textos:
        bb = _caja(t, fig, r)
        if bb.y1 > limite:
            _mover(t, 0, limite - bb.y1)
        while t.get_fontsize() > 11 and any(_solapa(_caja(t, fig, r), lg) for lg in logos):
            t.set_fontsize(t.get_fontsize() - 0.5)
        limite = _caja(t, fig, r).y0 - HUECO
    return limite


def _pies(fig, r):
    """Pies: no se pisan entre sí, ni llegan a la firma, y quedan por encima del margen inferior. Devuelve su borde superior."""
    pies = [t for t in fig.texts if _es_pie(t)]
    firma = [Bbox.from_extents(b.x0 - 0.012, b.y0 - 0.004, b.x1, b.y1 + 0.004) for b in (_caja(t, fig, r) for t in fig.texts if _es_firma(t))]

    def apilar():
        techo = MARGEN - HUECO
        for t in sorted(pies, key=lambda t: _caja(t, fig, r).y0):
            bb = _caja(t, fig, r)
            if bb.y0 < techo + HUECO:
                _mover(t, 0, techo + HUECO - bb.y0)
                bb = _caja(t, fig, r)
            techo = max(techo, bb.y1)
        return techo

    apilar()
    for t in pies:  # un pie que llega a la firma: baja la letra y, si no basta, se parte en líneas
        for f in firma:
            if _solapa(_caja(t, fig, r), f):
                _ajustar_ancho(t, fig, r, f.x0)
    return apilar()


def _encajar_graficas(fig, r, base, tope):
    logos = _logos_visibles(fig, r)
    """Cada gráfica, con sus ejes y rótulos, cabe entre los márgenes, por encima de los pies y por debajo de la cabecera."""
    for _ in range(2):
        for ax in fig.axes:
            if not ax.get_visible():
                continue
            bb = ax.get_tightbbox(r).transformed(fig.transFigure.inverted())
            p = ax.get_position()
            x0, y0, w, h = p.x0, p.y0, p.width, p.height
            if bb.x0 < MARGEN:
                x0, w = x0 + MARGEN - bb.x0, w - (MARGEN - bb.x0)
            if bb.x1 > 1 - MARGEN:
                w -= bb.x1 - (1 - MARGEN)
            if bb.y0 < base + HUECO:
                y0, h = y0 + base + HUECO - bb.y0, h - (base + HUECO - bb.y0)
            tope_ax = min([tope] + [lg.y0 - HUECO for lg in logos if bb.x0 < lg.x1 and lg.x0 < bb.x1 and bb.y0 < lg.y0])  # no tapar el logo
            if bb.y1 > tope_ax:
                h -= bb.y1 - tope_ax
            if (x0, y0, w, h) != (p.x0, p.y0, p.width, p.height):
                ax.set_position([x0, y0, max(w, 0.1), max(h, 0.2)])


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
            leg.remove()
            ax.legend(h, e, loc="lower right", bbox_to_anchor=(1.0, 1.01), ncol=min(len(h), 4) or 1, frameon=False, fontsize=8.5,
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
    _margenes_de_la_figura(fig, r)
    _leyendas_de_la_figura(fig, r)
    tope = min(_cabecera(fig, r), 1 - MARGEN)
    techo_pies = _pies(fig, r)
    _encajar_graficas(fig, r, techo_pies, tope)
    _leyendas(fig, r, techo_pies)


def _savefig(self, *args, **kw):
    if self.axes or self.texts:
        acabar(self)
    return _original(self, *args, **kw)


def instalar():
    if Figure.savefig is not _savefig:
        Figure.savefig = _savefig
