# -*- coding: utf-8 -*-
"""Informe forense: detecta el tipo de CSV y señala los casos anómalos plantados."""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src", "analysis")))
import informe_forense as inf  # noqa: E402


def _hallazgos(df, fn):
    rep = inf.Informe("t", len(df))
    fn(df, rep)
    return {t for _, t, _, _ in rep.hallazgos}


def test_comentarios_detecta_copypasta_y_cuenta_anterior():
    filas = [{"comment_id": str(i), "video_id": "1", "autor_handle": f"u{i}", "autor_uid": str(i),
              "texto": "texto copiado en bloque por varios", "likes": "0",
              "comment_fecha_utc": "2026-01-01 10:00:00", "autor_fecha_creacion_cuenta": "2020-01-01 00:00:00"}
             for i in range(4)]
    filas.append({**filas[0], "comment_id": "9", "autor_uid": "9", "texto": "otro",
                  "autor_fecha_creacion_cuenta": "2027-01-01 00:00:00"})
    df = pd.DataFrame(filas)
    assert inf.detectar_tipo(df) == "comentarios"
    h = _hallazgos(df, inf.analizar_comentarios)
    assert "Mismo texto desde cuentas distintas" in h
    assert "Comentario anterior a la creación de la cuenta" in h


def test_publicaciones_detecta_retirado_y_programado():
    df = pd.DataFrame([{"video_id": "1", "video_vistas": "100", "video_likes": "5", "retirado": "true",
                        "desfase_subida_seg": "200000", "video_fecha_utc": "2026-01-01 10:00:00"},
                       {"video_id": "2", "video_vistas": "100", "video_likes": "5", "retirado": "0",
                        "desfase_subida_seg": "5", "video_fecha_utc": "2026-01-02 10:00:00"}])
    assert inf.detectar_tipo(df) == "publicaciones"
    h = _hallazgos(df, inf.analizar_publicaciones)
    assert "Moderación: retirados, prohibidos o en revisión" in h
    assert "Publicados mucho después de crearse el vídeo" in h


def test_columnas_ausentes_no_rompen():
    assert _hallazgos(pd.DataFrame({"video_vistas": ["1"]}), inf.analizar_publicaciones) == set()
