from simracing.comun.api import seudonimo
from tests.conftest import CABECERAS, TOKEN


async def test_registra_sesion_y_publica_evento(cliente_ingesta, repo, cola, sesion):
    respuesta = await cliente_ingesta.post("/api/telemetria", json=sesion, headers=CABECERAS)

    assert respuesta.status_code == 202
    cuerpo = respuesta.json()
    assert cuerpo["estado"] == "pendiente"
    guardada = repo.sesiones[cuerpo["id_sesion"]]
    assert guardada["estado"] == "pendiente"
    assert guardada["circuito"] == "spa_francorchamps"
    assert cola.publicados == [cuerpo["id_sesion"]]


async def test_el_piloto_se_guarda_seudonimizado(cliente_ingesta, repo, sesion):
    respuesta = await cliente_ingesta.post("/api/telemetria", json=sesion, headers=CABECERAS)
    guardada = repo.sesiones[respuesta.json()["id_sesion"]]
    assert guardada["piloto"] == seudonimo(TOKEN, "sal")
    assert TOKEN not in str(guardada)


async def test_sin_token_responde_401(cliente_ingesta, cola, sesion):
    respuesta = await cliente_ingesta.post("/api/telemetria", json=sesion)
    assert respuesta.status_code == 401
    assert respuesta.json()["error"] == "no_autorizado"
    assert cola.publicados == []


async def test_token_no_valido_responde_401(cliente_ingesta, sesion):
    respuesta = await cliente_ingesta.post(
        "/api/telemetria", json=sesion, headers={"Authorization": "Bearer otro"}
    )
    assert respuesta.status_code == 401


async def test_datos_incoherentes_responden_422_con_formato_propio(cliente_ingesta, repo, sesion):
    sesion["vueltas"][0]["tiempo_ms"] = 1
    respuesta = await cliente_ingesta.post("/api/telemetria", json=sesion, headers=CABECERAS)

    assert respuesta.status_code == 422
    cuerpo = respuesta.json()
    assert cuerpo["error"] == "validacion"
    assert cuerpo["detalle"][0]["campo"].startswith("vueltas.0")
    assert repo.sesiones == {}


async def test_health_ok(cliente_ingesta):
    respuesta = await cliente_ingesta.get("/health")
    assert respuesta.status_code == 200
    assert respuesta.json() == {
        "status": "ok",
        "service": "ingesta",
        "dependencias": {"mongodb": "ok", "redis": "ok"},
    }


async def test_health_503_si_cae_una_dependencia(cliente_ingesta, cola):
    cola.disponible = False
    respuesta = await cliente_ingesta.get("/health")
    assert respuesta.status_code == 503
    assert respuesta.json()["dependencias"]["redis"] == "error"
