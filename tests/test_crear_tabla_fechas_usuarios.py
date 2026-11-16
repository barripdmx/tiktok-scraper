from scripts.crear_tabla_fechas_usuarios import build


def test_fecha_confirmada_prevalece_y_comentador_se_unifica_por_id():
    accounts = [{"user_id": "1", "username": "principal",
                 "fecha_creacion_perfil_utc": "2020-01-01T00:00:00+00:00",
                 "fecha_uid_estimada_utc": "2019-12-31T23:59:00+00:00",
                 "fuente_fecha_perfil": "perfil"}]
    comments = [{"autor_id": "1", "autor_handle": "nuevo_nombre",
                 "creado_utc": "2026-10-26T10:00:00Z"},
                {"autor_id": "1", "autor_handle": "nuevo_nombre",
                 "creado_utc": "2026-10-26T11:00:00Z"},
                {"autor_id": "x", "autor_handle": "sin_id_numerico",
                 "creado_utc": "2026-10-26T10:00:00Z"}]
    table = build(accounts, comments)
    assert len(table) == 2
    known = next(row for row in table if row["user_id"] == "1")
    assert known["fecha_orden_utc"] == "2020-01-01T00:00:00+00:00"
    assert known["tipo_fecha"] == "Confirmada por perfil"
    assert known["en_grafo_comentarios"] == "Sí"
    assert known["comentarios_observados"] == 2
    assert known["usuario"] == "principal"
    unknown = next(row for row in table if row["user_id"] == "x")
    assert unknown["tipo_fecha"] == "Sin fecha"
    assert table[-1] is unknown
