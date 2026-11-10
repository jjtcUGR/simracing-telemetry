"""Modelos de entrada y reglas de validación de la telemetría."""

import math
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_IDENTIFICADOR = r"^[a-z0-9_]{2,60}$"
_MAX_CLAVES_SETUP = 60
_PRESION_MIN_PSI = 10.0
_PRESION_MAX_PSI = 50.0


class Condiciones(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pista: Literal["seco", "mojado"]
    temp_aire_c: float = Field(ge=-30, le=60)
    temp_pista_c: float = Field(ge=-30, le=80)


class Vuelta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    numero: int = Field(ge=1)
    tiempo_ms: int = Field(gt=0, le=3_600_000)
    sectores_ms: list[int] = Field(min_length=1, max_length=10)
    valida: bool = True

    @model_validator(mode="after")
    def _sectores_coherentes(self) -> "Vuelta":
        if any(s <= 0 for s in self.sectores_ms):
            raise ValueError("los tiempos de sector deben ser positivos")
        if abs(sum(self.sectores_ms) - self.tiempo_ms) > 1:
            raise ValueError("la suma de los sectores no coincide con el tiempo de vuelta")
        return self


def _hojas(valor: Any, profundidad: int = 0):
    if profundidad > 3:
        raise ValueError("el setup no puede tener más de 3 niveles de anidación")
    if isinstance(valor, dict):
        for v in valor.values():
            yield from _hojas(v, profundidad + 1)
    else:
        yield valor


class SesionEntrada(BaseModel):
    """Sesión de pista enviada por un piloto o un plugin del simulador."""

    model_config = ConfigDict(extra="forbid")

    juego: str = Field(pattern=_IDENTIFICADOR)
    vehiculo: str = Field(pattern=_IDENTIFICADOR)
    circuito: str = Field(pattern=_IDENTIFICADOR)
    condiciones: Condiciones
    setup: dict[str, Any]
    vueltas: list[Vuelta] = Field(min_length=1, max_length=200)

    @field_validator("setup")
    @classmethod
    def _setup_valido(cls, setup: dict[str, Any]) -> dict[str, Any]:
        hojas = list(_hojas(setup))
        if len(hojas) > _MAX_CLAVES_SETUP:
            raise ValueError(f"el setup no puede tener más de {_MAX_CLAVES_SETUP} parámetros")
        for hoja in hojas:
            if isinstance(hoja, bool | str):
                continue
            if not isinstance(hoja, int | float) or not math.isfinite(hoja):
                raise ValueError("los parámetros del setup deben ser números, textos o booleanos")
            if abs(hoja) > 10_000:
                raise ValueError("hay un parámetro del setup fuera de rango")
        presiones = setup.get("presiones_psi")
        if isinstance(presiones, dict):
            for rueda, psi in presiones.items():
                if not isinstance(psi, int | float) or not (
                    _PRESION_MIN_PSI <= psi <= _PRESION_MAX_PSI
                ):
                    raise ValueError(
                        f"presión imposible en la rueda {rueda}: debe estar entre "
                        f"{_PRESION_MIN_PSI} y {_PRESION_MAX_PSI} psi"
                    )
        return setup

    @model_validator(mode="after")
    def _vueltas_coherentes(self) -> "SesionEntrada":
        numeros = [v.numero for v in self.vueltas]
        if len(numeros) != len(set(numeros)):
            raise ValueError("hay números de vuelta repetidos")
        if len({len(v.sectores_ms) for v in self.vueltas}) != 1:
            raise ValueError("todas las vueltas deben tener el mismo número de sectores")
        return self
