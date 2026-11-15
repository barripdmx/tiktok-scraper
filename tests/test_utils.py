# -*- coding: utf-8 -*-
"""
tests/test_utils.py — Pruebas unitarias de tiktok_utils.py
Ejecutar: pytest tests/test_utils.py -v
"""

import re
import sys
import os
from datetime import datetime

# Asegurar que el directorio src/utils esté en el path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src", "utils")))

from tiktok_utils import (
    parse_count,
    extract_video_id_from_url,
    extract_username_from_url,
    is_valid_video_url,
    is_in_date_range,
    is_likely_in_date_range,
    get_date_from_video_id,
)

# ---------------------------------------------------------------------------
# parse_count
# ---------------------------------------------------------------------------

class TestParseCount:
    def test_million(self):
        assert parse_count("1.2M") == 1_200_000

    def test_kilo(self):
        assert parse_count("500K") == 500_000

    def test_kilo_decimal(self):
        assert parse_count("1.5K") == 1_500

    def test_plain_integer(self):
        assert parse_count("1234") == 1234

    def test_comma_thousands(self):
        # "1,234" — la coma se convierte a punto; extrae dígitos limpios
        assert parse_count("1,234") == 1234

    def test_empty_string(self):
        assert parse_count("") == 0

    def test_none(self):
        assert parse_count(None) == 0

    def test_case_insensitive(self):
        assert parse_count("2m") == 2_000_000

    def test_whitespace(self):
        assert parse_count("  300K  ") == 300_000


# ---------------------------------------------------------------------------
# extract_video_id_from_url
# ---------------------------------------------------------------------------

class TestExtractVideoId:
    def test_standard_url(self):
        url = "https://www.tiktok.com/@user/video/7123456789012345678"
        assert extract_video_id_from_url(url) == "7123456789012345678"

    def test_url_with_query(self):
        url = "https://www.tiktok.com/@user/video/7123456789012345678?is_from_webapp=1"
        # URL with query — extract_video_id works on path before split
        assert extract_video_id_from_url(url) == "7123456789012345678"

    def test_no_video_segment(self):
        assert extract_video_id_from_url("https://www.tiktok.com/@user") == ""

    def test_empty_string(self):
        assert extract_video_id_from_url("") == ""

    def test_none(self):
        assert extract_video_id_from_url(None) == ""


# ---------------------------------------------------------------------------
# extract_username_from_url
# ---------------------------------------------------------------------------

class TestExtractUsername:
    def test_standard_url(self):
        url = "https://www.tiktok.com/@sanchezcastejon/video/7123456789012345678"
        assert extract_username_from_url(url) == "sanchezcastejon"

    def test_no_at_sign(self):
        assert extract_username_from_url("https://www.tiktok.com/tag/python") == ""


# ---------------------------------------------------------------------------
# is_valid_video_url
# ---------------------------------------------------------------------------

class TestIsValidVideoUrl:
    def test_valid(self):
        assert is_valid_video_url("https://www.tiktok.com/@user/video/7123456789012345678") is True

    def test_too_short_id(self):
        # ID menor de 15 dígitos → inválido
        assert is_valid_video_url("https://www.tiktok.com/@user/video/12345") is False

    def test_no_video_path(self):
        assert is_valid_video_url("https://www.tiktok.com/@user") is False

    def test_empty(self):
        assert is_valid_video_url("") is False

    def test_none(self):
        assert is_valid_video_url(None) is False

    def test_non_numeric_id(self):
        assert is_valid_video_url("https://www.tiktok.com/@user/video/abcdefghijklmnop") is False


# ---------------------------------------------------------------------------
# is_in_date_range
# ---------------------------------------------------------------------------

# ID real cuya fecha aproximada es 2025-01-15 (obtenido con id >> 32)
# 7456302222222222222 >> 32 ≈ 2025-01-15 (estimado)
# Usamos un ID generado con timestamp conocido:
# datetime(2025,3,1).timestamp() = 1740787200
# id = 1740787200 << 32 = 7477553324327272448
_ID_2025_03_01 = str(1740787200 << 32)


