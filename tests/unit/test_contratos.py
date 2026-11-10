"""Los dobles de prueba solo son útiles si se comportan como las clases reales.

Este test comprueba que cada método público de un doble existe también en su clase real
(con los mismos parámetros), para que los tests unitarios no pasen con un doble que
tiene métodos que la implementación real no tiene.
"""

import inspect

import pytest

from simracing.comun.datos import CacheRedis, ColaRedis, RepositorioMongo
from tests.fakes import CacheFalsa, ColaFalsa, RepoFalso


def _metodos_publicos(clase) -> dict:
    return {
        nombre: inspect.signature(miembro)
        for nombre, miembro in inspect.getmembers(clase, inspect.isfunction)
        if not nombre.startswith("_")
    }


@pytest.mark.parametrize(
    ("doble", "real"),
    [(RepoFalso, RepositorioMongo), (ColaFalsa, ColaRedis), (CacheFalsa, CacheRedis)],
)
def test_el_doble_respeta_la_interfaz_real(doble, real):
    metodos_reales = _metodos_publicos(real)
    for nombre, firma in _metodos_publicos(doble).items():
        assert nombre in metodos_reales, f"{real.__name__} no implementa {nombre}()"
        assert list(firma.parameters) == list(metodos_reales[nombre].parameters), (
            f"{real.__name__}.{nombre}() tiene parámetros distintos al doble"
        )
