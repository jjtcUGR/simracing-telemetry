from simracing.analisis.worker import procesar_sesion


async def _procesada(repo, cache, sesion, id_sesion, **cambios):
    await repo.insertar_sesion(
        {"_id": id_sesion, "piloto": "p1", "estado": "pendiente", **sesion, **cambios}
    )
    await procesar_sesion(id_sesion, repo, cache)


async def test_setups_exige_vehiculo_y_circuito(cliente_busqueda):
    respuesta = await cliente_busqueda.get("/api/setups", params={"vehiculo": "x"})
    assert respuesta.status_code == 400
    assert respuesta.json()["error"] == "peticion_incorrecta"


async def test_setups_sin_resultados_devuelve_lista_vacia(cliente_busqueda):
    respuesta = await cliente_busqueda.get("/api/setups", params={"vehiculo": "x", "circuito": "y"})
    assert respuesta.status_code == 200
    assert respuesta.json() == []


async def test_ranking_ordenado_y_cacheado(cliente_busqueda, repo, cache, sesion):
    await _procesada(repo, cache, sesion, "rapida")
    lenta = {
        **sesion,
        "vueltas": [
            {"numero": 1, "tiempo_ms": 140904, "sectores_ms": [42980, 60410, 37514], "valida": True}
        ],
    }
    await _procesada(repo, cache, lenta, "lenta")
    params = {"vehiculo": "porsche_992_gt3_r", "circuito": "spa_francorchamps"}

    primera = await cliente_busqueda.get("/api/setups", params=params)
    assert primera.status_code == 200
    assert primera.headers["X-Cache"] == "MISS"
    assert [s["id_sesion"] for s in primera.json()] == ["rapida", "lenta"]
    assert primera.json()[0]["puntuacion"] > primera.json()[1]["puntuacion"]

    segunda = await cliente_busqueda.get("/api/setups", params=params)
    assert segunda.headers["X-Cache"] == "HIT"
    assert segunda.json() == primera.json()


async def test_filtra_por_condiciones(cliente_busqueda, repo, cache, sesion):
    await _procesada(repo, cache, sesion, "seco")
    mojado = {**sesion, "condiciones": {**sesion["condiciones"], "pista": "mojado"}}
    await _procesada(repo, cache, mojado, "mojado")
    respuesta = await cliente_busqueda.get(
        "/api/setups",
        params={
            "vehiculo": "porsche_992_gt3_r",
            "circuito": "spa_francorchamps",
            "condiciones": "mojado",
        },
    )
    assert [s["id_sesion"] for s in respuesta.json()] == ["mojado"]


async def test_detalle_de_sesion(cliente_busqueda, repo, cache, sesion):
    await _procesada(repo, cache, sesion, "s1")
    respuesta = await cliente_busqueda.get("/api/sesiones/s1")
    assert respuesta.status_code == 200
    assert respuesta.json()["id_sesion"] == "s1"
    assert respuesta.json()["analisis"]["sector_mas_debil"] == 2


async def test_detalle_de_sesion_inexistente(cliente_busqueda):
    respuesta = await cliente_busqueda.get("/api/sesiones/no-existe")
    assert respuesta.status_code == 404


async def test_comparativa(cliente_busqueda, repo, cache, sesion):
    await _procesada(repo, cache, sesion, "a")
    otra = {
        **sesion,
        "vueltas": [
            {"numero": 1, "tiempo_ms": 139004, "sectores_ms": [41880, 59610, 37514], "valida": True}
        ],
    }
    await _procesada(repo, cache, otra, "b")
    respuesta = await cliente_busqueda.get(
        "/api/comparativa", params={"sesion_a": "a", "sesion_b": "b"}
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["sectores_ms"] == [100, -200, 0]
    assert respuesta.json()["total_ms"] == -100


async def test_comparativa_con_sesion_pendiente_responde_409(cliente_busqueda, repo, cache, sesion):
    await _procesada(repo, cache, sesion, "a")
    await repo.insertar_sesion({"_id": "b", "piloto": "p", "estado": "pendiente", **sesion})
    respuesta = await cliente_busqueda.get(
        "/api/comparativa", params={"sesion_a": "a", "sesion_b": "b"}
    )
    assert respuesta.status_code == 409


async def test_comparativa_de_circuitos_distintos_responde_409(
    cliente_busqueda, repo, cache, sesion
):
    await _procesada(repo, cache, sesion, "a")
    await _procesada(repo, cache, {**sesion, "circuito": "monza"}, "b")
    respuesta = await cliente_busqueda.get(
        "/api/comparativa", params={"sesion_a": "a", "sesion_b": "b"}
    )
    assert respuesta.status_code == 409


async def test_comparativa_con_sesion_inexistente_responde_404(cliente_busqueda):
    respuesta = await cliente_busqueda.get(
        "/api/comparativa", params={"sesion_a": "a", "sesion_b": "b"}
    )
    assert respuesta.status_code == 404


async def test_health(cliente_busqueda, cache):
    assert (await cliente_busqueda.get("/health")).status_code == 200
    cache.disponible = False
    respuesta = await cliente_busqueda.get("/health")
    assert respuesta.status_code == 503
    assert respuesta.json()["service"] == "busqueda"