class TestIsInDateRange:
    def test_no_range_always_true(self):
        assert is_in_date_range(_ID_2025_03_01, None, None) is True

    def test_in_range(self):
        start = datetime(2025, 2, 1)
        end = datetime(2025, 4, 1)
        assert is_in_date_range(_ID_2025_03_01, start, end) is True

    def test_before_range(self):
        start = datetime(2025, 4, 1)
        end = datetime(2025, 6, 1)
        assert is_in_date_range(_ID_2025_03_01, start, end) is False

    def test_after_range(self):
        start = datetime(2024, 1, 1)
        end = datetime(2024, 12, 31)
        assert is_in_date_range(_ID_2025_03_01, start, end) is False

    def test_only_start(self):
        assert is_in_date_range(_ID_2025_03_01, datetime(2025, 2, 1), None) is True

    def test_only_end(self):
        assert is_in_date_range(_ID_2025_03_01, None, datetime(2025, 4, 1)) is True

    def test_only_start_too_late(self):
        assert is_in_date_range(_ID_2025_03_01, datetime(2025, 5, 1), None) is False


# ---------------------------------------------------------------------------
# is_likely_in_date_range (margen)
# ---------------------------------------------------------------------------

class TestIsLikelyInDateRange:
    def test_within_margin(self):
        # El ID es exactamente 2025-03-01; pedimos desde 2025-03-04 con margen 5 días → debe pasar
        assert is_likely_in_date_range(_ID_2025_03_01, datetime(2025, 3, 4), None, margin_days=5) is True

    def test_outside_margin(self):
        # Pedimos desde 2025-04-01 con margen 2 días → el ID (2025-03-01) está fuera
        assert is_likely_in_date_range(_ID_2025_03_01, datetime(2025, 4, 1), None, margin_days=2) is False

    def test_no_range(self):
        assert is_likely_in_date_range(_ID_2025_03_01, None, None) is True


# ---------------------------------------------------------------------------
# Regresión: split_hashtags — bug del doble backslash (\\s vs \s)
# ---------------------------------------------------------------------------

class TestSplitHashtagsRegression:
    """
    Regresión para A-03 de analitica_redes.py:
    `re.split(r"[|,\\s]+", ...)` usaba \\s literal en vez de \\s regex.
    La corrección usa r"[|,\\s]+" que sí reconoce espacios y tabulaciones.
    """
    PATTERN = r"[|,\s]+"

    def test_pipe_separator(self):
        assert re.split(self.PATTERN, "python|tiktok|viral") == ["python", "tiktok", "viral"]

    def test_comma_separator(self):
        assert re.split(self.PATTERN, "python,tiktok,viral") == ["python", "tiktok", "viral"]

    def test_space_separator(self):
        result = re.split(self.PATTERN, "python tiktok viral")
        assert result == ["python", "tiktok", "viral"]

    def test_mixed(self):
        result = re.split(self.PATTERN, "python|tiktok, viral")
        assert "python" in result and "tiktok" in result and "viral" in result

    def test_wrong_pattern_doesnt_split_on_space(self):
        """Confirma que el patrón con \\\\s literal NO divide en espacios (el bug original)."""
        wrong_pattern = r"[|,\\s]+"
        result = re.split(wrong_pattern, "python tiktok viral")
        # Con el patrón erróneo, el espacio NO actúa como separador
        assert result == ["python tiktok viral"]


