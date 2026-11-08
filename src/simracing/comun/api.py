"""Piezas comunes de las APIs HTTP: autenticación, formato de errores y health check."""

import asyncio
import hashlib
import logging
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

log = logging.getLogger(__name__)
_bearer = HTTPBearer(auto_error=False)

_CODIGOS = {
    400: "peticion_incorrecta",
    401: "no_autorizado",
    404: "no_encontrado",
    409: "conflicto",
    503: "no_disponible",
}


def seudonimo(token: str, sal: str) -> str:
    """Identificador estable del piloto que no permite recuperar el token (RGPD)."""
    return hashlib.sha256(f"{sal}:{token}".encode()).hexdigest()[:16]


async def piloto_autenticado(
    request: Request,
    credenciales: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> str:
    config = request.app.state.config
    if credenciales is None or credenciales.credentials not in config.api_tokens:
        raise HTTPException(status_code=401, detail="token ausente o no válido")
    return seudonimo(credenciales.credentials, config.salt_seudonimo)


def instalar_manejadores_errores(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def _validacion(_: Request, exc: RequestValidationError) -> JSONResponse:
        errores = [
            {"campo": ".".join(str(p) for p in e["loc"] if p != "body"), "mensaje": e["msg"]}
            for e in exc.errors()
        ]
        return JSONResponse(status_code=422, content={"error": "validacion", "detalle": errores})

    @app.exception_handler(HTTPException)
    async def _http(_: Request, exc: HTTPException) -> JSONResponse:
        codigo = _CODIGOS.get(exc.status_code, "error")
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": codigo, "detalle": exc.detail},
            headers=getattr(exc, "headers", None),
        )


async def comprobar_dependencias(dependencias: dict[str, Any], timeout_s: float = 2.0) -> dict:
    """Hace `ping()` a todas las dependencias en paralelo y devuelve {nombre: "ok" | "error"}."""

    async def comprobar(nombre: str, dep: Any) -> str:
        try:
            await asyncio.wait_for(dep.ping(), timeout=timeout_s)
            return "ok"
        except Exception:
            log.warning("dependencia no disponible", extra={"dependencia": nombre})
            return "error"

    resultados = await asyncio.gather(*(comprobar(n, d) for n, d in dependencias.items()))
    return dict(zip(dependencias, resultados, strict=True))


def respuesta_salud(servicio: str, estado: dict[str, str]) -> JSONResponse:
    ok = all(v == "ok" for v in estado.values())
    return JSONResponse(
        status_code=200 if ok else 503,
        content={"status": "ok" if ok else "error", "service": servicio, "dependencias": estado},
    )
