"""Lógica de negocio pura (sin E/S): análisis de sesiones, puntuación y comparativas."""

from collections.abc import Mapping, Sequence
from statistics import fmean, pstdev
from typing import Any

UMBRAL_ANOMALIA = 1.07
"""Una vuelta más lenta que el 107 % de la mejor se considera anómala (regla clásica de la F1)."""

PESO_RITMO = 0.8
PESO_REGULARIDAD = 0.2


def vueltas_validas(vueltas: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """Vueltas marcadas como válidas que no superan el 107 % de la mejor."""
    marcadas = [v for v in vueltas if v.get("valida", True)]
    if not marcadas:
        return []
    mejor = min(v["tiempo_ms"] for v in marcadas)
    return [v for v in marcadas if v["tiempo_ms"] <= mejor * UMBRAL_ANOMALIA]


def analizar_sesion(vueltas: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    validas = vueltas_validas(vueltas)
    resultado: dict[str, Any] = {
        "vueltas_totales": len(vueltas),
        "vueltas_validas": len(validas),
        "vueltas_invalidas": len(vueltas) - len(validas),
        "mejor_vuelta_ms": None,
        "mejor_vuelta_sectores_ms": None,
        "vuelta_ideal_ms": None,
        "consistencia_ms": None,
        "sector_mas_debil": None,
    }
    if not validas:
        return resultado

    mejor = min(validas, key=lambda v: v["tiempo_ms"])
    num_sectores = len(mejor["sectores_ms"])
    por_sector = [[v["sectores_ms"][i] for v in validas] for i in range(num_sectores)]
    mejores_sectores = [min(s) for s in por_sector]
    perdida_media = [fmean(s) - m for s, m in zip(por_sector, mejores_sectores, strict=True)]

    resultado.update(
        mejor_vuelta_ms=mejor["tiempo_ms"],
        mejor_vuelta_sectores_ms=list(mejor["sectores_ms"]),
        vuelta_ideal_ms=sum(mejores_sectores),
        consistencia_ms=round(pstdev([v["tiempo_ms"] for v in validas])),
        sector_mas_debil=perdida_media.index(max(perdida_media)) + 1,
    )
    return resultado


def puntuar_setup(mejor_vuelta_ms: int, consistencia_ms: int, record_ms: int) -> float:
    """Puntuación de 0 a 100: 80 % ritmo respecto al récord del coche/circuito, 20 % regularidad.

    El ritmo vale 1 si la vuelta iguala el récord y baja linealmente hasta 0 en el 107 %, de modo
    que un segundo de diferencia pese más que unas décimas de irregularidad.
    """
    if mejor_vuelta_ms <= 0 or record_ms <= 0:
        raise ValueError("los tiempos deben ser positivos")
    diferencia = max(mejor_vuelta_ms / record_ms - 1, 0.0)
    ritmo = max(1 - diferencia / (UMBRAL_ANOMALIA - 1), 0.0)
    regularidad = 1 / (1 + max(consistencia_ms, 0) / 1000)
    return round(100 * (PESO_RITMO * ritmo + PESO_REGULARIDAD * regularidad), 1)


def ranking_setups(entradas: Sequence[Mapping[str, Any]], limite: int) -> list[dict[str, Any]]:
    """Ordena los setups de mejor a peor puntuación, calculada contra el récord del conjunto."""
    if not entradas:
        return []
    record = min(e["mejor_vuelta_ms"] for e in entradas)
    puntuadas = [
        {**e, "puntuacion": puntuar_setup(e["mejor_vuelta_ms"], e["consistencia_ms"], record)}
        for e in entradas
    ]
    puntuadas.sort(key=lambda e: (-e["puntuacion"], e["mejor_vuelta_ms"]))
    return puntuadas[:limite]


def comparar_vueltas(sectores_a: Sequence[int], sectores_b: Sequence[int]) -> dict[str, Any]:
    """Diferencia A - B por sector y total. Positivo: A es más lenta."""
    if len(sectores_a) != len(sectores_b):
        raise ValueError("las vueltas no tienen el mismo número de sectores")
    diferencias = [a - b for a, b in zip(sectores_a, sectores_b, strict=True)]
    return {"total_ms": sum(diferencias), "sectores_ms": diferencias}