def test_metadatos_ampliados():
    from tiktok_utils import metadatos_ampliados, COLUMNAS_AMPLIADAS
    item = {"locationCreated": "FR", "IsAigc": False, "penaltyContext": {"status": 102, "reviewed": "0"},
            "poi": {"name": "Torre Eiffel", "fatherPoiName": "Paris"}, "diversificationLabels": ["Lip-sync", "Performance"],
            "stickersOnItem": [{"stickerText": ["best", "friend"]}], "anchors": [{"type": 28, "keyword": "Pull"}],
            "author": {"id": "7", "secUid": "S", "signature": "bio"}, "authorStats": {"followingCount": 12},
            "video": {"subtitleInfos": [{"LanguageCodeName": "spa-ES", "Source": "ASR", "Url": "u"}]},
            "textExtra": [{"hashtagId": "9", "hashtagName": "blocus"}, {"userId": "1"}]}
    m = metadatos_ampliados(item)
    assert list(m) == COLUMNAS_AMPLIADAS
    assert m["pais_creacion"] == "FR" and m["es_aigc"] == "false" and m["moderacion_estado"] == "102"
    assert m["lugar"] == "Torre Eiffel" and m["lugar_ciudad"] == "Paris"
    assert m["categorias_recomendador"] == "Lip-sync|Performance" and m["stickers"] == "best friend" and m["anclas"] == "Pull"
    assert m["autor_bio"] == "bio" and m["autor_seguidos"] == "12" and m["subtitulos_idiomas"] == "spa-ES:ASR"
    assert m["hashtags_ids"] == "9:blocus" and m["fotos_urls"] == ""
    assert m["moderacion_json"] == '{"status":102,"reviewed":"0"}'
    assert all(v == "" for v in metadatos_ampliados({}).values())


def test_campos_forenses():
    from tiktok_utils import campos_forenses, campos_forenses_desde_fila, metadatos_ampliados, COLUMNAS_AMPLIADAS
    vid = (1_700_000_000 << 32) | 5          # el id esconde su fecha: 2023-11-14 22:13:20 UTC
    item = {"id": str(vid), "createTime": 1_700_000_000 + 3600,   # publicado 1 h después de crear el id ⇒ borrador
            "author": {"id": str((1_600_000_000 << 32) | 1)},
            "video": {"playAddr": "https://x/video/tos/alisg/tos-alisg-pve-0037/a/?bt=1098&q=1", "bitrate": 1125079,
                      "VQScore": "48.9", "volumeInfo": {"Loudness": -13.9, "Peak": 0.6}},
            "music": {"id": "77", "playUrl": "https://v/video/tos/no1a/tos-no1a-v-2370-no/b/?bt=125"},
            "statsV2": {"repostCount": "4"}, "poi": {"cityCode": "2975088", "countryCode": "3017382"},
            "penaltyContext": {"conclu_calculated_time": str((1_700_000_000 + 100) * 1000)},
            "warnInfo": [{"key": "electionsTag_banner"}]}
    f = campos_forenses(item)
    assert f["video_fecha_utc"] == "2023-11-14 23:13:20" and f["video_snowflake_utc"] == "2023-11-14 22:13:20"
    assert f["desfase_subida_seg"] == 3600 and f["inferencia_programado"] == 1
    assert f["autor_fecha_creacion_cuenta"] == "2020-09-13 12:26:40"
    assert (f["cdn_cluster_video"], f["cdn_cluster_audio"]) == ("alisg", "no1a")
    assert (f["video_origin_bucket"], f["video_bucket_suffix"]) == ("tos-alisg-pve-0037", "")
    assert (f["audio_origin_bucket"], f["audio_bucket_suffix"]) == ("tos-no1a-v-2370-no", "no")
    assert f["video_bitrate"] == 1125079 and f["video_vqscore"] == "48.9" and f["audio_loudness_lufs"] == -13.9
    assert f["video_reposts"] == "4" and f["poi_city_code"] == "2975088" and f["music_id"] == "77"
    assert f["latencia_moderacion_seg"] == -3500.0 and f["banner_institucional_key"] == "electionsTag_banner"
    # sin bitrate propio cae al bt= de la URL (×1024); un desfase < 5 min no es programado
    item["video"].pop("bitrate"); item["createTime"] = 1_700_000_010
    g = campos_forenses(item)
    assert g["video_bitrate"] == 1098 * 1024 and g["inferencia_programado"] == 0
    # los campos nuevos van al final de COLUMNAS_AMPLIADAS y un item vacío no inventa datos
    assert list(campos_forenses({})) == COLUMNAS_AMPLIADAS[-21:] and all(v in ("", None) for v in campos_forenses({}).values())
    assert list(metadatos_ampliados(item))[-21:] == COLUMNAS_AMPLIADAS[-21:]
    # las 50 columnas ampliadas previas no se mueven (empiezan en pais_creacion, acaban en audio_url); las 21 nuevas, detrás
    assert COLUMNAS_AMPLIADAS[0] == "pais_creacion" and COLUMNAS_AMPLIADAS[49] == "audio_url" and len(COLUMNAS_AMPLIADAS) == 71
    assert COLUMNAS_AMPLIADAS[50] == "video_fecha_utc" and COLUMNAS_AMPLIADAS[66] == "autor_fecha_creacion_cuenta" and COLUMNAS_AMPLIADAS[67:] == ["video_origin_bucket", "video_bucket_suffix", "audio_origin_bucket", "audio_bucket_suffix"]
    # retro-enriquecimiento desde una fila de CSV (video_fecha es %d-%m-%Y local)
    r = campos_forenses_desde_fila({"video_id": str(vid), "video_fecha": "14-11-2023 12:00:00", "audio_url": "u/video/tos/no1a/x",
                                    "moderacion_json": "{no json", "aviso_json": '[{"key":"k"}]'})
    assert r["video_snowflake_utc"] == "2023-11-14 22:13:20" and r["cdn_cluster_audio"] == "no1a"
    assert r["audio_origin_bucket"] == "" and r["video_origin_bucket"] == ""   # sin bucket `tos-X-…` en esas URLs de prueba
    assert r["banner_institucional_key"] == "k" and r["latencia_moderacion_seg"] == ""
    assert campos_forenses_desde_fila({})["desfase_subida_seg"] == ""
    assert campos_forenses_desde_fila({"aviso_json": float("nan")})["banner_institucional_key"] == ""
    assert campos_forenses({"video": {"VQScore": 0}})["video_vqscore"] == 0
    z = campos_forenses({"video": {"playAddr": "https://v/a.mp4", "subtitleInfos": [{"Url": "https://v/tos-alisg-v-1/x?bt=2"}]}})
    assert z["cdn_cluster_video"] == "alisg" and z["video_bitrate"] == 2048


