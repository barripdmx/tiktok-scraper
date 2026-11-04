from scripts.revision_semanal_blocus import actualizar, alta_estimada, coma, enlaces, informe_vacio, reciente


def obs(uid, usuario, seguidores=100, estado="ok"):
    return {"uid": uid, "usuario": usuario, "seguidores": seguidores, "estado": estado}


def test_alta_estimada():
    assert alta_estimada("7698786239998870550") == "2026-10-20"


def test_coma():
    assert coma(6.84) == "+6,8" and coma(-3.7) == "-3,7"


def test_ciclo_nueva_renombrada_baja_y_crecimiento():
    censo, inf = {}, informe_vacio()
    actualizar(censo, [obs("7000000000000000001", "blocus_a", 100)], "d1", inf)
    assert inf["nuevas"] == ["blocus_a"]
    inf = informe_vacio()
    actualizar(censo, [obs("7000000000000000001", "blocus_b", 120)], "d2", inf)
    assert inf["renombradas"] == [("blocus_a", "blocus_b")] and inf["crecimiento"] == [("blocus_b", 100, 120)]
    inf = informe_vacio()
    actualizar(censo, [obs("7000000000000000001", "blocus_b", None, "no_disponible:10221")], "d3", inf)
    assert inf["bajas"] == []  # un fallo no basta
    actualizar(censo, [obs("7000000000000000001", "blocus_b", None, "no_disponible:10221")], "d4", inf)
    assert inf["bajas"] == ["blocus_b"]
    actualizar(censo, [obs("7000000000000000001", "blocus_b", 130)], "d5", inf)
    assert inf["reaparecidas"] == ["blocus_b"]


def test_crecimiento_solo_con_medicion_inmediatamente_anterior():
    censo, inf = {}, informe_vacio()
    actualizar(censo, [obs("7000000000000000003", "y", 100)], "d1", inf)
    actualizar(censo, [obs("7000000000000000003", "y", None, "no_disponible:10221")], "d2", inf)
    actualizar(censo, [obs("7000000000000000003", "y", 120)], "d3", inf)
    assert inf["crecimiento"] == []


def test_nueva_reciente_y_enlaces():
    assert reciente("2026-10-20", "2026-11-04 10:00") and not reciente("2026-08-01", "2026-11-04 10:00") and not reciente("2026-10-20", "d1")
    assert enlaces("grupo https://signal.group/#abc y t.me/blocus", "") == ["https://signal.group/#abc", "t.me/blocus"]
    censo, inf = {}, informe_vacio()
    o = {**obs("7698786239998870550", "z", 10), "enlaces": ["t.me/z"]}
    actualizar(censo, [o], "2026-11-04 10:00", inf)
    assert inf["nuevas_recientes"] == ["z"] and inf["enlaces"] == [("z", ["t.me/z"])]


def test_base_pequena_no_cuenta_en_crecimiento():
    censo, inf = {}, informe_vacio()
    actualizar(censo, [obs("7000000000000000002", "x", 5)], "d1", inf)
    actualizar(censo, [obs("7000000000000000002", "x", 50)], "d2", inf)
    assert inf["crecimiento"] == []
