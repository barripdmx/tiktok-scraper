# -*- coding: utf-8 -*-
"""
tests/test_pipeline.py — Pruebas de las funciones del pipeline de datos que
históricamente han causado bugs (merge de enriquecimiento, parseo de lotes LLM,
checkpoints, clasificación de errores y escáner de proyecto del menú).

Ejecutar:  pytest tests/test_pipeline.py -v
"""

import json
import os
import sys

import pytest

pd = pytest.importorskip("pandas")

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for p in (ROOT, os.path.join(ROOT, "src", "utils")):
    if p not in sys.path:
        sys.path.insert(0, p)


# ===========================================================================
# FUN-04 — merge de enriquecimiento: colisiones de columnas y lookup legacy
# ===========================================================================

import enriquecer_csv_fechas_creacion as enr  # noqa: E402


def _lookup_completo():
    return pd.DataFrame({
        "username_consulta": ["ana", "ben"],
        "username_real": ["ana", "ben"],
        "fecha_creacion_cuenta": ["01-01-2020", "02-02-2021"],
        "fuente_fecha_creacion": ["createTime", "createTime"],
        "user_id": ["111", "222"], "sec_uid": ["s1", "s2"],
        "verified": ["No", "No"], "followers": [1000, 2000],
        "following": [1, 2], "likes": [50, 90], "video_count": [3, 4],
        "error": ["", ""],
    })


class TestMergeEnriquecimiento:
    def test_colisiones_se_renombran_a_cuenta(self, tmp_path):
        # CSV fuente con columnas que colisionan con el lookup (likes del
        # comentario, followers preexistente). No deben generar _x/_y.
        src = tmp_path / "proj_videos_comentarios_api.csv"
        pd.DataFrame({
            "autor_handle": ["@ana", "@ben"], "texto": ["hola", "adios"],
            "likes": [5, 9], "followers": [100, 200],
        }).to_csv(src, index=False, encoding="utf-8-sig")

        out = enr.merge_lookup_into_source(
            str(src), "autor_handle", _lookup_completo(), str(tmp_path / "out.csv"))
        cols = list(pd.read_csv(out, encoding="utf-8-sig").columns)

        assert "likes" in cols and "likes_cuenta" in cols
        assert "followers" in cols and "followers_cuenta" in cols
        assert not any(c.endswith(("_x", "_y")) for c in cols)
        assert "fecha_creacion_cuenta" in cols

    def test_no_duplica_filas_del_source(self, tmp_path):
        src = tmp_path / "p_videos_comentarios_api.csv"
        pd.DataFrame({"autor_handle": ["@ana", "@ben", "@ana"],
                      "texto": ["a", "b", "c"]}).to_csv(
            src, index=False, encoding="utf-8-sig")
        out = enr.merge_lookup_into_source(
            str(src), "autor_handle", _lookup_completo(), str(tmp_path / "o.csv"))
        assert len(pd.read_csv(out, encoding="utf-8-sig")) == 3  # mismas filas

    def test_lookup_legacy_sin_columnas_no_crashea(self, tmp_path):
        # Lookup antiguo sin 'error'/'sec_uid'/'video_count' no debe dar KeyError.
        src = tmp_path / "p_videos_comentarios_api.csv"
        pd.DataFrame({"autor_handle": ["@ana"], "texto": ["hi"]}).to_csv(
            src, index=False, encoding="utf-8-sig")
        legacy = pd.DataFrame({
            "username_consulta": ["ana"], "username_real": ["ana"],
            "fecha_creacion_cuenta": ["01-01-2020"],
            "fuente_fecha_creacion": ["createTime"], "user_id": ["111"],
            "verified": ["No"], "followers": [10], "following": [1], "likes": [5],
        })
        out = enr.merge_lookup_into_source(
            str(src), "autor_handle", legacy, str(tmp_path / "o.csv"))
        cols = list(pd.read_csv(out, encoding="utf-8-sig").columns)
        assert "fecha_creacion_cuenta" in cols


# ===========================================================================
# FUN-06 — clasificación de cuentas resueltas (transitorio vs permanente)
# ===========================================================================

class TestCuentasResueltas:
    def test_transitorio_reintentable_permanente_cacheado(self):
        df = pd.DataFrame({
            "username_consulta": ["ok", "perm", "trans", "vacio"],
            "error": ["", "HTTP 404 Not Found", "timeout", None],
        })
        r = enr._cuentas_resueltas(df)
        assert {"ok", "perm", "vacio"} <= r      # resueltos
        assert "trans" not in r                  # transitorio → reintentar

    def test_lookup_sin_columna_error(self):
        df = pd.DataFrame({"username_consulta": ["a", "b"]})
        assert enr._cuentas_resueltas(df) == {"a", "b"}

    def test_lookup_vacio(self):
        assert enr._cuentas_resueltas(pd.DataFrame()) == set()


# ===========================================================================
# FUN-07 — parseo de la respuesta del LLM (índices 1-based, huecos, wrappers)
# ===========================================================================

sent = pytest.importorskip("src.analysis.analizar_sentimiento",
                           reason="requiere tkinter/dotenv/taxonomia_ia")