def test_campos_forenses_comentario(tmp_path):
    import csv
    from tiktok_utils import (campos_forenses_comentario, campos_forenses_comentario_desde_fila, migrar_csv_comentarios,
                              cluster_cdn, COLUMNAS_COMENTARIOS, COLUMNAS_COMENTARIOS_BASE, COLUMNAS_COMENTARIOS_FORENSES)
    # 12 históricas intactas y primeras; 18 forenses detrás
    assert COLUMNAS_COMENTARIOS_BASE[:5] == ["video_id", "video_url", "username", "comment_id", "fecha"] and len(COLUMNAS_COMENTARIOS) == 30
    assert COLUMNAS_COMENTARIOS[11] == "parent_comment_id" and COLUMNAS_COMENTARIOS[12] == "comment_timestamp_unix"
    cid = (1_700_000_000 << 32) | 99
    c = {"cid": str(cid), "create_time": 1_700_000_030, "comment_language": "es", "reply_comment_total": 0,
         "is_author_digged": False, "stick_position": 0, "author_pin": False,
         "reply_to_reply_id": "770", "reply_to_userid": "55",
         "user": {"uid": str((1_600_000_000 << 32) | 1), "sec_uid": "SEC",
                  "avatar_thumb": {"url_list": ["https://p16/musically-maliva-obj/x", "https://p16/tos-no1a-avt-1/y"]}}}
    f = campos_forenses_comentario(c)
    assert list(f) == COLUMNAS_COMENTARIOS_FORENSES
    # create_time manda sobre el snowflake (que va ~30 s por detrás); la secuencia son los 32 bits bajos
    assert f["comment_timestamp_unix"] == 1_700_000_030 and f["comment_fecha_utc"] == "2023-11-14 22:13:50"
    assert f["comment_snowflake_utc"] == "2023-11-14 22:13:20" and f["comment_secuencia"] == 99
    assert f["autor_fecha_creacion_cuenta"] == "2020-09-13 12:26:40" and f["autor_cluster_cdn"] == "maliva"
    # avatar antiguo musically-*-obj: el cluster lo colapsa con maliva, pero el flag legacy lo distingue
    assert (f["autor_avatar_origin_bucket"], f["autor_avatar_bucket_suffix"], f["autor_avatar_legacy_musically"]) == ("musically-maliva-obj", "", "True")
    h = campos_forenses_comentario({"user": {"avatar_thumb": {"url_list": ["https://p16/tos-no1a-avt-0068c001-no/y~t"]}}})
    assert (h["autor_avatar_origin_bucket"], h["autor_avatar_bucket_suffix"], h["autor_avatar_legacy_musically"]) == ("tos-no1a-avt-0068c001-no", "no", "False")
    # los ceros reales se conservan; lo que falta es ""
    assert f["total_respuestas_hilo"] == 0 and f["like_del_creador"] == 0 and f["comentario_fijado"] == 0
    assert f["comment_ip_label"] == "" and f["comment_idioma"] == "es"
    assert (f["reply_to_comment_id"], f["reply_to_userid"]) == ("770", "55")
    # respuesta directa al raíz: reply_to_reply_id "0" no es arista; sin author_pin ni stick → ""
    g = campos_forenses_comentario({"cid": str(cid), "reply_to_reply_id": "0", "is_author_digged": True, "author_pin": True})
    assert g["reply_to_comment_id"] == "" and g["like_del_creador"] == 1 and g["comentario_fijado"] == 1
    assert g["total_respuestas_hilo"] == "" and g["comentario_fijado"] == 1
    assert all(v == "" for v in campos_forenses_comentario({}).values()) and campos_forenses_comentario(None)["autor_uid"] == ""
    assert cluster_cdn("https://x/musically-useast2a-obj/y") == "useast2a"
    # retro: la hora sale de `fecha` (local España), no del snowflake
    r = campos_forenses_comentario_desde_fila({"comment_id": str(cid), "fecha": "2023-11-14 23:14:00"})
    assert r["comment_timestamp_unix"] == 1_700_000_040 and r["comment_fecha_utc"] == "2023-11-14 22:14:00"
    assert r["comment_snowflake_utc"] == "2023-11-14 22:13:20" and r["comment_secuencia"] == 99 and r["autor_uid"] == ""
    # fecha ilegible o NaN → cae al snowflake; id corrupto → todo ""
    assert campos_forenses_comentario_desde_fila({"comment_id": str(cid), "fecha": float("nan")})["comment_timestamp_unix"] == 1_700_000_000
    assert campos_forenses_comentario_desde_fila({"comment_id": "abc", "fecha": ""})["comment_fecha_utc"] == ""
    # hora repetida del cambio de horario (26-10-2025 02:30 ocurre dos veces): gana el instante más cercano al snowflake
    utc_0030 = 1_761_438_600  # 2025-10-26 00:30 UTC = 02:30 CEST (1ª vez); 01:30 UTC = 02:30 CET (2ª)
    for ts in (utc_0030, utc_0030 + 3600):
        assert campos_forenses_comentario_desde_fila({"comment_id": str((ts - 20) << 32), "fecha": "2025-10-26 02:30:00"})["comment_timestamp_unix"] == ts
    # migración in situ 12→30: conserva filas y columnas, idempotente, y no pisa con columnas ajenas
    ruta = str(tmp_path / "c.csv")
    with open(ruta, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNAS_COMENTARIOS_BASE); w.writeheader()
        w.writerow({"video_id": "1", "comment_id": str(cid), "fecha": "2023-11-14 23:14:00", "texto": "hola, \"qué\"", "likes": "0"})
    assert migrar_csv_comentarios(ruta) == 1 and migrar_csv_comentarios(ruta) == 0
    fila = next(csv.DictReader(open(ruta, encoding="utf-8-sig", newline="")))
    assert list(fila) == COLUMNAS_COMENTARIOS and fila["texto"] == 'hola, "qué"' and fila["likes"] == "0"
    assert fila["comment_fecha_utc"] == "2023-11-14 22:14:00" and fila["reply_to_userid"] == ""
    ajeno = str(tmp_path / "a.csv")
    open(ajeno, "w", encoding="utf-8-sig").write("comment_id,sentiment\n1,POS\n")
    try:
        migrar_csv_comentarios(ajeno); assert False
    except ValueError:
        assert open(ajeno, encoding="utf-8-sig").read().startswith("comment_id,sentiment")


