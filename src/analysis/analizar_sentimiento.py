# -*- coding: utf-8 -*-
"""
analizar_sentimiento.py — Pipeline unificado de análisis multidimensional con IA.

Proveedores disponibles:
  roberta  → pysentimiento (local, sin API key, sin límites) · solo sentimiento
  groq     → Groq / llama-3.3-70b-versatile  (100K tokens/día gratis)
  mistral  → Mistral / open-mistral-nemo      (1B tokens/mes gratis, 2 req/min)

Uso desde menú:
    python src/analysis/analizar_sentimiento.py

Uso programático:
    from src.analysis.analizar_sentimiento import analizar_sentimiento
    df_result = analizar_sentimiento(df, csv_path, proveedor_id="mistral")

Salida (columnas añadidas al CSV):
  sentiment  POS / NEG / NEU / None
  bias       conservador / progresista / neutro / mixto / no_inferible
  archetype  arquetipo conductual (ver config/taxonomia_ia.py)
  intent     compra / info / difusion / castigo / ninguna
  pain_point dolor expresado (ver config/taxonomia_ia.py)
  sarcasm    True / False
  noise      True / False (sticker, solo-emoji u homónimo no relacionado)

Los proveedores LLM rellenan todas las columnas; RoBERTa (local) solo 'sentiment'
y 'noise'. El análisis es aditivo: la columna 'sentiment' se conserva para
mantener compatibilidad con informes anteriores.
"""

import os
import sys
import csv as _csv
import json
import time
import hashlib
from datetime import datetime

import pandas as pd
from dotenv import load_dotenv
import tkinter as tk
from tkinter import filedialog

# ─── Paths ──────────────────────────────────────────────────────────────────

BASE_DIR   = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CONFIG_DIR = os.path.join(BASE_DIR, "config")
DATA_DIR   = os.path.join(BASE_DIR, "data")

sys.path.insert(0, BASE_DIR)
load_dotenv(os.path.join(CONFIG_DIR, ".env"))

from config.taxonomia_ia import (  # noqa: E402
    SENTIMIENTOS, SESGOS, INTENCIONES, ARQUETIPOS, PAIN_POINTS,
    es_ruido, descripcion_arquetipos, descripcion_pain_points,
)

# ─── Configuración de proveedores ──────────────────────────────────────────

PROVEEDORES = {
    "roberta": {
        "nombre":      "RoBERTa (local)",
        "tipo":        "local",
        "modelo":      "finiteautomata/bertweet-base-sentiment-analysis",
        "sleep":       0,
        "descripcion": "Sin API key · Instantáneo · Sin límites · Solo sentimiento",
    },
    "groq": {
        "nombre":      "Groq",
        "tipo":        "openai_compat",
        "modelo":      "llama-3.3-70b-versatile",
        "api_key_env": "GROQ_API_KEY",
        "sleep":       0.5,
        "limite_diario": 100_000,
        "descripcion": "100K tokens/día · Rápido · análisis multidimensional",
    },
    "mistral": {
        "nombre":      "Mistral",
        "tipo":        "openai_compat",
        "modelo":      "open-mistral-nemo",
        "api_key_env": "MISTRAL_API_KEY",
        "sleep":       31,
        "limite_diario": 33_000_000,
        "descripcion": "1B tokens/mes · 2 req/min · análisis multidimensional",
    },
}

# Lote más pequeño que antes (50): cada comentario genera ahora 7 campos, no 1.
BATCH_SIZE      = 30
MAX_TOKENS      = 4000
TRUNC_TEXTO     = 350   # antes 200 — el sarcasmo/ironía se pierde al cortar corto
TELEMETRY_CSV   = os.path.join(DATA_DIR, "llm_telemetry.csv")
_TELEM_CAMPOS   = [
    "timestamp", "proveedor", "modelo", "n_comentarios",
    "tokens_in", "tokens_out", "latencia_ms", "finish_reason", "parse_ok",
]

# Columnas que produce el análisis (en orden). 'sentiment' va primero por compat.
DIM_CAMPOS = ["sentiment", "bias", "archetype", "intent", "pain_point", "sarcasm", "noise"]

