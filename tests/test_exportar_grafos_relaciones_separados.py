from scripts.exportar_grafos_relaciones_separados import split_graphs


def test_cada_lista_tiene_grafo_propio_y_conserva_objetivos():
    nodes = [
        {"node_id": "uid:1", "user_id": "1", "username": "objetivo",
         "objetivo": "objetivo"},
        {"node_id": "uid:2", "user_id": "2", "username": "seguidor",
         "objetivo": ""},
        {"node_id": "uid:3", "user_id": "3", "username": "seguido",
         "objetivo": ""},
        {"node_id": "uid:4", "user_id": "4", "username": "aislado",
         "objetivo": "aislado"},
    ]
    relations = [
        {"source": "uid:2", "target": "uid:1", "capturas": "objetivo:seguidores:x",
         "primera_observacion_utc": "x", "ultima_observacion_utc": "x"},
        {"source": "uid:1", "target": "uid:3", "capturas": "objetivo:seguidos:x",
         "primera_observacion_utc": "x", "ultima_observacion_utc": "x"},
        {"source": "uid:1", "target": "uid:2",
         "capturas": "objetivo:seguidores:x|objetivo:seguidos:y",
         "primera_observacion_utc": "x", "ultima_observacion_utc": "y"},
    ]
    graphs = split_graphs(nodes, relations)
    followers, following = graphs["seguidores"], graphs["seguidos"]
    assert set(followers.edges) == {("uid:2", "uid:1"), ("uid:1", "uid:2")}
    assert set(following.edges) == {("uid:1", "uid:3"), ("uid:1", "uid:2")}
    assert "uid:4" in followers and "uid:4" in following
    assert followers.nodes["uid:1"]["label"] == "@objetivo"
    assert all(attrs["tipo"] == "cuenta" for _, attrs in followers.nodes(data=True))
