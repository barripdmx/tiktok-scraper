"""Compara el orden web de @jbarri con las fechas de su exportación oficial.

Sin --exportacion genera el informe preliminar de capturas web. El ZIP/JSON
privado se lee en memoria y nunca se copia ni se incluye en los resultados.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "outputs" / "estudio_orden_jbarri_20261026"
KEYS = {
    "seguidores": {"follower", "followers", "followerlist", "fanslist", "fans"},
    "seguidos": {"following", "followinglist", "followings"},
}
TABLE_FIELDS = ["lista", "posicion_respuesta", "pagina", "posicion_en_pagina", "user_id",
                "username_web", "username_exportacion", "fecha_seguimiento_exportacion_utc", "estado_cruce",
                "cursor_enviado", "minCursor", "maxCursor", "observed_at", "evidencia"]


def key(value: str) -> str:
    return re.sub(r"[^a-z]", "", str(value).casefold())


def handle(value: str) -> str:
    text = str(value or "").strip().removeprefix("@").casefold()
    return text if re.fullmatch(r"[a-z0-9_.]{1,24}", text) else ""


def parse_date(value: object) -> str:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        date = datetime.fromtimestamp(value, timezone.utc)
    else:
        raw = str(value or "").strip()
        if not raw:
            return ""
        raw = re.sub(r"\s+UTC$", "+00:00", raw, flags=re.I).replace("Z", "+00:00")
        try:
            date = datetime.fromisoformat(raw)
        except ValueError:
            return ""
        if date.tzinfo is None:
            date = date.replace(tzinfo=timezone.utc)
    return date.astimezone(timezone.utc).isoformat(timespec="seconds")


def leaf_list(node: object) -> list[dict] | None:
    if isinstance(node, list) and all(isinstance(row, dict) for row in node):
        return node
    if isinstance(node, dict):
        for name, value in node.items():
            if key(name) in {"fanslist", "followerlist", "followinglist", "following", "list", "entries", "data"}:
                result = leaf_list(value)
                if result is not None:
                    return result
    return None


def candidates(node: object, path: tuple[str, ...] = ()) -> list[tuple[str, str, list[dict]]]:
    found = []
    if isinstance(node, dict):
        for name, value in node.items():
            new_path = (*path, str(name))
            direction = next((d for d, names in KEYS.items() if key(name) in names), None)
            if direction:
                rows = leaf_list(value)
                if rows is not None:
                    found.append((direction, "/".join(new_path), rows))
                    continue
            found.extend(candidates(value, new_path))
    elif isinstance(node, list):
        for value in node:
            if isinstance(value, dict):
                found.extend(candidates(value, path))
    return found


def parse_entry(row: dict) -> tuple[str, str]:
    fields = {key(name): value for name, value in row.items()}
    username = handle(fields.get("username") or fields.get("uniqueid") or fields.get("user"))
    date = parse_date(fields.get("date") or fields.get("followdate") or fields.get("timestamp"))
    return username, date


def read_export(path: Path) -> tuple[dict[str, dict[str, str]], dict]:
    if not path.is_file():
        raise FileNotFoundError(path)
    sha = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            sha.update(block)
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            choices = [info for info in archive.infolist() if not info.is_dir()
                       and Path(info.filename).name.casefold() in {"user_data_tiktok.json", "user_data.json"}]
            if len(choices) != 1:
                raise ValueError("El ZIP debe contener un único user_data_tiktok.json o user_data.json.")
            data = json.loads(archive.read(choices[0]).decode("utf-8-sig"))
    else:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    found = candidates(data)
    result: dict[str, dict[str, str]] = {}
    metadata = {"archivo_sha256": sha.hexdigest(), "archivo_nombre": path.name, "listas": {}}
    for direction in KEYS:
        options = []
        for candidate_direction, section, rows in found:
            if candidate_direction != direction:
                continue
            values = [parsed for item in rows if (parsed := parse_entry(item))[0]]
            options.append((section, values))
        options.sort(key=lambda item: len(item[1]), reverse=True)
        if not options:
            metadata["listas"][direction] = {"estado": "ausente"}
            result[direction] = {}
            continue
        section, values = options[0]
        if len(options) > 1 and len(options[1][1]) == len(values) and options[1][1] != values:
            raise ValueError(f"Hay dos listas {direction} incompatibles en la exportación.")
        grouped: dict[str, set[str]] = {}
        for username, date in values:
            grouped.setdefault(username, set()).add(date)
        ambiguous = {u for u, dates in grouped.items() if len(dates) != 1 or "" in dates}
        result[direction] = {u: next(iter(dates)) for u, dates in grouped.items() if u not in ambiguous}
        metadata["listas"][direction] = {"estado": "disponible", "seccion": section,
                                         "filas": len(values), "fechas_validas": len(result[direction]),
                                         "ambiguas_o_sin_fecha": len(ambiguous)}
    return result, metadata


def read_capture(folder: Path, direction: str) -> list[dict[str, str]]:
    with (folder / f"{direction}.csv").open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def compare(web: list[dict[str, str]], dated: dict[str, str], direction: str) -> tuple[list[dict], dict]:
    web_counts: dict[str, int] = {}
    for row in web:
        name = handle(row["username"])
        web_counts[name] = web_counts.get(name, 0) + 1
    table = []
    matched = []
    for row in web:
        name = handle(row["username"])
        if not name:
            status = "usuario_web_invalido"
        elif web_counts[name] > 1:
            status = "duplicado_web"
        elif name not in dated:
            status = "sin_cruce_exportacion"
        else:
            status = "fecha_disponible"
        date = dated.get(name, "") if status == "fecha_disponible" else ""
        table.append({"lista": direction, "posicion_respuesta": row["posicion_respuesta"],
                      "pagina": row["pagina"], "posicion_en_pagina": row["posicion_en_pagina"],
                      "user_id": row["user_id"], "username_web": row["username"],
                      "username_exportacion": name if date else "",
                      "fecha_seguimiento_exportacion_utc": date, "estado_cruce": status,
                      "cursor_enviado": row["cursor_enviado"], "minCursor": row["minCursor"],
                      "maxCursor": row["maxCursor"], "observed_at": row["observed_at"],
                      "evidencia": row["evidencia"]})
        if date:
            matched.append((int(row["posicion_respuesta"]), date, name))
    export_only = sorted(set(dated) - set(web_counts))
    for name in export_only:
        table.append({"lista": direction, "posicion_respuesta": "", "pagina": "",
                      "posicion_en_pagina": "", "user_id": "", "username_web": "",
                      "username_exportacion": name,
                      "fecha_seguimiento_exportacion_utc": dated[name],
                      "estado_cruce": "solo_exportacion", "cursor_enviado": "",
                      "minCursor": "", "maxCursor": "", "observed_at": "", "evidencia": ""})
    inversions = ties = pairs = 0
    examples = []
    for i, (left_pos, left_date, left_name) in enumerate(matched):
        for right_pos, right_date, right_name in matched[i + 1:]:
            if left_date == right_date:
                ties += 1
                continue
            pairs += 1
            if left_date < right_date:
                inversions += 1
                if len(examples) < 20:
                    examples.append({"arriba": f"@{left_name}", "posicion_arriba": left_pos,
                                     "fecha_arriba": left_date, "abajo": f"@{right_name}",
                                     "posicion_abajo": right_pos, "fecha_abajo": right_date})
    window_checked = window_inside = 0
    window_outside = []
    for row in table:
        date = row["fecha_seguimiento_exportacion_utc"]
        lower, upper = row["minCursor"], row["cursor_enviado"]
        if not date or not str(lower).isdigit():
            continue
        followed = datetime.fromisoformat(date).timestamp()
        lower_time = int(lower)
        upper_time = int(upper) if str(upper).isdigit() and int(upper) > 0 else datetime.fromisoformat(
            row["observed_at"].replace("Z", "+00:00")).timestamp()
        window_checked += 1
        if lower_time <= followed <= upper_time:
            window_inside += 1
        elif len(window_outside) < 20:
            window_outside.append({"username": row["username_web"], "posicion": row["posicion_respuesta"],
                                   "fecha": date, "cursor_min": lower, "cursor_max": upper})
    pages = {}
    for row in web:
        pages[int(row["pagina"])] = int(row["minCursor"]) if str(row["minCursor"]).isdigit() else None
    cursor_values = [value for _, value in sorted(pages.items()) if value is not None]
    summary = {"web_filas": len(web), "exportacion_fechas_validas": len(dated),
               "coincidencias_con_fecha": len(matched), "solo_web": len(web) - len(matched),
               "solo_exportacion": len(export_only),
               "pares_fechas_distintas": pairs, "pares_empatados": ties,
               "inversiones": inversions, "fraccion_inversiones": inversions / pairs if pairs else None,
               "ejemplos_inversion": examples,
               "paginas_con_cursor": len(cursor_values),
               "cursores_descendentes": all(a > b for a, b in zip(cursor_values, cursor_values[1:])),
               "cursor_ultimo_utc": datetime.fromtimestamp(cursor_values[-1], timezone.utc).isoformat()
               if cursor_values else None,
               "fechas_comparadas_con_ventana_cursor": window_checked,
               "fechas_dentro_ventana_cursor": window_inside,
               "fechas_fuera_ventana_cursor": window_checked - window_inside,
               "ejemplos_fuera_ventana_cursor": window_outside}
    return table, summary


def blocus_observations() -> list[dict]:
    import json as _json
    base = ROOT / "data" / "user_blocusespanol" / "relaciones" / "http_curl_20261025"
    with (base / "seguidores.csv").open(encoding="utf-8-sig", newline="") as stream:
        first = [row["id"] for row in csv.DictReader(stream)]
    root = ROOT / "data" / "lote_blocus_20261025T195208Z" / "evidencias_orden"
    folders = [root / stamp / "blocusespanol" / "seguidores" for stamp in
               ("20261025T200409Z", "20261025T213414Z")]
    sequences = [first]
    for folder in folders:
        sequences.append([str(row["user_id"]) for file in sorted(folder.glob("pagina_*.json"))
                          for row in _json.loads(file.read_text(encoding="utf-8"))["rows"]])
    transitions = []
    for old, new in zip(sequences, sequences[1:]):
        old_set, new_set = set(old), set(new)
        added = [i + 1 for i, uid in enumerate(new) if uid not in old_set]
        removed = [i + 1 for i, uid in enumerate(old) if uid not in new_set]
        transitions.append({"antes": len(old), "despues": len(new), "nuevos": len(added),
                            "posiciones_nuevos": added, "bajas": len(removed),
                            "posiciones_bajas": removed,
                            "orden_comun_identico": [u for u in old if u in new_set]
                                                   == [u for u in new if u in old_set]})
    return transitions


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exportacion", type=Path, help="ZIP/JSON oficial de @jbarri; no se copia.")
    parser.add_argument("--captura", type=Path, help="Carpeta captura_web_*; por defecto la última.")
    args = parser.parse_args()
    capture = args.captura or max(STUDY.glob("captura_web_*/resumen.json"), key=lambda p: p.stat().st_mtime).parent
    captured = json.loads((capture / "resumen.json").read_text(encoding="utf-8"))
    dated, export_meta = read_export(args.exportacion) if args.exportacion else ({}, {"estado": "pendiente"})
    table, metrics = [], {}
    for direction in KEYS:
        csv_path = capture / f"{direction}.csv"
        if csv_path.exists():
            chunk, metrics[direction] = compare(read_capture(capture, direction), dated.get(direction, {}), direction)
            table.extend(chunk)
        else:
            metrics[direction] = {"estado": "captura_no_disponible"}
    with (STUDY / "comparacion.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=TABLE_FIELDS)
        writer.writeheader()
        writer.writerows(table)
    blocus = blocus_observations()
    result = {"captura": str(capture.resolve()), "estado_exportacion": "analizada" if args.exportacion else "pendiente",
              "exportacion": export_meta, "captura_estado": captured.get("lists", {}),
              "comparacion": metrics, "blocus_tres_capturas": blocus}
    (STUDY / "resumen.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    text = ["# Orden de seguidores y seguidos: @jbarri", "",
            f"Captura web: `{capture}`. Exportación oficial: **{result['estado_exportacion']}**.", "",
            "## Evidencia observacional anterior", ""]
    for step in blocus:
        text.append(f"@blocusespanol: {step['antes']} → {step['despues']} seguidores; "
                    f"{step['nuevos']} ID nuevos en posiciones {step['posiciones_nuevos']}; "
                    f"{step['bajas']} bajas; orden común conservado: {step['orden_comun_identico']}.")
    text += ["", "## @jbarri", ""]
    for direction in KEYS:
        state, comparison = captured.get("lists", {}).get(direction, {}), metrics[direction]
        advertised = state.get("advertised_count_end", state.get("advertised_count_start"))
        coverage = (f" de {advertised} mostradas en el perfil" if advertised is not None else "")
        text.append(f"- {direction}: {state.get('rows', 0)} filas web{coverage}, "
                    f"estado `{state.get('status', 'desconocido')}`; "
                    f"{comparison.get('coincidencias_con_fecha', 0)} cruces fechados, "
                    f"{comparison.get('solo_web', 0)} solo web y {comparison.get('solo_exportacion', 0)} solo exportación; "
                    f"{comparison.get('inversiones', 0)} inversiones de {comparison.get('pares_fechas_distintas', 0)} pares comparables.")
    text += ["", "## Interpretación", ""]
    if args.exportacion:
        text.append("Una inversión ocurre cuando una cuenta situada arriba tiene una fecha oficial anterior a otra situada abajo. "
                    "Los empates de fecha se excluyen. Cero inversiones respaldan orden descendente entre las cuentas comparables de esta captura, "
                    "no una garantía universal ni la fecha de seguimiento de otras cuentas.")
        for direction in KEYS:
            comparison = metrics[direction]
            text.append(f"En {direction}, {comparison['fechas_dentro_ventana_cursor']} de "
                        f"{comparison['fechas_comparadas_con_ventana_cursor']} fechas cruzadas caen entre "
                        "el cursor enviado y el cursor mínimo de su página. Es una observación empírica de esta captura; "
                        "no atribuye una fecha individual a otras listas.")
    else:
        text.append("La exportación oficial de @jbarri aún no está disponible; no hay contraste de fechas individuales. "
                    "Las inserciones al principio de @blocusespanol apoyan la hipótesis de orden reciente→antiguo, pero no certifican el ranking histórico. "
                    "Cuando TikTok prepare el JSON, conviene repetir la captura web ese mismo día y ejecutar este script con "
                    "`--captura RUTA_CAPTURA --exportacion RUTA_JSON_O_ZIP`.")
    text.append("Las cifras de perfil y las filas devueltas no coinciden; la paginación terminó sin devolver todas las cuentas "
                "anunciadas. El contraste de fechas solo cubrirá las filas efectivamente observadas.")
    text += ["", "El cursor de la API web puede parecer una marca de tiempo y desciende entre páginas, "
             "pero la API web no documenta una fecha de seguimiento por fila. La Research API es un sistema distinto.", "",
             "Fuentes: [Research API de seguidores](https://developers.tiktok.com/docs/en/research-api-specs-query-user-followers), "
             "[portabilidad oficial](https://developers.tiktok.com/docs/en/data-portability-data-types), "
             "[cliente web en GitHub](https://github.com/sangzun-han/Tiktok-Api/blob/main/README.md).", ""]
    (STUDY / "INFORME.md").write_text("\n".join(text), encoding="utf-8")
    print(json.dumps({"estado_exportacion": result["estado_exportacion"], "comparacion": metrics}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