PROMPT_MULTI = f"""Eres un analista de social listening para comentarios de TikTok en español.
Analiza CADA comentario y devuelve un objeto JSON con EXACTAMENTE estos campos:
- index: número del comentario (entero)
- sentiment: {"|".join(SENTIMIENTOS)} (POS=positivo/apoyo, NEG=crítica/insulto/queja, NEU=neutro/pregunta)
- bias: {"|".join(SESGOS)} (sesgo político del autor; usa 'no_inferible' si no se deduce)
- archetype: uno de:
{descripcion_arquetipos()}
- intent: {"|".join(INTENCIONES)} (compra=interés en producto/link, difusion=quiere compartir, castigo=pide sanción)
- pain_point: uno de:
{descripcion_pain_points()}
- sarcasm: true|false (true si hay ironía, burla o sarcasmo aunque el texto parezca literal; señales: 💀, exageración)
- noise: true|false (true si es spam, sticker, solo-emoji u homónimo sin relación con el tema)

REGLAS:
- Usa el CONTEXTO de los vídeos para desambiguar ironía y sesgo.
- No inventes el sesgo: si dudas, usa 'no_inferible'.
- Usa SOLO los valores de las listas. Si nada encaja, usa 'otro' (archetype) o 'ninguno' (pain_point).
- Devuelve SOLO un OBJETO JSON con la clave "resultados", cuyo valor es un array con un objeto por comentario, en el MISMO orden. Sin markdown, sin texto extra, sin explicaciones.

Ejemplo de formato exacto:
{{"resultados": [{{"index": 0, "sentiment": "NEG", "bias": "conservador", "archetype": "meme_fiscal", "intent": "castigo", "pain_point": "doble_rasero_fiscal", "sarcasm": true, "noise": false}}]}}"""


# ─── Excepciones ────────────────────────────────────────────────────────────

class RateLimitDiaria(Exception):
    """Límite de tokens por día agotado."""


# ─── Telemetría ─────────────────────────────────────────────────────────────

def _log_telemetria(**kwargs):
    """Añade una fila al CSV acumulativo de telemetría LLM."""
    fila = {k: kwargs.get(k, "") for k in _TELEM_CAMPOS}
    existe = os.path.exists(TELEMETRY_CSV)
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(TELEMETRY_CSV, "a", newline="", encoding="utf-8") as f:
        w = _csv.DictWriter(f, fieldnames=_TELEM_CAMPOS)
        if not existe:
            w.writeheader()
        w.writerow(fila)


# ─── Utilidades comunes ─────────────────────────────────────────────────────

def detectar_columna_texto(df):
    for col in ['texto', 'comment_text', 'comentario_texto', 'text', 'comentario', 'content', 'body']:
        if col in df.columns:
            return col
    for col in df.columns:
        if any(k in col.lower() for k in ('text', 'texto', 'comment')):
            return col
    return None


def detectar_columna_id(df):
    for col in ['comment_id', 'comentario_id', 'cid', 'id']:
        if col in df.columns:
            return col
    return None


def clave_estable(row, col_id, col_texto):
    if col_id:
        val = row.get(col_id)
        if val is not None and str(val).strip() not in ('', 'nan', 'None'):
            return str(val).strip()
    return hashlib.md5(str(row[col_texto]).encode('utf-8', errors='replace')).hexdigest()[:16]


def _migrar_checkpoint_si_necesario(ckpt_path, ckpt_data, df_len):
    """Detecta checkpoints con claves posicionales (formato antiguo) y los reinicia."""
    if not ckpt_data:
        return ckpt_data
    sample = list(ckpt_data.keys())[:20]
    try:
        nums = [int(k) for k in sample]
        if all(0 <= n < max(df_len * 3, 100_000) for n in nums):
            import shutil
            backup = ckpt_path.replace(".json", "_posicional_backup.json")
            shutil.copy2(ckpt_path, backup)
            print("   ⚠️  Checkpoint en formato antiguo (claves posicionales) detectado.")
            print(f"   ℹ️  Copia guardada en: {os.path.basename(backup)}")
            print("   🔄  Reiniciando con claves estables (ID o hash de texto).")
            return {}
    except (ValueError, TypeError):
        pass
    return ckpt_data


