import copy

import httpx
import pytest

from simracing.busqueda.app import crear_app as crear_busqueda
from simracing.comun.config import Config
from simracing.ingesta.app import crear_app as crear_ingesta
from tests.fakes import CacheFalsa, ColaFalsa, RepoFalso

TOKEN = "token-de-prueba"
CABECERAS = {"Authorization": f"Bearer {TOKEN}"}

SESION_EJEMPLO = {
    "juego": "assetto_corsa_competizione",
    "vehiculo": "porsche_992_gt3_r",
    "circuito": "spa_francorchamps",
    "condiciones": {"pista": "seco", "temp_aire_c": 21, "temp_pista_c": 29},
    "setup": {
        "presiones_psi": {"di": 27.4, "dd": 27.5, "ti": 27.1, "td": 27.2},
        "aero": {"ala_trasera": 6, "splitter": 2},
    },
    "vueltas": [
        {"numero": 1, "tiempo_ms": 139470, "sectores_ms": [42110, 59870, 37490], "valida": True},
        {"numero": 2, "tiempo_ms": 138904, "sectores_ms": [41980, 59410, 37514], "valida": True},
    ],
}


@pytest.fixture
def sesion() -> dict:
    return copy.deepcopy(SESION_EJEMPLO)


@pytest.fixture
def config() -> Config:
    return Config(
        mongo_url="mongodb://no-usado",
        mongo_db="test",
        redis_url="redis://no-usado",
        api_tokens=frozenset({TOKEN}),
        salt_seudonimo="sal",
    )


@pytest.fixture
def repo() -> RepoFalso:
    return RepoFalso()


@pytest.fixture
def cola() -> ColaFalsa:
    return ColaFalsa()


@pytest.fixture
def cache() -> CacheFalsa:
    return CacheFalsa()


@pytest.fixture
async def cliente_ingesta(config, repo, cola):
    app = crear_ingesta(config, repo=repo, cola=cola)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://ingesta"
    ) as cliente:
        yield cliente


@pytest.fixture
async def cliente_busqueda(config, repo, cache):
    app = crear_busqueda(config, repo=repo, cache=cache)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://busqueda"
    ) as cliente:
        yield cliente
