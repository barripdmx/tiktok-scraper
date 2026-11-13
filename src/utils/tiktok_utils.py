# -*- coding: utf-8 -*-
"""
tiktok_utils.py — Funciones compartidas entre los scrapers de TikTok.

Importar desde los scrapers:
    from tiktok_utils import (
        get_date_from_video_id, estimate_date_from_id_simple,
        is_likely_in_date_range, is_in_date_range,
        extract_video_id_from_url, extract_username_from_url,
        is_valid_video_url, parse_count,
        human_scroll, accept_cookies_banner, handle_verification,
        detect_end_of_results,
        resolve_cookies_path,
        load_cookies, save_cookies, ensure_context,
        collect_video_urls,
        cli_value, ask_or_arg,
    )
"""

import os
import re
import sys
import csv
import glob
import json
import asyncio
import random
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

# ---------------------------------------------------------------------------
# PARÁMETROS POR LÍNEA DE COMANDOS
#
# El menú gráfico recoge usuario/términos/fechas en sus propios campos y los
# pasa como flags. Ejecutado a mano, el scraper sigue preguntando por consola:
# ask_or_arg() usa el flag si viene y, si no, cae al input() de siempre.
# Con --no-prompt (lo pasa el menú) nunca pregunta: aplica el valor por defecto.
# ---------------------------------------------------------------------------

def cli_value(flag: str, argv=None) -> str | None:
    """Valor que sigue a `flag` en argv, o None si el flag no aparece."""
    argv = sys.argv if argv is None else argv
    if flag in argv:
        i = argv.index(flag)
        if i + 1 < len(argv):
            return argv[i + 1].strip()
    return None


def ask_or_arg(flag: str, prompt: str, default: str = "", argv=None) -> str:
    """Valor del flag; si no viene, pregunta por consola (o devuelve default
    cuando se ha pedido modo no interactivo con --no-prompt)."""
    argv = sys.argv if argv is None else argv
    value = cli_value(flag, argv)
    if value is not None:
        return value
    if "--no-prompt" in argv:
        return default
    return input(prompt).strip()

# ---------------------------------------------------------------------------
# FECHA DESDE ID (Snowflake timestamp: id >> 32 = segundos Unix)
# ---------------------------------------------------------------------------

def get_date_from_video_id(video_id: str) -> datetime:
    """Extrae la fecha aproximada del ID del video (id >> 32 = timestamp Unix)."""
    try:
        vid = int(str(video_id).replace("'", "").strip())
        return datetime.fromtimestamp(vid >> 32)
    except Exception:
        return None


# Alias usado en 1_tiktok_scraper_user.py
get_date_from_id = get_date_from_video_id


def estimate_date_from_id_simple(video_id: str) -> datetime:
    """
    Estimación alternativa basada en el prefijo del ID (primeros 3 dígitos).
    Activo cuando el shift de 32 bits falla (IDs sin timestamp estándar).

    Rangos calibrados a 2026-05 (id >> 32 = unix timestamp):
        prefix >= 772 → 2027-01
        prefix >= 771 → 2026-12
        prefix >= 768 → 2026-09
        prefix >= 764 → 2026-06
        prefix >= 761 → 2026-03
        prefix >= 759 → 2026-01
        prefix >= 757 → 2025-12
        prefix >= 754 → 2025-09
        prefix >= 751 → 2025-06
        prefix >= 745 → 2025-01
        prefix >= 737 → 2024-06
        prefix >= 731 → 2024-01
        prefix >= 718 → 2023-01
        prefix >= 704 → 2022-01
        prefix >= 691 → 2021-01
        else          → 2020-01
    """
    try:
        vid = str(video_id).replace("'", "")
        prefix = int(vid[:3]) if len(vid) >= 3 else 0

        if prefix >= 772:
            return datetime(2027, 1, 1)
        elif prefix >= 771:
            return datetime(2026, 12, 1)
        elif prefix >= 768:
            return datetime(2026, 9, 1)
        elif prefix >= 764:
            return datetime(2026, 6, 1)
        elif prefix >= 761:
            return datetime(2026, 3, 1)
        elif prefix >= 759:
            return datetime(2026, 1, 1)
        elif prefix >= 757:
            return datetime(2025, 12, 1)
        elif prefix >= 754:
            return datetime(2025, 9, 1)
        elif prefix >= 751:
            return datetime(2025, 6, 1)
        elif prefix >= 745:
            return datetime(2025, 1, 1)
        elif prefix >= 737:
            return datetime(2024, 6, 1)
        elif prefix >= 731:
            return datetime(2024, 1, 1)
        elif prefix >= 718:
            return datetime(2023, 1, 1)
        elif prefix >= 704:
            return datetime(2022, 1, 1)
        elif prefix >= 691:
            return datetime(2021, 1, 1)
        else:
            return datetime(2020, 1, 1)
    except Exception:
        return None