def limpiar_json(texto):
    t = texto.strip()
    for prefix in ("```json", "```"):
        if t.startswith(prefix):
            t = t[len(prefix):]
    if t.endswith("```"):
        t = t[:-3]
    return t.strip()


def _extraer_json(texto):
    """Extrae el bloque JSON (objeto o array) de la respuesta, ignorando
    preámbulos en lenguaje natural (p.ej. 'Aquí están los objetos JSON:')."""
    t = limpiar_json(texto)
    inicios = [p for p in (t.find("{"), t.find("[")) if p != -1]
    if not inicios:
        return t
    i = min(inicios)
    j = max(t.rfind("}"), t.rfind("]"))
    if j > i:
        return t[i:j + 1]
    return t


def get_checkpoint_path(csv_file, proveedor_id):
    return csv_file.replace(".csv", f"_{proveedor_id}_checkpoint.json")


def load_checkpoint(checkpoint_path):
    if os.path.exists(checkpoint_path):
        with open(checkpoint_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"   ✓ Checkpoint encontrado: {len(data):,} comentarios ya procesados")
        return data
    return {}


def save_checkpoint(checkpoint_path, etiquetas_dict):
    with open(checkpoint_path, "w", encoding="utf-8") as f:
        json.dump(etiquetas_dict, f, ensure_ascii=False)


# ─── Esquema multidimensional ────────────────────────────────────────────────

def _obj_defecto(noise=False):
    """Objeto por defecto (seguro) para todas las dimensiones."""
    return {
        "sentiment": "NEU", "bias": "no_inferible", "archetype": "otro",
        "intent": "ninguna", "pain_point": "ninguno", "sarcasm": False, "noise": noise,
    }


def _es_completo(v):
    """True si la entrada del checkpoint ya tiene el análisis multidimensional."""
    return isinstance(v, dict) and "bias" in v


def _parsear_item(item):
    """Valida un objeto del modelo contra los enums cerrados."""
    obj = _obj_defecto()
    s = str(item.get("sentiment", item.get("label", "NEU"))).upper()
    obj["sentiment"] = s if s in SENTIMIENTOS else "NEU"
    b = str(item.get("bias", "no_inferible")).lower()
    obj["bias"] = b if b in SESGOS else "no_inferible"
    a = str(item.get("archetype", "otro")).lower()
    obj["archetype"] = a if a in ARQUETIPOS else "otro"
    it = str(item.get("intent", "ninguna")).lower()
    obj["intent"] = it if it in INTENCIONES else "ninguna"
    p = str(item.get("pain_point", "ninguno")).lower()
    obj["pain_point"] = p if p in PAIN_POINTS else "ninguno"
    obj["sarcasm"] = bool(item.get("sarcasm", False))
    obj["noise"] = bool(item.get("noise", False))
    return obj


def _parsear_respuesta(texto_resp, n):
    """Parsea la respuesta del modelo en una lista de n objetos validados.

    Acepta tanto un objeto {"resultados": [...]} (modo json_object) como un
    array suelto [...] (compatibilidad)."""
    datos = json.loads(_extraer_json(texto_resp))
    if isinstance(datos, dict):
        datos = (datos.get("resultados") or datos.get("results")
                 or datos.get("comentarios") or [])
    if not isinstance(datos, list):
        raise ValueError("La respuesta no contiene una lista de resultados")
    objs = [_obj_defecto() for _ in range(n)]
    for pos, item in enumerate(datos):
        if not isinstance(item, dict):
            continue
        idx = item.get("index")
        if not isinstance(idx, int) or not (0 <= idx < n):
            idx = pos  # si el modelo no numeró bien, usa el orden de aparición
        if 0 <= idx < n:
            objs[idx] = _parsear_item(item)
    return objs


def construir_mensaje_usuario(textos, vid_labels, contexto_map):
    """Construye el cuerpo del mensaje: bloque de contexto + comentarios numerados."""
    lineas = []
    if contexto_map:
        lineas.append("CONTEXTO DE LOS VÍDEOS (para desambiguar ironía y sesgo):")
        for lbl, ctx in contexto_map.items():
            extra = f" | hashtags: {ctx['hashtags']}" if ctx.get("hashtags") else ""
            lineas.append(f"[{lbl}] {ctx['copy']}{extra}")
        lineas.append("")
    lineas.append("Comentarios:")
    for i, (t, lbl) in enumerate(zip(textos, vid_labels)):
        pref = f"[{lbl}] " if (contexto_map and lbl) else ""
        lineas.append(f"{i}. {pref}{t[:TRUNC_TEXTO]}")
    return f"{PROMPT_MULTI}\n\n" + "\n".join(lineas)