def test_bucket_cdn():
    from tiktok_utils import bucket_cdn
    # tos-* con y sin sufijo (el sufijo es el último tramo alfabético de un bucket de 5+ tramos)
    assert bucket_cdn("https://p16-common-sign.tiktokcdn-eu.com/tos-no1a-avt-0068c001-no/ab~tplv.jpg?x=1") == ("tos-no1a-avt-0068c001-no", "no", False)
    assert bucket_cdn("https://p16/tos-useast2a-avt-0068-euttp/ab") == ("tos-useast2a-avt-0068-euttp", "euttp", False)
    assert bucket_cdn("https://p16/tos-alisg-ve-37c815-sg/ab") == ("tos-alisg-ve-37c815-sg", "sg", False)
    assert bucket_cdn("https://p16/tos-maliva-avt-0068/ab") == ("tos-maliva-avt-0068", "", False)
    assert bucket_cdn("https://p16/tos-alisg-pve-0037c001/ab")[1] == ""
    # /video/tos/<idc>/ no es el bucket: se queda con el tos-… posterior
    assert bucket_cdn("https://v45.tiktokcdn-eu.com/h/t/video/tos/no1a/tos-no1a-v-2370-no/ab/?bt=1") == ("tos-no1a-v-2370-no", "no", False)
    assert bucket_cdn("https://v/video/tos/alisg/tos-alisg-ve-37c815-sg") == ("tos-alisg-ve-37c815-sg", "sg", False)   # bucket al final de la URL
    # avatar antiguo: legacy, sin sufijo
    assert bucket_cdn("https://p16/musically-maliva-obj/ab.jpeg") == ("musically-maliva-obj", "", True)
    # nulos y malformados
    for malo in (None, "", 5, float("nan"), "https://p16/avatar.jpg", "tos-", "https://p16/tos-/x", "/tos-no1a/x"):
        assert bucket_cdn(malo) == ("", "", False), malo


