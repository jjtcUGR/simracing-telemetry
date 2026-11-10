"""Bucle del worker: lee eventos `sesion.recibida`, analiza la sesión y actualiza el ranking."""

import asyncio
import logging
from datetime import UTC, datetime

from simracing.comun.calculos import analizar_sesion, puntuar_setup
from simracing.comun.datos import patron_cache_setups

log = logging.getLogger(__name__)

INACTIVIDAD_RECLAMO_MS = 30_000
"""Un evento sin confirmar durante 30 s se considera abandonado y otro worker lo reclama."""


async def procesar_sesion(id_sesion: str, repo, cache) -> bool:
    """Analiza una sesión. Es idempotente: procesarla dos veces deja el mismo resultado."""
    sesion = await repo.obtener_sesion(id_sesion)
    if sesion is None:
        log.warning("sesion inexistente", extra={"id_sesion": id_sesion})
        return False
    if sesion.get("estado") == "procesada":
        return True

    analisis = analizar_sesion(sesion["vueltas"])
    analisis["puntuacion_setup"] = None
    if analisis["mejor_vuelta_ms"] is not None:
        combinacion = {
            "juego": sesion["juego"],
            "vehiculo": sesion["vehiculo"],
            "circuito": sesion["circuito"],
            "condicion": sesion["condiciones"]["pista"],
        }
        record_previo = await repo.mejor_tiempo(combinacion)
        record = min(filter(None, [record_previo, analisis["mejor_vuelta_ms"]]))
        analisis["puntuacion_setup"] = puntuar_setup(
            analisis["mejor_vuelta_ms"], analisis["consistencia_ms"], record
        )
        await repo.guardar_setup(
            {
                "_id": id_sesion,
                "id_sesion": id_sesion,
                "piloto": sesion["piloto"],
                **combinacion,
                "condiciones": sesion["condiciones"],
                "setup": sesion["setup"],
                "mejor_vuelta_ms": analisis["mejor_vuelta_ms"],
                "consistencia_ms": analisis["consistencia_ms"],
                "registrada": datetime.now(UTC).isoformat(),
            }
        )
        await cache.invalidar(patron_cache_setups(sesion["vehiculo"], sesion["circuito"]))

    await repo.marcar_procesada(id_sesion, analisis)
    log.info(
        "sesion procesada",
        extra={
            "id_sesion": id_sesion,
            **{k: analisis[k] for k in ("mejor_vuelta_ms", "vuelta_ideal_ms", "puntuacion_setup")},
        },
    )
    return True


async def ciclo(cola, repo, cache, consumidor: str, bloqueo_ms: int = 5000) -> int:
    """Una iteración: reclama eventos abandonados, lee nuevos y los procesa. Devuelve cuántos."""
    mensajes = await cola.reclamar_pendientes(consumidor, INACTIVIDAD_RECLAMO_MS)
    mensajes += await cola.leer(consumidor, cuantos=10, bloqueo_ms=bloqueo_ms)
    procesados = 0
    for id_mensaje, id_sesion in mensajes:
        try:
            await procesar_sesion(id_sesion, repo, cache)
        except Exception:
            # Sin confirmar: el evento queda pendiente y se reintentará al reclamarlo.
            log.exception("error procesando sesion", extra={"id_sesion": id_sesion})
            continue
        await cola.confirmar(id_mensaje)
        procesados += 1
    return procesados


async def ejecutar(cola, repo, cache, consumidor: str, parar: asyncio.Event) -> None:
    await cola.asegurar_grupo()
    log.info("worker escuchando", extra={"consumidor": consumidor, "stream": cola.stream})
    while not parar.is_set():
        try:
            await ciclo(cola, repo, cache, consumidor)
        except Exception:
            log.exception("fallo en el bucle del worker; reintento en 2 s")
            await asyncio.sleep(2)