# ─── Contexto de los vídeos (copy + hashtags por video_id) ───────────────────

def cargar_contexto_videos(csv_file, df_f):
    """Busca el CSV de vídeos asociado y devuelve {video_id: {copy, hashtags}}.

    Best-effort: si no encuentra el CSV de vídeos, devuelve {} y el análisis
    continúa sin contexto (degradación elegante)."""
    if 'video_id' not in df_f.columns:
        return {}

    base = os.path.basename(csv_file)
    dir_ = os.path.dirname(csv_file)
    candidatos = []
    for patron in ("_comentarios_api.csv", "_comentarios.csv", "_comments.csv"):
        if patron in base:
            candidatos.append(os.path.join(dir_, base.replace(patron, ".csv")))
    # Búsqueda por prefijo de proyecto: primer *_videos.csv que comparta inicio
    prefijo = base.split("_videos")[0].split("_comentarios")[0]
    try:
        for f in os.listdir(dir_):
            if f.startswith(prefijo) and f.endswith("_videos.csv"):
                candidatos.append(os.path.join(dir_, f))
    except OSError:
        pass

    for ruta in candidatos:
        if not os.path.exists(ruta):
            continue
        try:
            cols = pd.read_csv(ruta, nrows=0, encoding="utf-8-sig").columns.tolist()
            if 'video_desc' not in cols:
                continue
            usecols = ['video_id', 'video_desc'] + (['hashtags'] if 'hashtags' in cols else [])
            dfv = pd.read_csv(ruta, usecols=usecols, low_memory=False, encoding="utf-8-sig")
            ctx = {}
            for _, r in dfv.iterrows():
                copy = str(r.get('video_desc', '') or '')[:160].replace("\n", " ").strip()
                htags = str(r.get('hashtags', '') or '')[:120].replace("|", " ").strip() if 'hashtags' in usecols else ""
                ctx[str(r['video_id'])] = {"copy": copy, "hashtags": htags}
            if ctx:
                print(f"   🎬 Contexto de vídeos: {os.path.basename(ruta)} ({len(ctx):,} vídeos)")
                return ctx
        except Exception:
            continue
    print("   ℹ️  Sin CSV de vídeos asociado — el análisis continúa sin contexto.")
    return {}


# ─── Proveedor: RoBERTa local (solo sentimiento) ─────────────────────────────

def clasificar_roberta(df_f, col_texto):
    """Clasifica con pysentimiento (RoBERTa). Sin API, instantáneo. Solo POS/NEG/NEU."""
    try:
        from pysentimiento import create_analyzer
    except ImportError:
        print("   ❌ pysentimiento no instalado. Ejecuta: pip install pysentimiento")
        return None

    print("   Cargando modelo RoBERTa (primera vez puede tardar ~30s)...")
    analyzer = create_analyzer(task="sentiment", lang="es")

    etiquetas = []
    total = len(df_f)
    for i, texto in enumerate(df_f[col_texto].fillna("")):
        try:
            result = analyzer.predict(str(texto)[:512])
            etiquetas.append(result.output.upper())
        except Exception:
            etiquetas.append(None)
        if (i + 1) % 500 == 0 or (i + 1) == total:
            print(f"   Clasificados: {i+1:,}/{total:,}", end="\r")
    print()
    return etiquetas


# ─── Proveedor: OpenAI-compatible (Groq / Mistral) ──────────────────────────

def _crear_cliente_openai_compat(proveedor_id, api_key):
    if proveedor_id == "groq":
        from groq import Groq
        return Groq(api_key=api_key)
    elif proveedor_id == "mistral":
        try:
            from mistralai import Mistral
        except ImportError:
            from mistralai.client import Mistral
        return Mistral(api_key=api_key)
    raise ValueError(f"Proveedor desconocido: {proveedor_id}")


