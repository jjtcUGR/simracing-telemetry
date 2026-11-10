"""Read API: ranking de setups, detalle de sesiones y comparativas, con caché en Redis."""

import logging
from contextlib import asynccontextmanager
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException, Query, Request, Response

from simracing import __version__
from simracing.comun.api import (
    comprobar_dependencias,
    instalar_manejadores_errores,
    respuesta_salud,
)
from simracing.comun.calculos import comparar_vueltas, ranking_setups
from simracing.comun.config import Config
from simracing.comun.datos import CacheRedis, RepositorioMongo, clave_cache_setups, cliente_redis

SERVICIO = "busqueda"
log = logging.getLogger(__name__)

_CAMPOS_RANKING = (
    "id_sesion",
    "piloto",
    "juego",
    "vehiculo",
    "circuito",
    "condiciones",
    "mejor_vuelta_ms",
    "consistencia_ms",
    "puntuacion",
    "setup",
)


def _publica(sesion: dict) -> dict:
    sesion = dict(sesion)
    sesion["id_sesion"] = sesion.pop("_id")
    return sesion


def crear_app(config: Config | None = None, repo=None, cache=None) -> FastAPI:

    @asynccontextmanager
    async def ciclo_de_vida(app: FastAPI):
        redis = None
        if app.state.repo is None:
            app.state.repo = RepositorioMongo(app.state.config.mongo_url, app.state.config.mongo_db)
        if app.state.cache is None:
            redis = cliente_redis(app.state.config.redis_url)
            app.state.cache = CacheRedis(redis)
        log.info("servicio iniciado", extra={"version": __version__})
        yield
        if redis is not None:
            await redis.aclose()
        await app.state.repo.cerrar()

    app = FastAPI(
        title="SimRacing Telemetry · Búsqueda", version=__version__, lifespan=ciclo_de_vida
    )
    app.state.config = config or Config.desde_entorno()
    app.state.repo = repo
    app.state.cache = cache
    instalar_manejadores_errores(app)

    @app.get("/api/setups")
    async def buscar_setups(
        request: Request,
        response: Response,
        vehiculo: str | None = None,
        circuito: str | None = None,
        juego: str | None = None,
        condiciones: Literal["seco", "mojado"] | None = None,
        limite: Annotated[int, Query(ge=1, le=100)] = 20,
    ) -> list[dict]:
        if not vehiculo or not circuito:
            raise HTTPException(
                status_code=400, detail="los parámetros vehiculo y circuito son obligatorios"
            )
        clave = clave_cache_setups(vehiculo, circuito, juego, condiciones, limite)
        cache = request.app.state.cache
        try:
            en_cache = await cache.obtener(clave)
        except Exception:
            log.warning("cache no disponible", exc_info=True)
            en_cache = None
        if en_cache is not None:
            response.headers["X-Cache"] = "HIT"
            return en_cache

        filtro = {"vehiculo": vehiculo, "circuito": circuito}
        if juego:
            filtro["juego"] = juego
        if condiciones:
            filtro["condicion"] = condiciones
        entradas = await request.app.state.repo.buscar_setups(filtro)
        resultado = [
            {k: e.get(k) for k in _CAMPOS_RANKING} for e in ranking_setups(entradas, limite)
        ]
        try:
            await cache.guardar(clave, resultado, request.app.state.config.cache_ttl_s)
        except Exception:
            log.warning("no se pudo guardar en cache", exc_info=True)
        response.headers["X-Cache"] = "MISS"
        return resultado

    @app.get("/api/sesiones/{id_sesion}")
    async def obtener_sesion(id_sesion: str, request: Request) -> dict:
        sesion = await request.app.state.repo.obtener_sesion(id_sesion)
        if sesion is None:
            raise HTTPException(status_code=404, detail="la sesión no existe")
        return _publica(sesion)

    @app.get("/api/comparativa")
    async def comparar(
        request: Request, sesion_a: str | None = None, sesion_b: str | None = None
    ) -> dict:
        if not sesion_a or not sesion_b:
            raise HTTPException(
                status_code=400, detail="los parámetros sesion_a y sesion_b son obligatorios"
            )
        repo = request.app.state.repo
        a, b = await repo.obtener_sesion(sesion_a), await repo.obtener_sesion(sesion_b)
        if a is None or b is None:
            raise HTTPException(status_code=404, detail="alguna de las sesiones no existe")
        if a.get("estado") != "procesada" or b.get("estado") != "procesada":
            raise HTTPException(status_code=409, detail="alguna sesión aún no está procesada")
        if a["circuito"] != b["circuito"]:
            raise HTTPException(status_code=409, detail="las sesiones son de circuitos distintos")
        sectores_a = a["analisis"].get("mejor_vuelta_sectores_ms")
        sectores_b = b["analisis"].get("mejor_vuelta_sectores_ms")
        if not sectores_a or not sectores_b:
            raise HTTPException(status_code=409, detail="alguna sesión no tiene vueltas válidas")
        try:
            diferencia = comparar_vueltas(sectores_a, sectores_b)
        except ValueError as e:
            raise HTTPException(status_code=409, detail=str(e)) from e
        return {"sesion_a": sesion_a, "sesion_b": sesion_b, "circuito": a["circuito"], **diferencia}

    @app.get("/health")
    async def salud(request: Request):
        estado = await comprobar_dependencias(
            {"mongodb": request.app.state.repo, "redis": request.app.state.cache}
        )
        return respuesta_salud(SERVICIO, estado)

    return app
