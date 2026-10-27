"""Valida los artefactos del lote Blocus y deja una nota de cobertura."""

import csv
import json
from collections import Counter
from pathlib import Path


OUT = Path(__file__).resolve().parents[1] / "outputs/comentarios_blocus_20261026"


def rows(name):
    with (OUT / name).open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def main():
    posts = rows("publicaciones.csv")
    status = rows("estado_publicaciones.csv")
    accounts = rows("estado_cuentas.csv")
    comments = rows("comentarios.csv")
    ids = [row["id"] for row in posts]
    assert len(ids) == len(set(ids)) == len(status) == 495
    assert len(accounts) == 54
    assert {row["id"] for row in status} == set(ids)
    assert all(row["estado"] in ("completo", "parcial") for row in status)
    assert sum(int(row["capturados"]) for row in status) == len(comments)
    comment_keys = [(row["publication_id"], row["comment_id"]) for row in comments]
    assert len(comment_keys) == len(set(comment_keys))
    assert all(row["publication_id"] in ids and row["comment_id"] for row in comments)
    assert sum(int(row["publicaciones_observadas"]) for row in accounts) == len(posts)
    assert sum(int(row["comentarios_capturados"]) for row in accounts) == len(comments)
    assert sum(int(row["publicaciones_descargadas"]) for row in accounts) == len(posts)

    states = Counter(row["estado"] for row in status)
    types = Counter(row["tipo"] for row in posts)
    accounts_unavailable = [row["cuenta"] for row in accounts if row["perfil_disponible"] == "False"]
    reported = sum(int(row["reportados_principales"]) for row in status if row["reportados_principales"])
    replies = sum(row["is_reply"] == "1" for row in comments)
    accounts_with_posts = sum(int(row["publicaciones_observadas"]) > 0 for row in accounts)
    result = {"cuentas": len(accounts), "cuentas_con_publicaciones": accounts_with_posts,
              "cuentas_perfil_no_disponible": accounts_unavailable,
              "publicaciones": len(posts), "videos": types["video"], "fotos": types["photo"],
              "publicaciones_completas": states["completo"], "publicaciones_parciales": states["parcial"],
              "comentarios": len(comments), "respuestas": replies, "total_reportado_api": reported,
              "ids_comentario_duplicados": 0, "archivos_publicacion": len(list((OUT / "por_publicacion").glob("*.json")))}
    assert result["archivos_publicacion"] == len(posts)
    (OUT / "auditoria.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    note = f"""# Comentarios de las 54 cuentas analizadas

Se inventariaron {len(posts)} publicaciones visibles ({types['video']} vídeos y {types['photo']} fotos) de {accounts_with_posts} cuentas con posts. Las cuentas @{accounts_unavailable[0]} y @{accounts_unavailable[1]} devolvieron un error de perfil y no se pudo verificar su inventario.

Se guardaron {len(comments):,} comentarios, incluidas {replies:,} respuestas, sin IDs duplicados dentro de una publicación. {states['completo']} posts coinciden con el total anunciado por la API o muestran cero. Otros {states['parcial']} quedan marcados como parciales porque TikTok anunció más comentarios o respuestas de los que entregó mediante su paginación. El total anunciado para el conjunto fue {reported:,}; no representa necesariamente comentarios aún accesibles, porque puede incluir contenido eliminado, filtrado o no visible para esta sesión. «Completo» describe la coincidencia de los datos recibidos con ese contador, no una garantía de acceso a comentarios privados o borrados.

- `comentarios.csv`: una fila por comentario o respuesta, con cuenta, URL e ID del post, autor, texto, fecha UTC, likes y vínculo al comentario padre.
- `publicaciones.csv`: inventario de enlaces de vídeos y fotos.
- `estado_publicaciones.csv`: capturas, total anunciado y estado de cada post.
- `estado_cuentas.csv`: cobertura y recuentos por cuenta.
- `por_publicacion/`: archivos JSON reanudables por post.

Fecha de recopilación: 26 de octubre de 2026. Para reanudar posts erróneos o nuevos, actualizar el inventario visible y ejecutar `python scripts/descargar_comentarios_http_blocus.py`; los posts ya guardados se omiten.
"""
    (OUT / "COBERTURA.md").write_text(note, encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