def _llamar_api_openai_compat(client, proveedor_id, modelo, mensajes, max_tokens):
    """Llama a la API y devuelve (texto, finish_reason, tok_in, tok_out).

    Fuerza salida JSON con response_format=json_object: evita que el modelo
    anteponga preámbulos o rechace la tarea (problema típico de modelos pequeños)."""
    json_fmt = {"type": "json_object"}
    if proveedor_id == "groq":
        resp = client.chat.completions.create(
            model=modelo, messages=mensajes,
            temperature=0.2, top_p=0.9, max_tokens=max_tokens,
            response_format=json_fmt,
        )
        u = resp.usage or {}
        return (resp.choices[0].message.content.strip(),
                resp.choices[0].finish_reason,
                getattr(u, "prompt_tokens", 0),
                getattr(u, "completion_tokens", 0))
    elif proveedor_id == "mistral":
        resp = client.chat.complete(
            model=modelo, messages=mensajes,
            temperature=0.2, max_tokens=max_tokens,
            response_format=json_fmt,
        )
        u = resp.usage or {}
        return (resp.choices[0].message.content.strip(),
                resp.choices[0].finish_reason,
                getattr(u, "prompt_tokens", 0),
                getattr(u, "completion_tokens", 0))


def clasificar_lote_openai_compat(client, proveedor_id, modelo, prompt_user, n, reintentos=3):
    """Clasifica un lote. Devuelve lista de n objetos dict o None.

    Reintenta con backoff si la respuesta viene vacía, truncada o no parsea
    (modelos pequeños a veces devuelven texto vacío o no-JSON puntualmente)."""
    mensajes = [
        {"role": "system", "content": "Eres un analista de social listening experto en español. Respondes SOLO con un objeto JSON."},
        {"role": "user",   "content": prompt_user},
    ]
    for intento in range(1, reintentos + 1):
        t0 = time.time()
        try:
            texto_resp, finish_reason, tok_in, tok_out = _llamar_api_openai_compat(
                client, proveedor_id, modelo, mensajes, max_tokens=MAX_TOKENS)
            latencia_ms = int((time.time() - t0) * 1000)

            if finish_reason == "length":
                _log_telemetria(timestamp=datetime.now().isoformat(), proveedor=proveedor_id,
                                modelo=modelo, n_comentarios=n, tokens_in=tok_in,
                                tokens_out=tok_out, latencia_ms=latencia_ms,
                                finish_reason=finish_reason, parse_ok=False)
                print(f"   ⚠️ Respuesta truncada (length), reintento {intento}/{reintentos}…")
                time.sleep(2 * intento)
                continue

            objs = _parsear_respuesta(texto_resp, n)
            _log_telemetria(timestamp=datetime.now().isoformat(), proveedor=proveedor_id,
                            modelo=modelo, n_comentarios=n, tokens_in=tok_in,
                            tokens_out=tok_out, latencia_ms=latencia_ms,
                            finish_reason=finish_reason, parse_ok=True)
            return objs

        except (json.JSONDecodeError, ValueError) as e:
            # Respuesta vacía o no-JSON: reintentar
            print(f"   ⚠️ Respuesta no-JSON ({str(e)[:60]}), reintento {intento}/{reintentos}…")
            time.sleep(2 * intento)
            continue
        except Exception as e:
            err = str(e)
            if "rate_limit_exceeded" in err and any(k in err for k in ("per day", "TPD", "per_day")):
                raise RateLimitDiaria(err)
            if "model_decommissioned" in err or "decommissioned" in err:
                raise RuntimeError(f"\n❌ MODELO DADO DE BAJA: {modelo}")
            # Errores transitorios (5xx, 429 por minuto, red): backoff y reintento
            if any(k in err.lower() for k in ("429", "500", "502", "503", "timeout", "overloaded")):
                wait = 5 * intento
                print(f"   ⚠️ Error transitorio ({err[:50]}), espera {wait}s (intento {intento}/{reintentos})…")
                time.sleep(wait)
                continue
            print(f"   ⚠️ Error puntual: {err[:150]}")
            return None

    print(f"   ❌ Lote omitido tras {reintentos} intentos.")
    return None


# ─── Dispatcher principal ────────────────────────────────────────────────────