class TestParsearRespuesta:
    def test_1_based_se_realinea(self):
        resp = json.dumps({"resultados": [
            {"index": 1, "sentiment": "POS"},
            {"index": 2, "sentiment": "NEG"},
            {"index": 3, "sentiment": "NEU"}]})
        objs = sent._parsear_respuesta(resp, 3)
        assert [o["sentiment"] for o in objs] == ["POS", "NEG", "NEU"]

    def test_0_based_intacto(self):
        resp = json.dumps([
            {"index": 0, "sentiment": "POS"},
            {"index": 1, "sentiment": "NEG"},
            {"index": 2, "sentiment": "NEU"}])
        objs = sent._parsear_respuesta(resp, 3)
        assert [o["sentiment"] for o in objs] == ["POS", "NEG", "NEU"]

    def test_huecos_usan_defecto(self):
        # Solo llega el índice 0; el resto queda con el objeto por defecto (NEU).
        resp = json.dumps({"resultados": [{"index": 0, "sentiment": "NEG"}]})
        objs = sent._parsear_respuesta(resp, 3)
        assert objs[0]["sentiment"] == "NEG"
        assert objs[1]["sentiment"] == "NEU" and objs[2]["sentiment"] == "NEU"

    def test_valores_fuera_de_enum_se_normalizan(self):
        resp = json.dumps({"resultados": [{"index": 0, "sentiment": "INVENTADO"}]})
        objs = sent._parsear_respuesta(resp, 1)
        assert objs[0]["sentiment"] == "NEU"

    def test_json_invalido_lanza(self):
        # JSON no parseable → lanza para que el llamante reintente.
        with pytest.raises((ValueError, json.JSONDecodeError)):
            sent._parsear_respuesta("esto no es json", 2)

    def test_dict_sin_resultados_degrada_a_defecto(self):
        # JSON válido pero sin la clave esperada → n objetos por defecto (NEU),
        # sin romper el lote.
        objs = sent._parsear_respuesta('{"foo": 1}', 2)
        assert len(objs) == 2 and all(o["sentiment"] == "NEU" for o in objs)


# ===========================================================================
# REL-04 — claves vectorizadas idénticas a clave_estable (compat. checkpoints)
# ===========================================================================

class TestClavesVectorizadas:
    def test_identicas_a_clave_estable(self):
        df = pd.DataFrame({
            "comment_id": ["123", "", None, "456", float("nan"), "789"],
            "texto": ["hola", "mundo", "foo", "bar", float("nan"), "baz"],
        })
        for cid in ("comment_id", None):
            vect = sent.calcular_claves(df, cid, "texto")
            ref = [sent.clave_estable(df.iloc[i].to_dict(), cid, "texto")
                   for i in range(len(df))]
            assert vect == ref, f"claves divergen con col_id={cid}"


# ===========================================================================
# FUN-05 — checkpoint del sentimiento: round-trip atómico y tolerancia a corrupción
# ===========================================================================

class TestCheckpoint:
    def test_roundtrip(self, tmp_path):
        ckpt = str(tmp_path / "c_checkpoint.json")
        data = {"abc": {"sentiment": "POS", "bias": "neutro"}}
        sent.save_checkpoint(ckpt, data)
        assert sent.load_checkpoint(ckpt) == data
        assert not os.path.exists(ckpt + ".tmp")  # temporal limpiado

    def test_corrupto_no_aborta_y_respaldado(self, tmp_path):
        ckpt = tmp_path / "c_checkpoint.json"
        ckpt.write_text("{ esto no es json valido", encoding="utf-8")
        assert sent.load_checkpoint(str(ckpt)) == {}      # no lanza
        # el corrupto se renombra a _corrupt_*.json (no se pierde silenciosamente)
        respaldos = list(tmp_path.glob("c_checkpoint_corrupt_*.json"))
        assert len(respaldos) == 1

    def test_inexistente_devuelve_vacio(self, tmp_path):
        assert sent.load_checkpoint(str(tmp_path / "no_existe.json")) == {}


# ===========================================================================
# FUN-11 — escáner de proyecto del menú: preferencia de proveedor de sentimiento
# ===========================================================================

ctk = pytest.importorskip("customtkinter", reason="menu requiere customtkinter")
import menu  # noqa: E402