def test_reparsear_buckets_cdn(tmp_path):
    import csv, json, subprocess, sys
    uid = (1_780_000_000 << 32) | 1   # cuenta de 2026
    item = {"id": "7", "author": {"id": str(uid), "avatarThumb": "https://p16/musically-maliva-obj/a"},
            "video": {"PlayAddrStruct": {"UrlList": ["https://v16-webapp-prime.tiktok.com/video/tos/no1a/tos-no1a-ve-0068-no/x"]}}}
    (tmp_path / "7.json").write_text(json.dumps({"item": item}), encoding="utf-8")
    (tmp_path / "roto.json").write_text("{no json", encoding="utf-8")
    (tmp_path / "vacio.json").write_text(json.dumps({"item": {}}), encoding="utf-8")
    salida = tmp_path / "o.csv"
    r = subprocess.run([sys.executable, "-m", "scripts.reparsear_buckets_cdn", str(tmp_path), "-o", str(salida)],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    fila = next(csv.DictReader(open(salida, encoding="utf-8-sig", newline="")))
    assert (fila["avatar_origin_bucket"], fila["avatar_legacy_musically"], fila["autor_cohorte_anio"]) == ("musically-maliva-obj", "True", "2026")
    assert (fila["video_origin_bucket"], fila["video_bucket_suffix"]) == ("tos-no1a-ve-0068-no", "no") and "edge_host" not in fila
    assert "v16-webapp-prime.tiktok.com" in r.stdout and "Avatar y vídeo en distinto clúster: 1 de 1" in r.stdout


def test_comentarios_casos_limite(tmp_path):
    import csv, importlib.util
    from tiktok_utils import campos_forenses_comentario, migrar_csv_comentarios, COLUMNAS_COMENTARIOS, COLUMNAS_COMENTARIOS_BASE
    # booleanos que llegan como texto
    for v in ("0", "false", ""):
        g = campos_forenses_comentario({"is_author_digged": v, "author_pin": v})
        assert g["like_del_creador"] == 0 and g["comentario_fijado"] == 0
    assert campos_forenses_comentario({"is_author_digged": "1", "stick_position": "2"})["comentario_fijado"] == 1
    # CSV con filas de más campos: no se migra ni se toca
    mal = tmp_path / "m.csv"
    mal.write_text(",".join(COLUMNAS_COMENTARIOS_BASE) + "\n" + ",".join(["x"] * 14) + "\n", encoding="utf-8-sig")
    antes = mal.read_bytes()
    try:
        migrar_csv_comentarios(str(mal)); assert False
    except ValueError:
        assert mal.read_bytes() == antes
    # append_csv sobre un CSV de 30 columnas sin salto de línea final: no pega registros
    spec = importlib.util.spec_from_file_location("sc", "src/scrapers/2_tiktok_scraper_comentarios_api.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    ruta = str(tmp_path / "c.csv")
    m.append_csv([{"video_id": "1", "comment_id": "1"}], ruta)
    with open(ruta, "rb+") as f:
        data = f.read().rstrip(b"\r\n"); f.seek(0); f.truncate(); f.write(data)
    m.append_csv([{"video_id": "2", "comment_id": "2"}], ruta)
    filas = list(csv.DictReader(open(ruta, encoding="utf-8-sig", newline="")))
    assert [r["video_id"] for r in filas] == ["1", "2"] and list(filas[0]) == COLUMNAS_COMENTARIOS


def test_fusion_videos_y_escritura(tmp_path):
    import csv, json, importlib.util
    from tiktok_utils import leer_filas_previas, fusionar_filas_video, escribir_atomico, COLUMNAS_AMPLIADAS
    jp, cp = str(tmp_path / "a.json"), str(tmp_path / "a.csv")
    assert leer_filas_previas(jp, cp) == {}
    # solo CSV (el JSON falta): el histórico se recupera en vez de perderse
    with open(cp, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["video_id", "video_fecha", "poi_city_code"]); w.writeheader()
        w.writerow({"video_id": "1", "video_fecha": "14-11-2023 12:00:00", "poi_city_code": "77"})
    previas = leer_filas_previas(jp, cp)
    assert list(previas) == ["1"] and previas["1"]["poi_city_code"] == "77"
    # un valor nuevo vacío no pisa el ya capturado; un 0 real sí cuenta; los vídeos nuevos se suman
    vid = str((1_700_000_000 << 32) | 5)
    previas[vid] = {"video_id": vid, "video_fecha": "14-11-2023 23:13:20"}
    filas = fusionar_filas_video(previas, [{"video_id": "1", "poi_city_code": "", "video_likes": 0}, {"video_id": "2"}, {"sin_id": 1}])
    por = {r["video_id"]: r for r in filas}
    assert set(por) == {"1", vid, "2"} and por["1"]["poi_city_code"] == "77" and por["1"]["video_likes"] == 0
    # las filas antiguas reciben lo calculable (fecha UTC desde video_fecha, desfase desde el id)
    assert por[vid]["video_fecha_utc"] == "2023-11-14 22:13:20" and por[vid]["desfase_subida_seg"] == 0
    # JSON ilegible + CSV bueno: se sigue con el CSV; ambos ilegibles: no se sobrescribe nada
    open(jp, "w", encoding="utf-8").write("{roto")
    assert list(leer_filas_previas(jp, cp)) == ["1"]
    open(cp, "wb").write(bytes([0xFF, 0xFE, 0x00, 0xFF]))
    try:
        leer_filas_previas(jp, cp); assert False
    except RuntimeError:
        assert open(jp, encoding="utf-8").read() == "{roto"
    # escritura atómica: sin temporales y sustitución completa
    escribir_atomico(jp, lambda f: f.write("[]"), encoding="utf-8")
    assert open(jp, encoding="utf-8").read() == "[]" and [x.name for x in tmp_path.iterdir() if x.name.endswith(".tmp")] == []

    # scraper de perfil: dos pasadas suman, y el CSV no repite cabeceras (music_id estaba duplicado)
    spec = importlib.util.spec_from_file_location("su", "src/scrapers/1_tiktok_scraper_user.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    m.dataset_dir = lambda nombre: str(tmp_path)
    m.save_results("u", [{"video_id": "10", "music_id": "m"}], {})
    m.save_results("u", [{"video_id": "11"}], {})
    cab = next(csv.reader(open(tmp_path / "user_u_videos.csv", encoding="utf-8-sig", newline="")))
    assert len(cab) == len(set(cab)) and cab[-4:] == ["video_origin_bucket", "video_bucket_suffix", "audio_origin_bucket", "audio_bucket_suffix"]
    assert [r["video_id"] for r in csv.DictReader(open(tmp_path / "user_u_videos.csv", encoding="utf-8-sig", newline=""))] == ["10", "11"]


def test_bucket_en_url_alternativa_y_csv_sin_tty():
    import importlib.util
    from tiktok_utils import campos_forenses, campos_forenses_comentario
    # playAddr da clúster pero sin bucket completo: se toma de otra URL del mismo payload
    it = {"video": {"playAddr": "https://v/video/tos/no1a/x", "PlayAddrStruct": {"UrlList": ["https://v/video/tos/no1a/tos-no1a-ve-0068-no/y"]}}}
    f = campos_forenses(it)
    assert (f["cdn_cluster_video"], f["video_origin_bucket"], f["video_bucket_suffix"]) == ("no1a", "tos-no1a-ve-0068-no", "no")
    c = campos_forenses_comentario({"user": {"avatar_thumb": {"url_list": ["https://p/sin-bucket.jpg", "https://p/tos-useast2a-avt-1-euttp/z"]}}})
    assert (c["autor_cluster_cdn"], c["autor_avatar_origin_bucket"]) == ("useast2a", "tos-useast2a-avt-1-euttp")
    # sin TTY y sin CSV válido, el scraper de comentarios sale con error en vez de abrir un diálogo
    spec = importlib.util.spec_from_file_location("sc2", "src/scrapers/2_tiktok_scraper_comentarios_api.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    import sys
    argv, sys.argv = sys.argv, ["scraper"]
    try:
        m.seleccionar_csv(); assert False
    except SystemExit as e:
        assert e.code == 1
    finally:
        sys.argv = argv


def test_id_posible_en_rango():
    from datetime import datetime
    from tiktok_utils import id_posible_en_rango
    def vid(y, m, d):
        return str(int(datetime(y, m, d, 12).timestamp()) << 32)
    ini, fin = datetime(2026, 11, 10), datetime(2026, 11, 14)
    assert id_posible_en_rango(vid(2026, 11, 12), ini, fin)                 # dentro
    assert id_posible_en_rango(vid(2026, 11, 3), ini, fin)                  # id anterior pero publicado después (programado): se revisa
    assert not id_posible_en_rango(vid(2026, 10, 1), ini, fin)              # claramente antiguo
    assert not id_posible_en_rango(vid(2026, 11, 20), ini, fin)             # un id posterior al fin nunca puede publicarse antes
    assert id_posible_en_rango(vid(2026, 11, 15), ini, fin)                 # 1 día de margen por arriba
    assert id_posible_en_rango("abc", ini, fin) and id_posible_en_rango(vid(2020, 1, 1), None, None)
    assert not id_posible_en_rango(vid(2026, 10, 25), ini, fin, margen_dias=7)