def analizar_sentimiento(df, csv_file, proveedor_id):
    """Analiza (multidimensional) el DataFrame con el proveedor indicado.

    Devuelve el DataFrame con las columnas de DIM_CAMPOS, o None si error.
    """
    cfg = PROVEEDORES.get(proveedor_id)
    if cfg is None:
        print(f"❌ Proveedor desconocido: {proveedor_id}")
        return None

    print(f"\n{'─'*60}")
    print(f"  Proveedor : {cfg['nombre']}")
    print(f"  Tipo      : {cfg['tipo']}")
    if cfg["tipo"] != "local":
        print(f"  Modelo    : {cfg['modelo']}")
    print(f"{'─'*60}")

    # Normaliza BOM en cabeceras (algunos CSV vienen con '﻿' en la 1ª columna)
    df = df.rename(columns=lambda c: c.lstrip("﻿") if isinstance(c, str) else c)

    col_texto = detectar_columna_texto(df)
    if col_texto is None:
        print(f"❌ Columna de texto no encontrada. Columnas: {list(df.columns)}")
        return None
    print(f"  Columna texto : '{col_texto}'")

    if 'is_reply' in df.columns:
        df_f = df[df['is_reply'] == 0].reset_index(drop=True)
        print(f"  Comentarios directos: {len(df_f):,} (de {len(df):,} totales)")
    else:
        df_f = df.reset_index(drop=True)
        print(f"  Comentarios: {len(df_f):,}")

    if len(df_f) == 0:
        print("  ⚠️ No hay comentarios para analizar")
        return None

    # ── RoBERTa local (solo sentimiento, sin checkpoint) ─────────────────────
    if cfg["tipo"] == "local":
        etiquetas_lista = clasificar_roberta(df_f, col_texto)
        if etiquetas_lista is None:
            return None
        df_f['sentiment'] = etiquetas_lista
        for campo in ["bias", "archetype", "intent", "pain_point", "sarcasm"]:
            df_f[campo] = None
        df_f['noise'] = [es_ruido(t) for t in df_f[col_texto]]
        _guardar_y_mostrar(df_f, csv_file, proveedor_id)
        return df_f

    # ── APIs externas (Groq / Mistral) ───────────────────────────────────────
    api_key = os.getenv(cfg.get("api_key_env", ""), "")
    if not api_key:
        print(f"  ❌ {cfg.get('api_key_env')} no configurada en config/.env")
        return None

    col_id = detectar_columna_id(df_f)
    claves = [clave_estable(df_f.iloc[i].to_dict(), col_id, col_texto)
              for i in range(len(df_f))]
    fuente = f"columna '{col_id}'" if col_id else "hash MD5 del texto"
    print(f"  Clave checkpoint  : {fuente}")

    ckpt_path = get_checkpoint_path(csv_file, proveedor_id)
    etiquetas = load_checkpoint(ckpt_path)
    etiquetas = _migrar_checkpoint_si_necesario(ckpt_path, etiquetas, len(df_f))

    pendientes = [i for i in range(len(df_f)) if not _es_completo(etiquetas.get(claves[i]))]
    print(f"  Por procesar      : {len(pendientes):,}")

    # Pre-filtro de ruido/homónimos (no gasta tokens)
    n_ruido = 0
    restantes = []
    for idx in pendientes:
        if es_ruido(df_f.loc[idx, col_texto]):
            etiquetas[claves[idx]] = _obj_defecto(noise=True)
            n_ruido += 1
        else:
            restantes.append(idx)
    pendientes = restantes
    if n_ruido:
        print(f"  🧹 Pre-filtro de ruido: {n_ruido:,} marcados (sticker/emoji/homónimo)")
        save_checkpoint(ckpt_path, etiquetas)

    # Ordenar por vídeo para coherencia de contexto entre lotes
    if 'video_id' in df_f.columns:
        pendientes.sort(key=lambda i: str(df_f.loc[i, 'video_id']))

    n_pendientes = len(pendientes)

    # Estimación de tiempo
    if proveedor_id == "groq":
        tokens_est = n_pendientes * 60
        dias_est = tokens_est / cfg["limite_diario"]
        if dias_est > 1:
            print(f"  ⏱️  ~{dias_est:.0f} días con Groq free ({tokens_est:,} tokens / 100K/día)")
    elif proveedor_id == "mistral":
        horas_est = (n_pendientes / BATCH_SIZE) * cfg["sleep"] / 3600
        print(f"  ⏱️  ~{horas_est:.1f}h con Mistral free (2 req/min)")

    # Contexto de los vídeos (copy + hashtags)
    contexto_videos = cargar_contexto_videos(csv_file, df_f)

    # Crear cliente
    try:
        if cfg["tipo"] == "openai_compat":
            client = _crear_cliente_openai_compat(proveedor_id, api_key)
        else:
            raise ValueError(f"Tipo de proveedor no soportado: {cfg['tipo']}")
    except ImportError:
        pkg_map = {"groq": "groq", "mistral": "mistralai"}
        print(f"  ❌ Librería no instalada. Ejecuta: pip install {pkg_map.get(proveedor_id, '')}")
        return None

    tiene_vid = 'video_id' in df_f.columns and bool(contexto_videos)

    # Bucle de clasificación
    try:
        for lote_num, i in enumerate(range(0, n_pendientes, BATCH_SIZE)):
            indices_lote = pendientes[i:i + BATCH_SIZE]
            textos = [str(df_f.loc[idx, col_texto])[:TRUNC_TEXTO] for idx in indices_lote]

            # Etiquetas de vídeo + mapa de contexto del lote
            contexto_map, vid_labels = {}, []
            if tiene_vid:
                label_de_vid = {}
                for idx in indices_lote:
                    vid = str(df_f.loc[idx, 'video_id'])
                    if vid not in label_de_vid:
                        lbl = f"v{len(label_de_vid)+1}"
                        label_de_vid[vid] = lbl
                        ctx = contexto_videos.get(vid)
                        if ctx and (ctx["copy"] or ctx["hashtags"]):
                            contexto_map[lbl] = ctx
                    vid_labels.append(label_de_vid[vid])
            else:
                vid_labels = [""] * len(indices_lote)

            prompt_user = construir_mensaje_usuario(textos, vid_labels, contexto_map)
            print(f"  Lote {lote_num+1:>4}: {len(textos)} coment...", end=" ", flush=True)

            resultado = clasificar_lote_openai_compat(
                client, proveedor_id, cfg["modelo"], prompt_user, len(indices_lote))

            if resultado is not None:
                for idx, obj in zip(indices_lote, resultado):
                    etiquetas[claves[idx]] = obj
                print(f"✓  (procesados: {len(etiquetas):,})")
            else:
                print("⚠️  omitido — error de API, no se escribe nada")

            if (lote_num + 1) % 10 == 0:
                save_checkpoint(ckpt_path, etiquetas)
                print(f"  💾 Checkpoint guardado ({len(etiquetas):,})")

            time.sleep(cfg["sleep"])

    except RateLimitDiaria:
        print("\n⏸️  LÍMITE DIARIO ALCANZADO")
        print(f"   Procesados: {len(etiquetas):,} / {len(df_f):,}")
        save_checkpoint(ckpt_path, etiquetas)
        print("   ✅ Checkpoint guardado. Vuelve mañana para continuar.")
        return None
    except KeyboardInterrupt:
        print("\n⏹️  Interrumpido por el usuario.")
        save_checkpoint(ckpt_path, etiquetas)
        print(f"   ✅ {len(etiquetas):,} comentarios guardados en checkpoint.")
        return None

    save_checkpoint(ckpt_path, etiquetas)
    _aplicar_columnas(df_f, claves, etiquetas)
    _guardar_y_mostrar(df_f, csv_file, proveedor_id)
    return df_f


