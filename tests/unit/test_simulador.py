import random

from tools.simulador import generar_sesion

from simracing.comun.modelos import SesionEntrada


def test_el_simulador_genera_sesiones_que_la_api_acepta():
    rng = random.Random(42)
    for _ in range(200):
        SesionEntrada.model_validate(generar_sesion(rng))


def test_la_semilla_hace_el_simulador_repetible():
    assert generar_sesion(random.Random(7)) == generar_sesion(random.Random(7))