def is_likely_in_date_range(
    video_id: str,
    start_dt: datetime,
    end_dt: datetime,
    margin_days: int = 2,
) -> bool:
    """Filtro previo con margen de error para no descartar videos en el límite."""
    if not start_dt and not end_dt:
        return True

    estimated = get_date_from_video_id(video_id) or estimate_date_from_id_simple(video_id)
    if not estimated:
        return True  # Si no se puede estimar, incluir por precaución

    margin = timedelta(days=margin_days)
    if start_dt and estimated.date() < (start_dt - margin).date():
        return False
    if end_dt and estimated.date() > (end_dt + margin).date():
        return False
    return True


def is_in_date_range(
    video_id: str,
    start_dt: datetime,
    end_dt: datetime,
) -> bool:
    """Filtro exacto sin margen (usado en el scraper de usuarios)."""
    if not start_dt and not end_dt:
        return True

    video_date = get_date_from_video_id(video_id)
    if not video_date:
        return True

    if start_dt and video_date.date() < start_dt.date():
        return False
    if end_dt and video_date.date() > end_dt.date():
        return False
    return True


# ---------------------------------------------------------------------------
# UTILIDADES DE URL
# ---------------------------------------------------------------------------

def normalize_tiktok_url(url: str) -> str:
    """
    Normaliza una URL de TikTok eliminando parámetros de tracking y fragmentos.
    No resuelve URLs cortas (vm.tiktok.com / vt.tiktok.com) — requeriría HTTP.
    """
    if not url:
        return ""
    # Eliminar query-string y fragmento
    url = url.split("?")[0].split("#")[0]
    # Asegurar protocolo
    if url.startswith("//"):
        url = "https:" + url
    elif url.startswith("/"):
        url = "https://www.tiktok.com" + url
    return url


def extract_video_id_from_url(url: str) -> str:
    """Extrae el ID numérico de una URL de vídeo de TikTok.

    Soporta los formatos:
    - https://www.tiktok.com/@user/video/1234567890123456789
    - https://www.tiktok.com/@user/video/1234567890123456789?foo=bar
    - /t/XXXXXXXXXX/  (formato corto — no se puede resolver sin HTTP)
    """
    url = normalize_tiktok_url(url or "")
    m = re.search(r'/video/(\d+)', url)
    return m.group(1) if m else ""


def extract_username_from_url(url: str) -> str:
    url = normalize_tiktok_url(url or "")
    m = re.search(r'/@([^/]+)/video/', url)
    return m.group(1) if m else ""


def is_valid_video_url(url: str) -> bool:
    """Valida que la URL contenga un ID numérico de al menos 15 dígitos."""
    if not url or "/video/" not in (url or ""):
        return False
    try:
        video_id = normalize_tiktok_url(url).split("/video/")[-1].split("/")[0]
        return video_id.isdigit() and len(video_id) >= 15
    except Exception:
        return False


# ---------------------------------------------------------------------------
# MÉTRICAS
# ---------------------------------------------------------------------------

def parse_count(text: str) -> int:
    """Convierte '1.2M', '500K', '1.234' a entero. Usado en fallback HTML."""
    if not text:
        return 0
    text = text.strip().upper().replace(',', '.')
    try:
        if 'M' in text:
            return int(float(text.replace('M', '')) * 1_000_000)
        elif 'K' in text:
            return int(float(text.replace('K', '')) * 1_000)
        else:
            cleaned = re.sub(r'[^\d]', '', text)
            return int(cleaned) if cleaned else 0
    except Exception:
        return 0


def _json(valor) -> str:
    if valor in (None, "", [], {}):
        return ""
    return json.dumps(valor, ensure_ascii=False, separators=(",", ":"))


def _celda(valor) -> str:
    if valor is None:
        return ""
    if isinstance(valor, bool):
        return "true" if valor else "false"
    return str(valor)


# ---------------------------------------------------------------------------
# CAMPOS FORENSES: snowflake (fechas ocultas en los ids), CDN, calidad, moderación
# ---------------------------------------------------------------------------

def _entero(valor) -> int:
    try:
        return int(float(valor))
    except (TypeError, ValueError):
        return 0