def _campo(obj, campo):
    """Extrae un campo del objeto del checkpoint (tolera formato antiguo string)."""
    if isinstance(obj, dict):
        return obj.get(campo)
    if isinstance(obj, str) and campo == "sentiment":
        return obj
    return None


def _aplicar_columnas(df_f, claves, etiquetas):
    """Vuelca las dimensiones del checkpoint a columnas del DataFrame."""
    for campo in DIM_CAMPOS:
        df_f[campo] = [_campo(etiquetas.get(k), campo) for k in claves]


def _guardar_y_mostrar(df_f, csv_file, proveedor_id):
    """Muestra estadísticas multidimensionales y guarda el CSV resultado."""
    total = len(df_f)
    clasificados = df_f['sentiment'].notna().sum()
    sin_clasificar = total - clasificados

    print(f"\n  Resultados ({clasificados:,} clasificados / {total:,} total):")
    print("  · Sentimiento:")
    for label, count in df_f['sentiment'].value_counts(dropna=True).items():
        bar = "█" * int(count / total * 30)
        print(f"      {label}: {count:>7,} ({count/total*100:.1f}%) {bar}")

    if 'bias' in df_f.columns and df_f['bias'].notna().any():
        print("  · Sesgo político:")
        for label, count in df_f['bias'].value_counts(dropna=True).items():
            print(f"      {label}: {count:>7,} ({count/total*100:.1f}%)")

    if 'noise' in df_f.columns:
        n_noise = int(df_f['noise'].fillna(False).astype(bool).sum())
        if n_noise:
            print(f"  · Ruido filtrado: {n_noise:,} ({n_noise/total*100:.1f}%)")
    if 'sarcasm' in df_f.columns and df_f['sarcasm'].notna().any():
        n_sarc = int(df_f['sarcasm'].fillna(False).astype(bool).sum())
        print(f"  · Sarcasmo/ironía: {n_sarc:,} ({n_sarc/total*100:.1f}%)")

    if sin_clasificar > 0:
        print(f"  ⚠️  Sin clasificar: {sin_clasificar:,} ({sin_clasificar/total*100:.1f}%)"
              " — errores de API, vuelve a ejecutar para reintentar")

    sufijo = "roberta" if proveedor_id == "roberta" else proveedor_id
    output_csv = csv_file.replace(".csv", f"_con_sentimiento_{sufijo}.csv")
    df_f.to_csv(output_csv, index=False, encoding="utf-8")
    print(f"\n  ✅ CSV guardado: {os.path.basename(output_csv)}")


