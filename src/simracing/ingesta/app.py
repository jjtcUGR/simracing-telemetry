"""Write API: valida las sesiones, las guarda como `pendiente` y avisa al worker por Redis."""

import logging
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, FastAPI, Request

from simracing import __version__
from simracing.comun.api import (
    comprobar_dependencias,
    instalar_manejadores_errores,
    piloto_autenticado,
    respuesta_salud,
)
from simracing.comun.config import Config
from simracing.comun.datos import ColaRedis, RepositorioMongo, cliente_redis
from simracing.comun.modelos import SesionEntrada

SERVICIO = "ingesta"
log = logging.getLogger(__name__)


def crear_app(config: Config | None = None, repo=None, cola=None) -> FastAPI:
    """Si no se inyectan `repo` y `cola` (como en los tests), se crean al arrancar."""

    @asynccontextmanager
    async def ciclo_de_vida(app: FastAPI):
        redis = None
        if app.state.repo is None:
            app.state.repo = RepositorioMongo(app.state.config.mongo_url, app.state.config.mongo_db)
        if app.state.cola is None:
            redis = cliente_redis(app.state.config.redis_url)
            app.state.cola = ColaRedis(redis, app.state.config.stream, app.state.config.grupo)
        log.info("servicio iniciado", extra={"version": __version__})
        yield
        if redis is not None:
            await redis.aclose()
        await app.state.repo.cerrar()

    app = FastAPI(
        title="SimRacing Telemetry · Ingesta", version=__version__, lifespan=ciclo_de_vida
    )
    app.state.config = config or Config.desde_entorno()
    app.state.repo = repo
    app.state.cola = cola
    instalar_manejadores_errores(app)

    @app.post("/api/telemetria", status_code=202)
    async def registrar_sesion(
        sesion: SesionEntrada,
        request: Request,
        piloto: Annotated[str, Depends(piloto_autenticado)],
    ) -> dict:
        id_sesion = uuid.uuid4().hex
        documento = {
            "_id": id_sesion,
            "piloto": piloto,
            "estado": "pendiente",
            "recibida": datetime.now(UTC).isoformat(),
            **sesion.model_dump(),
        }
        await request.app.state.repo.insertar_sesion(documento)
        await request.app.state.cola.publicar(id_sesion)
        log.info(
            "sesion recibida",
            extra={
                "id_sesion": id_sesion,
                "vueltas": len(sesion.vueltas),
                "circuito": sesion.circuito,
            },
        )
        return {"id_sesion": id_sesion, "estado": "pendiente"}

    @app.get("/health")
    async def salud(request: Request):
        estado = await comprobar_dependencias(
            {"mongodb": request.app.state.repo, "redis": request.app.state.cola}
        )
        return respuesta_salud(SERVICIO, estado)

    return app