def _id_snowflake(valor) -> tuple:
    """(unix ts en s, secuencia) de un id snowflake de TikTok: 32 bits altos y bajos. (0, "") si no es plausible (2014-2036)."""
    try:
        v = int(str(valor).strip())
    except ValueError:
        return 0, ""
    ts = v >> 32
    return (ts, v & 0xFFFFFFFF) if 1_400_000_000 < ts < 2_100_000_000 else (0, "")


def _snowflake_ts(valor) -> int:
    """Unix ts (s) en los 32 bits altos de un id de TikTok (vídeo o usuario); 0 si no es plausible."""
    return _id_snowflake(valor)[0]


try:
    from zoneinfo import ZoneInfo
    _MADRID = ZoneInfo("Europe/Madrid")
except Exception:  # sin tzdata (Windows limpio): se usa la hora local de la máquina
    _MADRID = None


def _fecha_local_a_ts(texto, formato: str, ref_ts: int = 0) -> int:
    """Hora local de España (como la guardan los scrapers) → unix UTC; 0 si no se puede leer.

    En la hora repetida del cambio de horario hay dos instantes posibles: se elige el más cercano a ref_ts (snowflake).
    """
    try:
        dt = datetime.strptime(str(texto).strip(), formato)
    except ValueError:
        return 0
    cands = {int(dt.replace(tzinfo=_MADRID, fold=f).timestamp()) for f in (0, 1)} if _MADRID else {int(dt.timestamp())}
    return min(cands, key=lambda t: abs(t - ref_ts))