# ─── Menú interactivo ────────────────────────────────────────────────────────

def seleccionar_proveedor():
    print("\n" + "=" * 60)
    print("  ¿Qué proveedor de IA usar para el análisis?")
    print("=" * 60)
    ids = list(PROVEEDORES.keys())
    for i, pid in enumerate(ids, 1):
        cfg = PROVEEDORES[pid]
        if cfg["tipo"] == "local":
            estado = "✅ Sin API key necesaria"
        else:
            api_key = os.getenv(cfg.get("api_key_env", ""), "")
            estado = "✅ API key configurada" if api_key else "❌ Sin API key"
        print(f"  {i}. {cfg['nombre']:20s} — {cfg['descripcion']}")
        print(f"       {estado}")
    print("=" * 60)

    while True:
        opcion = input(f"  Selecciona (1-{len(ids)}): ").strip()
        try:
            idx = int(opcion) - 1
            if 0 <= idx < len(ids):
                return ids[idx]
        except ValueError:
            pass
        print(f"  Opción no válida. Introduce un número del 1 al {len(ids)}.")


def main():
    print("=" * 60)
    print("  ANÁLISIS MULTIDIMENSIONAL CON IA")
    print("  Sentimiento · Sesgo · Arquetipo · Intención · Pain points")
    print("=" * 60)

    # Acepta ruta como argumento (lo pasa el menú cuando hay proyecto activo)
    if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]):
        csv_file = sys.argv[1]
        print(f"\n  Archivo: {os.path.basename(csv_file)}")
    else:
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        csv_file = filedialog.askopenfilename(
            title="Selecciona CSV de comentarios",
            filetypes=[("CSV Files", "*.csv")],
            initialdir=DATA_DIR,
        )
        root.destroy()

    if not csv_file:
        print("Operación cancelada.")
        return

    print(f"\n  Archivo: {os.path.basename(csv_file)}")
    df = pd.read_csv(csv_file)
    print(f"  Filas  : {len(df):,}")

    proveedor_id = seleccionar_proveedor()
    analizar_sentimiento(df, csv_file, proveedor_id)
    print("\n✅ Proceso finalizado.")


if __name__ == "__main__":
    main()
