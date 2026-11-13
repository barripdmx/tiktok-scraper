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
    assert f["video_bitrate"] == 1125079 and f["video_vqscore"] == "48.9" and f["audio_loudness_lufs"] == -13.9
    assert f["video_reposts"] == "4" and f["poi_city_code"] == "2975088" and f["music_id"] == "77"
    assert f["latencia_moderacion_seg"] == -3500.0 and f["banner_institucional_key"] == "electionsTag_banner"
    # sin bitrate propio cae al bt= de la URL (×1024); un desfase < 5 min no es programado
    item["video"].pop("bitrate"); item["createTime"] = 1_700_000_010
    g = campos_forenses(item)
    assert g["video_bitrate"] == 1098 * 1024 and g["inferencia_programado"] == 0
    # los campos nuevos van al final de COLUMNAS_AMPLIADAS y un item vacío no inventa datos
    assert list(campos_forenses({})) == COLUMNAS_AMPLIADAS[-17:] and all(v in ("", None) for v in campos_forenses({}).values())
    assert list(metadatos_ampliados(item))[-17:] == COLUMNAS_AMPLIADAS[-17:]
    # las 50 columnas ampliadas previas no se mueven (empiezan en pais_creacion, acaban en audio_url); las 17 nuevas, detrás
    assert COLUMNAS_AMPLIADAS[0] == "pais_creacion" and COLUMNAS_AMPLIADAS[49] == "audio_url" and len(COLUMNAS_AMPLIADAS) == 67
    assert COLUMNAS_AMPLIADAS[50] == "video_fecha_utc" and COLUMNAS_AMPLIADAS[-1] == "autor_fecha_creacion_cuenta"
    # retro-enriquecimiento desde una fila de CSV (video_fecha es %d-%m-%Y local)
    r = campos_forenses_desde_fila({"video_id": str(vid), "video_fecha": "14-11-2023 12:00:00", "audio_url": "u/video/tos/no1a/x",
                                    "moderacion_json": "{no json", "aviso_json": '[{"key":"k"}]'})
    assert r["video_snowflake_utc"] == "2023-11-14 22:13:20" and r["cdn_cluster_audio"] == "no1a"
    assert r["banner_institucional_key"] == "k" and r["latencia_moderacion_seg"] == ""
    assert campos_forenses_desde_fila({})["desfase_subida_seg"] == ""
    assert campos_forenses_desde_fila({"aviso_json": float("nan")})["banner_institucional_key"] == ""
    assert campos_forenses({"video": {"VQScore": 0}})["video_vqscore"] == 0
    z = campos_forenses({"video": {"playAddr": "https://v/a.mp4", "subtitleInfos": [{"Url": "https://v/tos-alisg-v-1/x?bt=2"}]}})
    assert z["cdn_cluster_video"] == "alisg" and z["video_bitrate"] == 2048