def _utc(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S") if ts else ""


def cluster_cdn(url) -> str:
    """Nodo físico del CDN de TikTok (no1a=UE, alisg=Singapur, maliva=Virginia…) a partir de una URL de vídeo/audio/subtítulo."""
    if not isinstance(url, str):
        return ""
    m = (re.search(r"tos-([a-z0-9]+)-", url) or re.search(r"/video/tos/([a-z0-9]+)/", url)
         or re.search(r"musically-([a-z0-9]+)-obj", url))  # avatares antiguos: /musically-maliva-obj/
    return m.group(1) if m else ""


def _bitrate_desde_url(url) -> int | str:
    """El parámetro bt= del CDN es video.bitrate/1024 (mediana 1024,5 sobre 310 pares reales): se reescala a bps."""
    try:
        bt = parse_qs(urlparse(url).query).get("bt", [""])[0]
    except (AttributeError, ValueError):
        return ""
    return int(bt) * 1024 if bt.isdigit() else ""


def _latencia_moderacion(conclu_ms, create_ts: int) -> float | str:
    """Segundos entre la publicación y el veredicto del clasificador de Trust & Safety (conclu_calculated_time)."""
    ms = _entero(conclu_ms)
    return round(ms / 1000.0 - create_ts, 2) if ms and create_ts else ""


def _derivados_id(create_ts: int, video_id, autor_uid) -> dict:
    """Fechas y desfase calculables solo con createTime + ids. desfase > 5 min ⇒ vídeo subido como borrador/programado."""
    sf = _snowflake_ts(video_id)
    desfase = create_ts - sf if create_ts and sf else ""
    return {
        "video_fecha_utc": _utc(create_ts),
        "video_snowflake_utc": _utc(sf),
        "desfase_subida_seg": desfase,
        "inferencia_programado": "" if desfase == "" else int(abs(desfase) > 300),
        "autor_fecha_creacion_cuenta": _utc(_snowflake_ts(autor_uid)),
    }


def campos_forenses(item: dict) -> dict:
    """17 campos forenses del itemStruct de TikTok. Vacío ("") cuando el dato no existe (distinto de 0)."""
    item = item or {}
    v = item.get("video") or {}
    music = item.get("music") or {}
    vol = v.get("volumeInfo") or {}
    poi = item.get("poi") or {}
    warn = item.get("warnInfo")
    subs = v.get("subtitleInfos") or []
    play = v.get("playAddr") or ""
    if isinstance(play, dict):
        play = (play.get("UrlList") or play.get("url_list") or [""])[0]
    play = play or ((v.get("PlayAddrStruct") or {}).get("UrlList") or [""])[0]
    sub_url = subs[0].get("Url", "") if subs else ""
    ref = play if cluster_cdn(play) else (sub_url or play)  # si playAddr no da cluster, prueba el subtítulo
    create_ts = _entero(item.get("createTime"))
    der = _derivados_id(create_ts, item.get("id"), (item.get("author") or {}).get("id"))
    cuenta = der.pop("autor_fecha_creacion_cuenta")  # va la última, como en la especificación
    return {
        **der,
        "cdn_cluster_video": cluster_cdn(ref),
        "cdn_cluster_audio": cluster_cdn(music.get("playUrl")),
        "poi_city_code": poi.get("cityCode", ""),
        "poi_country_code": poi.get("countryCode", ""),
        "video_reposts": (item.get("statsV2") or {}).get("repostCount"),
        "video_bitrate": v.get("bitrate") or _bitrate_desde_url(ref),
        # TikTok lo guarda en video.VQScore; la ruta claInfo.originalLanguageInfo.vqScore no aparece en datos reales
        "video_vqscore": v["VQScore"] if v.get("VQScore") is not None else ((v.get("claInfo") or {}).get("originalLanguageInfo") or {}).get("vqScore"),
        "audio_loudness_lufs": vol.get("Loudness"),
        "audio_peak": vol.get("Peak"),
        "music_id": music.get("id"),
        # el item no trae "moderation_info": el sello de tiempo vive en penaltyContext
        "latencia_moderacion_seg": _latencia_moderacion((item.get("penaltyContext") or {}).get("conclu_calculated_time"), create_ts),
        "banner_institucional_key": warn[0].get("key", "") if isinstance(warn, list) and warn and isinstance(warn[0], dict) else "",
        "autor_fecha_creacion_cuenta": cuenta,
    }


def campos_forenses_desde_fila(row: dict) -> dict:
    """Los campos forenses que se pueden derivar de una fila de CSV ya capturada, sin volver a TikTok.

    Solo devuelve los calculables (no hay poi/reposts/vqscore/loudness/music_id). Valores de la fila como
    texto (leer con dtype=str, keep_default_na=False). video_fecha es hora local de España.
    """
    create_ts = _fecha_local_a_ts(row.get("video_fecha"), "%d-%m-%Y %H:%M:%S", _snowflake_ts(row.get("video_id")))
    sub = str(row.get("subtitulos_urls") or "").split("|")[0]
    def leer(clave, defecto):
        try:
            return json.loads(row.get(clave) or "") or defecto
        except (json.JSONDecodeError, TypeError):  # TypeError: NaN de pandas
            return defecto

    pen, warn = leer("moderacion_json", {}), leer("aviso_json", [])
    return {
        **_derivados_id(create_ts, row.get("video_id"), row.get("autor_uid")),
        "cdn_cluster_video": cluster_cdn(sub),
        "cdn_cluster_audio": cluster_cdn(row.get("audio_url")),
        "video_bitrate": _bitrate_desde_url(sub),
        "latencia_moderacion_seg": _latencia_moderacion(pen.get("conclu_calculated_time") if isinstance(pen, dict) else None, create_ts),
        "banner_institucional_key": warn[0].get("key", "") if isinstance(warn, list) and warn and isinstance(warn[0], dict) else "",
    }


# ---------------------------------------------------------------------------
# COMENTARIOS: 12 columnas históricas + 15 forenses (siempre al final)
# ---------------------------------------------------------------------------

COLUMNAS_COMENTARIOS_BASE = [
    "video_id", "video_url", "username", "comment_id", "fecha", "autor_nombre", "autor_handle",
    "texto", "likes", "aweme_id_api", "is_reply", "parent_comment_id",
]
COLUMNAS_COMENTARIOS_FORENSES = [
    "comment_timestamp_unix", "comment_fecha_utc", "comment_snowflake_utc", "comment_secuencia_ms",
    "comment_ip_label", "comment_idioma", "autor_uid", "autor_secuid", "autor_fecha_creacion_cuenta",
    "autor_cluster_cdn", "total_respuestas_hilo", "like_del_creador", "comentario_fijado",
    "reply_to_comment_id", "reply_to_userid",
]
COLUMNAS_COMENTARIOS = COLUMNAS_COMENTARIOS_BASE + COLUMNAS_COMENTARIOS_FORENSES


def _bool(v) -> int:
    """0/1 también desde texto de CSV: "0", "false" y "" son falsos."""
    return int(str(v).strip().lower() not in ("", "0", "false", "none", "null"))


def _o_vacio(valor, convertir=_entero):
    """"" solo si el dato falta (None); un 0 real se conserva."""
    return "" if valor is None else convertir(valor)


def campos_forenses_comentario(c: dict) -> dict:
    """15 campos forenses de un comentario crudo de /api/comment/list/ o /api/comment/list/reply/.

    create_time (la fecha real) va entre 9 s y 25 min DETRÁS del snowflake del cid (mediana 29 s): no coinciden.
    reply_to_reply_id/reply_to_userid solo vienen cuando la respuesta contesta a otra respuesta (distinta del raíz).
    """
    c = c if isinstance(c, dict) else {}
    user = c.get("user") if isinstance(c.get("user"), dict) else {}
    sf, seq = _id_snowflake(c.get("cid"))
    ct = _entero(c.get("create_time"))
    avatar = next((k for u in ((user.get("avatar_thumb") or {}).get("url_list") or []) if (k := cluster_cdn(u))), "")
    pos, pin = c.get("stick_position"), c.get("author_pin")
    sin_destino = ("", "0", "None")
    return {
        "comment_timestamp_unix": ct or sf or "",
        "comment_fecha_utc": _utc(ct or sf),
        "comment_snowflake_utc": _utc(sf),
        "comment_secuencia_ms": seq,
        "comment_ip_label": _o_vacio(c.get("ip_label"), str),  # la API web actual no lo devuelve (0 de 628)
        "comment_idioma": _o_vacio(c.get("comment_language"), str),
        "autor_uid": _o_vacio(user.get("uid"), str),
        "autor_secuid": _o_vacio(user.get("sec_uid"), str),
        "autor_fecha_creacion_cuenta": _utc(_snowflake_ts(user.get("uid"))),
        "autor_cluster_cdn": avatar,
        "total_respuestas_hilo": _o_vacio(c.get("reply_comment_total")),  # solo en comentarios raíz
        "like_del_creador": _o_vacio(c.get("is_author_digged"), _bool),
        "comentario_fijado": "" if pos is None and pin is None else int(_entero(pos) > 0 or bool(_bool(pin))),
        "reply_to_comment_id": "" if str(c.get("reply_to_reply_id")) in sin_destino else str(c["reply_to_reply_id"]),
        "reply_to_userid": "" if str(c.get("reply_to_userid")) in sin_destino else str(c["reply_to_userid"]),
    }


def campos_forenses_comentario_desde_fila(row: dict) -> dict:
    """Los 4 campos temporales calculables de una fila de CSV antiguo (12 columnas); el resto queda "".

    La hora sale de `fecha` (create_time, local de España); el snowflake solo desambigua la hora repetida
    del cambio de horario o sustituye a una `fecha` ilegible (entonces va ~29 s adelantado).
    """
    sf, seq = _id_snowflake(row.get("comment_id"))
    ts = _fecha_local_a_ts(row.get("fecha"), "%Y-%m-%d %H:%M:%S", sf) or sf
    res = dict.fromkeys(COLUMNAS_COMENTARIOS_FORENSES, "")
    res.update(comment_timestamp_unix=ts or "", comment_fecha_utc=_utc(ts), comment_snowflake_utc=_utc(sf), comment_secuencia_ms=seq)
    return res


def migrar_csv_comentarios(ruta: str) -> int:
    """Pasa in situ un CSV de comentarios de 12 columnas a las 27, sin perder filas ni columnas. Devuelve las filas migradas.

    0 si ya está al día. Lanza ValueError (sin tocar el fichero) si trae columnas ajenas que se perderían.
    """
    with open(ruta, encoding="utf-8-sig", newline="") as f:
        lector = csv.DictReader(f)
        if lector.fieldnames == COLUMNAS_COMENTARIOS:
            return 0
        ajenas = [c for c in lector.fieldnames or [] if c not in COLUMNAS_COMENTARIOS]
        if ajenas:
            raise ValueError(f"{ruta}: columnas ajenas {ajenas}; no se migra para no perderlas")
        filas = list(lector)
    if any(None in f or None in f.values() for f in filas):  # DictReader pone aquí las filas con más o menos campos
        raise ValueError(f"{ruta}: filas con nº de campos distinto a la cabecera; no se migra")
    tmp = ruta + ".tmp"
    with open(tmp, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNAS_COMENTARIOS)
        w.writeheader()
        for fila in filas:
            for k, v in campos_forenses_comentario_desde_fila(fila).items():
                if not fila.get(k):
                    fila[k] = v
            w.writerow(fila)
    os.replace(tmp, ruta)
    return len(filas)


def metadatos_ampliados(item: dict) -> dict:
    """Metadatos OSINT del itemStruct de una publicación (vídeo o foto) que no son métricas básicas.

    País atribuido por TikTok (locationCreated), idioma, etiquetas de IA, moderación (penaltyContext),
    lugar etiquetado (poi), categorías del recomendador, anuncios, stickers y anclas. Valores en texto.
    """
    item = item or {}
    pen = item.get("penaltyContext") or {}
    poi = item.get("poi") or {}
    duet = item.get("duetInfo") or {}
    ia = item.get("creatorAIComment") or {}
    autor = item.get("author") or {}
    subs = (item.get("video") or {}).get("subtitleInfos") or []
    fotos = (item.get("imagePost") or {}).get("images") or []
    return {k: _celda(v) for k, v in {
        "pais_creacion": item.get("locationCreated", ""),
        "idioma_texto": item.get("textLanguage", ""),
        "idioma_titulo": item.get("titleLanguage", ""),
        "traducible": item.get("textTranslatable"),
        "categoria": item.get("CategoryType"),
        "categorias_recomendador": "|".join(item.get("diversificationLabels") or []),
        "id_recomendador": item.get("diversificationId"),
        "es_anuncio": item.get("isAd"),
        "aigc_tipo": item.get("aigcLabelType"),
        "aigc_moderacion": item.get("moderationAigcLabelType"),
        "es_aigc": item.get("IsAigc"),
        "aviso_ia_visible": item.get("ShowAIGC"),
        "aviso_ia": item.get("AIGCDescription", ""),
        "ia_creador_tema": ia.get("hasAITopic"),
        "ia_creador_motivo": ia.get("notEligibleReason"),
        "contenido_clasificado": item.get("isContentClassified"),
        "motivo_clasificacion": item.get("ContentClassificationReason", ""),
        "moderacion_estado": pen.get("status"),
        "moderacion_estado_video": pen.get("video_status"),
        "moderacion_revisado": pen.get("reviewed"),
        "moderacion_veredicto": pen.get("ec_global_verdict"),
        "moderacion_seguridad": pen.get("arb_content_safety_status"),
        "moderacion_penalizacion": pen.get("display_penalty_type"),
        "moderacion_json": _json(pen),
        "en_revision": item.get("isReviewing"),
        "prohibido": item.get("isProhibited"),
        "retirado": item.get("takeDown"),
        "aviso_json": _json(item.get("warnInfo")),
        "control_json": _json(item.get("item_control")),
        "lugar": poi.get("name", ""),
        "lugar_direccion": poi.get("address", ""),
        "lugar_ciudad": poi.get("city") or poi.get("fatherPoiName", ""),
        "lugar_tipo": poi.get("ttTypeNameTiny", ""),
        "anclas": "|".join(str(a.get("keyword") or a.get("type", "")) for a in item.get("anchors") or []),
        "stickers": "|".join(" ".join(s.get("stickerText") or []) for s in item.get("stickersOnItem") or []),
        "efectos": "|".join(e.get("name", "") for e in item.get("effectStickers") or []),
        "palabras_sugeridas": "|".join(item.get("suggestedWords") or []),
        "etiquetas_canal": _json(item.get("channelTags")),
        "item_original": item.get("originalItem"),
        "duet_de": duet.get("duetFromId", ""),
        "programado": item.get("scheduleTime"),
        "autor_uid": autor.get("id", ""),
        "autor_secuid": autor.get("secUid", ""),
        "autor_bio": autor.get("signature", ""),
        "autor_seguidos": (item.get("authorStats") or {}).get("followingCount"),
        "subtitulos_idiomas": "|".join(f"{x.get('LanguageCodeName', '')}:{x.get('Source', '')}" for x in subs),
        "subtitulos_urls": "|".join(x.get("Url", "") for x in subs),  # caducan: descargar el texto al capturar
        "fotos_urls": "|".join((f.get("imageURL") or {}).get("urlList", [""])[0] for f in fotos),
        "hashtags_ids": "|".join(f"{t.get('hashtagId')}:{t.get('hashtagName')}" for t in item.get("textExtra") or [] if t.get("hashtagName")),
        "audio_url": (item.get("music") or {}).get("playUrl", ""),
        **campos_forenses(item),  # siempre al final: las columnas anteriores no cambian de sitio
    }.items()}


COLUMNAS_AMPLIADAS = list(metadatos_ampliados({}))


# ---------------------------------------------------------------------------
# PLAYWRIGHT HELPERS (no dependen de config del scraper)
# ---------------------------------------------------------------------------

async def human_scroll(page) -> None:
    """Scroll humanizado alternando rueda, teclado y elemento para reducir detección."""
    technique = random.choice(["wheel", "wheel", "wheel", "keyboard", "element"])
    try:
        if technique == "wheel":
            await page.mouse.wheel(0, random.randint(400, 800))
        elif technique == "keyboard":
            key = random.choice(["PageDown", "PageDown", "End", "ArrowDown"])
            await page.keyboard.press(key)
            if key == "ArrowDown":
                for _ in range(random.randint(3, 8)):
                    await asyncio.sleep(0.1)
                    await page.keyboard.press("ArrowDown")
        elif technique == "element":
            videos = await page.query_selector_all('a[href*="/video/"]')
            if videos and len(videos) > 5:
                await videos[-1].scroll_into_view_if_needed()
    except Exception:
        try:
            await page.evaluate(f"window.scrollBy(0, {random.randint(400, 800)})")
        except Exception:
            pass


async def accept_cookies_banner(page):
    for sel in [
        'button:has-text("Aceptar todo")',
        'button:has-text("Accept all")',
        'button:has-text("I agree")',
    ]:
        try:
            b = await page.query_selector(sel)
            if b:
                await b.click()
                await asyncio.sleep(0.4)
                break
        except Exception:
            pass


async def handle_verification(page, max_wait: int = 90) -> bool:
    sels = [
        'div[id*="captcha"]',
        'div[class*="captcha"]',
        'div[class*="verify"]',
        'div[class*="secsdk"]',
    ]
    waited = 0
    while waited < max_wait:
        found = False
        for sel in sels:
            try:
                if await page.query_selector(sel):
                    found = True
                    break
            except Exception:
                pass
        if not found:
            return True
        await asyncio.sleep(1)
        waited += 1
    return False


async def detect_end_of_results(page) -> bool:
    selectors = [
        '[data-e2e="search-no-result"]',
        '[data-e2e="search-common-no-result"]',
        '[data-e2e="search-no-result-video"]',
    ]
    for sel in selectors:
        try:
            el = await page.query_selector(sel)
            if el and await el.is_visible():
                return True
        except Exception:
            pass
    try:
        el = await page.query_selector(
            "text=/no more results|no more videos|you\\'ve reached the end"
            "|no results|no videos|no se encontraron|sin resultados"
            "|fin de los resultados|no hay m[aá]s|has llegado al final/i"
        )
        if el and await el.is_visible():
            return True
    except Exception:
        pass
    return False


# ---------------------------------------------------------------------------
# GESTIÓN DE COOKIES Y CONTEXTO (parametrizados)
# ---------------------------------------------------------------------------

def resolve_cookies_path(base_dir: str) -> str:
    """Resuelve la ruta canónica del archivo de cookies de sesión de TikTok (SEC-01).

    Ubicación canónica: ``BASE_DIR/secrets/tiktok_cookies.json`` — una carpeta
    dedicada FUERA de ``data/``, que el usuario comparte/comprime junto a sus
    datasets. Mantener la sesión en ``data/`` arriesga filtrarla por accidente.

    Comportamiento (migración automática + fallback permanente):
      1. Crea ``secrets/`` si no existe.
      2. Si el archivo nuevo ya existe, lo devuelve.
      3. Si NO existe pero sí el legacy ``data/tiktok_cookies.json``, lo MIGRA
         con ``os.replace`` (move atómico). Si el move falla (permisos, disco,
         FS distinto), devuelve la ruta legacy como FALLBACK para no romper la
         autenticación viva del usuario.
      4. Si no existe ninguno, devuelve la ruta nueva (los guardados irán a
         ``secrets/`` desde el primer login).
    """
    secrets_dir = os.path.join(base_dir, "secrets")
    new_path = os.path.join(secrets_dir, "tiktok_cookies.json")
    legacy_path = os.path.join(base_dir, "data", "tiktok_cookies.json")

    try:
        os.makedirs(secrets_dir, exist_ok=True)
    except OSError:
        # No se pudo crear secrets/ → caer al legacy si existe, para no romper auth
        return legacy_path if os.path.exists(legacy_path) else new_path

    if os.path.exists(new_path):
        return new_path

    if os.path.exists(legacy_path):
        try:
            os.replace(legacy_path, new_path)
            print(f"🔐 Sesión migrada a {new_path} (fuera de data/)")
            return new_path
        except OSError:
            # Migración fallida → usar legacy para preservar la sesión existente
            return legacy_path

    return new_path


async def load_cookies(context, cookies_path: str) -> None:
    if os.path.exists(cookies_path):
        try:
            with open(cookies_path, "r", encoding="utf-8") as f:
                await context.add_cookies(json.load(f))
            print("🍪 Cookies cargadas")
        except Exception:
            pass


async def save_cookies(context, cookies_path: str) -> None:
    try:
        with open(cookies_path, "w", encoding="utf-8") as f:
            json.dump(await context.cookies(), f)
    except Exception:
        pass


def _release_profile_locks(profile_dir: str) -> None:
    """Elimina los archivos LOCK de instancia de Chrome que bloquean el arranque."""
    # Solo los dos LOCK críticos de instancia; los de leveldb son seguros
    critical = [
        os.path.join(profile_dir, "LOCK"),
        os.path.join(profile_dir, "Default", "LOCK"),
    ]
    for path in critical:
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError:
            pass


async def ensure_context(
    pw,
    profile_dir: str,
    cookies_path: str,
    headless: bool = False,
    block_media: bool = True,
):
    """Lanza un contexto persistente de Chromium con cookies y configuración antibot."""
    _release_profile_locks(profile_dir)

    # Usamos channel="chrome" (Chrome del sistema) porque el perfil fue creado
    # con Google Chrome y el Chromium bundled de Playwright es mucho más antiguo.
    # Con headless=False, Chromium bundled crashea al abrir un perfil de Chrome 143+.
    launch_kwargs = dict(
        user_data_dir=profile_dir,
        headless=headless,
        channel="chrome",
        args=[
            '--disable-blink-features=AutomationControlled',
            '--window-size=1280,900',
        ],
        ignore_default_args=['--enable-automation'],
        viewport={'width': 1280, 'height': 900},
        user_agent=(
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/134.0.0.0 Safari/537.36'
        ),
    )

    try:
        context = await pw.chromium.launch_persistent_context(**launch_kwargs)
    except Exception:
        await asyncio.sleep(2)
        _release_profile_locks(profile_dir)
        context = await pw.chromium.launch_persistent_context(**launch_kwargs)

    if block_media:
        async def _route_handler(route):
            if route.request.resource_type in {"image", "media", "font"}:
                return await route.abort()
            return await route.continue_()
        await context.route("**/*", _route_handler)

    page = await context.new_page()
    await load_cookies(context, cookies_path)
    await page.goto("https://www.tiktok.com", timeout=60000)
    await accept_cookies_banner(page)
    await handle_verification(page, 30)
    await save_cookies(context, cookies_path)
    await page.close()
    return context


# ---------------------------------------------------------------------------
# RECOLECCIÓN DE URLs (parámetros configurables por scraper)
# ---------------------------------------------------------------------------

async def collect_video_urls(
    context,
    url: str,
    max_scroll: int = 0,
    scroll_pause: tuple = (1.2, 2.0),
    no_new_limit: int = 3,
    cookies_path: str = None,
) -> list:
    """
    Recorre una página de búsqueda o hashtag de TikTok recolectando URLs de vídeos.

    Args:
        max_scroll: Límite de scrolls (0 = sin límite).
        scroll_pause: (min, max) segundos entre scrolls.
        no_new_limit: Ciclos sin nuevas URLs antes de considerar fin del contenido.
    """
    page = await context.new_page()
    print(f"🌍 Abriendo {url}")
    await page.goto(url, timeout=60000)
    await accept_cookies_banner(page)
    await handle_verification(page, 30)

    if "/search" in url:
        try:
            tab = await page.query_selector('button[data-e2e="search-tab-video"]')
            if tab:
                await tab.click()
                await asyncio.sleep(2)
        except Exception:
            pass

    video_urls = set()
    prev_count, no_new = 0, 0
    _max = max_scroll if max_scroll and max_scroll > 0 else None
    i = 0

    while True:
        i += 1
        for sel in ['a[href*="/video/"]', 'div[data-e2e*="video"] a']:
            try:
                for a in await page.query_selector_all(sel):
                    href = await a.get_attribute("href")
                    if href and "/video/" in href:
                        if href.startswith("//"): href = f"https:{href}"
                        elif href.startswith("/"): href = f"https://www.tiktok.com{href}"
                        clean = href.split("?")[0]
                        if is_valid_video_url(clean):
                            video_urls.add(clean)
            except Exception:
                pass

        cur = len(video_urls)
        total_label = str(_max) if _max else "∞"
        print(f"Scroll {i}/{total_label} -> {cur} videos")

        if await detect_end_of_results(page):
            print("✅ Fin del contenido (aviso de TikTok)")
            break

        if cur == prev_count:
            no_new += 1
            if no_new >= no_new_limit and cur > 0:
                print("✅ Fin del contenido")
                break
        else:
            no_new = 0

        if _max and i >= _max:
            break

        await human_scroll(page)
        await asyncio.sleep(random.uniform(*scroll_pause))
        prev_count = cur

    if cookies_path:
        await save_cookies(context, cookies_path)
    await page.close()
    return list(video_urls)
