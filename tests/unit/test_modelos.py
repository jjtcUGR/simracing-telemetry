import pytest
from pydantic import ValidationError

from simracing.comun.modelos import SesionEntrada


def test_sesion_valida(sesion):
    modelo = SesionEntrada.model_validate(sesion)
    assert len(modelo.vueltas) == 2


def test_rechaza_sectores_que_no_suman_el_tiempo(sesion):
    sesion["vueltas"][0]["tiempo_ms"] += 500
    with pytest.raises(ValidationError, match="suma de los sectores"):
        SesionEntrada.model_validate(sesion)


def test_rechaza_tiempos_negativos(sesion):
    sesion["vueltas"][0]["tiempo_ms"] = -1
    with pytest.raises(ValidationError):
        SesionEntrada.model_validate(sesion)


def test_rechaza_presiones_imposibles(sesion):
    sesion["setup"]["presiones_psi"]["di"] = 80
    with pytest.raises(ValidationError, match="presión imposible"):
        SesionEntrada.model_validate(sesion)


def test_rechaza_vueltas_repetidas(sesion):
    sesion["vueltas"][1]["numero"] = 1
    with pytest.raises(ValidationError, match="repetidos"):
        SesionEntrada.model_validate(sesion)


def test_rechaza_numero_de_sectores_distinto(sesion):
    sesion["vueltas"][1]["sectores_ms"] = [100000, 38904]
    with pytest.raises(ValidationError, match="mismo número de sectores"):
        SesionEntrada.model_validate(sesion)


def test_rechaza_campos_desconocidos(sesion):
    sesion["id_piloto"] = "intento-de-suplantacion"
    with pytest.raises(ValidationError):
        SesionEntrada.model_validate(sesion)


@pytest.mark.parametrize("valor", ["Spa Francorchamps", "spa/../x", "a"])
def test_rechaza_identificadores_mal_formados(sesion, valor):
    sesion["circuito"] = valor
    with pytest.raises(ValidationError):
        SesionEntrada.model_validate(sesion)


def test_rechaza_setup_demasiado_anidado(sesion):
    sesion["setup"] = {"a": {"b": {"c": {"d": {"e": 1}}}}}
    with pytest.raises(ValidationError, match="niveles"):
        SesionEntrada.model_validate(sesion)


def test_rechaza_setup_con_valores_no_admitidos(sesion):
    sesion["setup"]["marchas"] = [1, 2, 3]
    with pytest.raises(ValidationError):
        SesionEntrada.model_validate(sesion)
