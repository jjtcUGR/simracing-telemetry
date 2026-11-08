"""Flujo completo contra MongoDB y Redis reales: Ingesta → Redis Stream → worker → Búsqueda.

Se ejecutan en la CI (servicios de GitHub Actions) o en local con `docker compose up mongo redis`
y las variables MONGO_URL y REDIS_URL. Si no están definidas, se omiten.
"""

import os
import uuid

import httpx
import pytest

from simracing.analisis.worker import ciclo
from simracing.busqueda.app import crear_app as crear_busqueda
from simracing.comun.config import Config
from simracing.comun.datos import CacheRedis, ColaRedis, RepositorioMongo, cliente_redis
from simracing.ingesta.app import crear_app as crear_ingesta
from tests.conftest import CABECERAS, TOKEN

pytestmark = [
    pytest.mark.integracion,
    pytest.mark.skipif(
        not (os.environ.get("MONGO_URL") and os.environ.get("REDIS_URL")),
        reason="necesita MONGO_URL y REDIS_URL",
    ),
]


@pytest.fixture
async def entorno():
    sufijo = uuid.uuid4().hex[:8]
    config = Config(
        mongo_url=os.environ["MONGO_URL"],
        mongo_db=f"test_{sufijo}",
        redis_url=os.environ["REDIS_URL"],
        api_tokens=frozenset({TOKEN}),
        salt_seudonimo="sal",
        stream=f"test-sesiones-{sufijo}",
        grupo="test-analisis",
        cache_ttl_s=30,
    )
    redis = cliente_redis(config.redis_url)
    repo = RepositorioMongo(config.mongo_url, config.mongo_db)
    await repo.preparar()
    cola = ColaRedis(redis, config.stream, config.grupo)
    await cola.asegurar_grupo()
    cache = CacheRedis(redis)
    yield config, repo, cola, cache
    await redis.delete(config.stream)
    await cache.invalidar("cache:setups:*")
    await repo._cliente.drop_database(config.mongo_db)
    await redis.aclose()
    await repo.cerrar()


def _cliente(app):
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def test_sesion_recorre_todo_el_sistema(entorno, sesion):
    config, repo, cola, cache = entorno
    async with (
        _cliente(crear_ingesta(config, repo=repo, cola=cola)) as ingesta,
        _cliente(crear_busqueda(config, repo=repo, cache=cache)) as busqueda,
    ):
        assert (await ingesta.get("/health")).status_code == 200
        assert (await busqueda.get("/health")).status_code == 200

        alta = await ingesta.post("/api/telemetria", json=sesion, headers=CABECERAS)
        assert alta.status_code == 202
        id_sesion = alta.json()["id_sesion"]

        pendiente = await busqueda.get(f"/api/sesiones/{id_sesion}")
        assert pendiente.json()["estado"] == "pendiente"

        assert await ciclo(cola, repo, cache, "worker-test", bloqueo_ms=1000) == 1

        procesada = (await busqueda.get(f"/api/sesiones/{id_sesion}")).json()
        assert procesada["estado"] == "procesada"
        assert procesada["analisis"]["vuelta_ideal_ms"] == 138880

        params = {"vehiculo": sesion["vehiculo"], "circuito": sesion["circuito"]}
        ranking = await busqueda.get("/api/setups", params=params)
        assert ranking.headers["X-Cache"] == "MISS"
        assert ranking.json()[0]["id_sesion"] == id_sesion
        assert (await busqueda.get("/api/setups", params=params)).headers["X-Cache"] == "HIT"


async def test_evento_no_confirmado_se_reclama(entorno, sesion, monkeypatch):
    config, repo, cola, cache = entorno
    async with _cliente(crear_ingesta(config, repo=repo, cola=cola)) as ingesta:
        id_sesion = (await ingesta.post("/api/telemetria", json=sesion, headers=CABECERAS)).json()[
            "id_sesion"
        ]

    # Un worker lee el evento y "muere" antes de confirmarlo.
    assert len(await cola.leer("worker-caido", cuantos=10, bloqueo_ms=1000)) == 1

    monkeypatch.setattr("simracing.analisis.worker.INACTIVIDAD_RECLAMO_MS", 0)
    assert await ciclo(cola, repo, cache, "worker-sano", bloqueo_ms=100) == 1
    assert (await repo.obtener_sesion(id_sesion))["estado"] == "procesada"
