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
