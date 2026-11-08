"""Configuración leída de variables de entorno (factor III de las aplicaciones Twelve-Factor)."""

import os
from dataclasses import dataclass


def _obligatoria(nombre: str) -> str:
    valor = os.environ.get(nombre, "").strip()
    if not valor:
        raise RuntimeError(f"Falta la variable de entorno obligatoria {nombre}")
    return valor


@dataclass(frozen=True)
class Config:
    mongo_url: str
    mongo_db: str
    redis_url: str
    api_tokens: frozenset[str]
    salt_seudonimo: str
    stream: str = "sesiones"
    grupo: str = "analisis"
    cache_ttl_s: int = 60
    log_level: str = "INFO"

    @classmethod
    def desde_entorno(cls) -> "Config":
        tokens = frozenset(
            t.strip() for t in os.environ.get("API_TOKENS", "").split(",") if t.strip()
        )
        return cls(
            mongo_url=_obligatoria("MONGO_URL"),
            mongo_db=os.environ.get("MONGO_DB", "simracing"),
            redis_url=_obligatoria("REDIS_URL"),
            api_tokens=tokens,
            salt_seudonimo=os.environ.get("SALT_SEUDONIMO", ""),
            stream=os.environ.get("REDIS_STREAM", "sesiones"),
            grupo=os.environ.get("REDIS_GRUPO", "analisis"),
            cache_ttl_s=int(os.environ.get("CACHE_TTL_S", "60")),
            log_level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        )