class TestScanProyecto:
    def _crear_proyecto(self, d):
        base = "proj_videos_api"
        archivos = [
            f"{base}.csv",
            f"{base}_comentarios_api.csv",
            f"{base}_comentarios_api_con_sentimiento_roberta.csv",
            f"{base}_comentarios_api_con_sentimiento_groq.csv",
            f"{base}_comentarios_api_enriquecido_fechas_creacion.csv",
            f"{base}_comentarios_api_lookup_fechas_creacion.csv",  # debe ignorarse
        ]
        for a in archivos:
            (d / a).write_text("x", encoding="utf-8")
        (d / f"{base}_checkpoint.json").write_text("{}", encoding="utf-8")

    def test_prefiere_groq_sobre_roberta(self, tmp_path):
        self._crear_proyecto(tmp_path)
        res = menu.scan_project_files(str(tmp_path))
        assert "groq" in os.path.basename(res["sentiment"])
        assert "roberta" not in os.path.basename(res["sentiment"])

    def test_clasifica_y_ignora_auxiliares(self, tmp_path):
        self._crear_proyecto(tmp_path)
        res = menu.scan_project_files(str(tmp_path))
        assert res["videos"].endswith("proj_videos_api.csv")
        assert "comentarios_api" in os.path.basename(res["comments"])
        assert "enriquecido" in os.path.basename(res["enriched"])
        # lookup y checkpoint no deben aparecer como ninguno de los tipos
        assert "lookup" not in json.dumps(res)

    def test_sentiment_priority_orden(self):
        p = lambda name: menu._match_score(name, menu.SENTIMENT_PROVIDERS)
        assert p("x_groq.csv") > p("x_roberta.csv") > p("x.csv")


# ===========================================================================
# FUN-12 — captura de hashtag: fusión incremental (no perder vídeos al recapturar)
# ===========================================================================

pytest.importorskip("playwright", reason="scraper de hashtag requiere playwright")

import importlib.util as _ilu  # noqa: E402

_hastag_spec = _ilu.spec_from_file_location(
    "hastag_api_module", os.path.join(ROOT, "src", "scrapers", "2_tiktok_scraper_hastag_api.py")
)
hastag = _ilu.module_from_spec(_hastag_spec)
_hastag_spec.loader.exec_module(hastag)


class TestSaveResultsFusion:
    def _row(self, video_id, desc):
        return {
            "video_id": video_id, "video_url": f"https://x/{video_id}", "video_desc": desc,
            "video_fecha": "2026-01-01", "video_duracion_seg": 10, "video_width": 720,
            "video_height": 1280, "video_likes": 1, "video_vistas": 1, "video_compartidos": 0,
            "video_comentarios": 0, "video_guardados": 0, "username": "u", "author_nickname": "u",
            "author_verified": False, "music_title": "", "music_author": "", "hashtags": "",
        }

    def test_recaptura_no_pierde_videos_antiguos(self, tmp_path, monkeypatch):
        monkeypatch.setattr(hastag, "dataset_dir", lambda label: str(tmp_path))

        hastag.save_results("proy", [self._row("v1", "primero"), self._row("v2", "segundo")])
        # Recaptura posterior: la búsqueda de TikTok solo devuelve v2 (editado) y v3 (nuevo)
        info = hastag.save_results("proy", [self._row("v2", "segundo-editado"), self._row("v3", "tercero")])

        assert info["total"] == 3
        assert info["nuevos"] == 1

        with open(tmp_path / "proy_videos_api.json", encoding="utf-8") as f:
            data = json.load(f)
        ids = {r["video_id"] for r in data}
        assert ids == {"v1", "v2", "v3"}
        assert next(r for r in data if r["video_id"] == "v2")["video_desc"] == "segundo-editado"


# ===========================================================================
# FUN-13 — nubes de comentarios: reutiliza el sentimiento ya calculado
# ===========================================================================

ac = pytest.importorskip("src.analysis.analitica_comentarios",
                          reason="requiere wordcloud/tkinter/emoji")


class TestCargarSentimientoPrecalculado:
    def _df_comentarios(self):
        return pd.DataFrame({
            "comment_id": ["c1", "c2", "c3"],
            "texto": ["a", "b", "c"],
        })

    def test_sin_csv_de_sentimiento_devuelve_none(self, tmp_path):
        csv_file = str(tmp_path / "proy_comentarios_api.csv")
        assert ac._cargar_sentimiento_precalculado(csv_file, self._df_comentarios()) is None

    def test_reutiliza_groq_sobre_roberta_y_mapea_etiquetas(self, tmp_path):
        base = tmp_path / "proy_comentarios_api"
        # Si existen ambos, debe preferir groq (más rico) sobre roberta.
        pd.DataFrame({"comment_id": ["c1", "c2", "c3"],
                      "sentiment": ["POS", "NEG", "NEU"]}).to_csv(
            f"{base}_con_sentimiento_roberta.csv", index=False)
        pd.DataFrame({"comment_id": ["c1", "c2", "c3"],
                      "sentiment": ["NEG", "NEG", "POS"]}).to_csv(
            f"{base}_con_sentimiento_groq.csv", index=False)

        out = ac._cargar_sentimiento_precalculado(f"{base}.csv", self._df_comentarios())

        assert out is not None
        assert list(out["sentimiento"]) == ["negativo", "negativo", "positivo"]

    def test_comentario_sin_sentimiento_cae_a_neutro(self, tmp_path):
        base = tmp_path / "proy_comentarios_api"
        pd.DataFrame({"comment_id": ["c1"], "sentiment": ["POS"]}).to_csv(
            f"{base}_con_sentimiento_groq.csv", index=False)

        out = ac._cargar_sentimiento_precalculado(f"{base}.csv", self._df_comentarios())

        assert list(out["sentimiento"]) == ["positivo", "neutro", "neutro"]
