"""Acceso a MongoDB (persistencia) y Redis (cola de eventos y caché)."""

import json
import logging
from typing import Any

import redis.asyncio as aioredis
from pymongo import ASCENDING, AsyncMongoClient
from redis.exceptions import ResponseError

log = logging.getLogger(__name__)


class RepositorioMongo:
    """Colecciones: `sesiones` (sesiones recibidas y su análisis) y `setups` (ranking)."""

    def __init__(self, url: str, base_datos: str) -> None:
        self._cliente: AsyncMongoClient = AsyncMongoClient(url, serverSelectionTimeoutMS=3000)
        self._db = self._cliente[base_datos]
        self.sesiones = self._db["sesiones"]
        self.setups = self._db["setups"]

    async def preparar(self) -> None:
        await self.setups.create_index(
            [("vehiculo", ASCENDING), ("circuito", ASCENDING), ("mejor_vuelta_ms", ASCENDING)]
        )

    async def ping(self) -> None:
        await self._db.command("ping")

    async def cerrar(self) -> None:
        await self._cliente.close()

    async def insertar_sesion(self, sesion: dict[str, Any]) -> None:
        await self.sesiones.insert_one(sesion)

    async def obtener_sesion(self, id_sesion: str) -> dict[str, Any] | None:
        return await self.sesiones.find_one({"_id": id_sesion})

    async def marcar_procesada(self, id_sesion: str, analisis: dict[str, Any]) -> None:
        await self.sesiones.update_one(
            {"_id": id_sesion}, {"$set": {"estado": "procesada", "analisis": analisis}}
        )

    async def guardar_setup(self, entrada: dict[str, Any]) -> None:
        await self.setups.replace_one({"_id": entrada["_id"]}, entrada, upsert=True)

    async def mejor_tiempo(self, filtro: dict[str, Any]) -> int | None:
        doc = await self.setups.find_one(filtro, sort=[("mejor_vuelta_ms", ASCENDING)])
        return doc["mejor_vuelta_ms"] if doc else None

    async def buscar_setups(self, filtro: dict[str, Any], limite: int = 500) -> list[dict]:
        cursor = self.setups.find(filtro).sort("mejor_vuelta_ms", ASCENDING).limit(limite)
        return await cursor.to_list(length=None)


class ColaRedis:
    """Redis Streams con grupo de consumidores: cada evento lo procesa un único worker."""

    def __init__(self, cliente: aioredis.Redis, stream: str, grupo: str) -> None:
        self._r = cliente
        self.stream = stream
        self.grupo = grupo

    async def ping(self) -> None:
        await self._r.ping()

    async def publicar(self, id_sesion: str) -> None:
        await self._r.xadd(self.stream, {"id_sesion": id_sesion}, maxlen=100_000, approximate=True)

    async def asegurar_grupo(self) -> None:
        try:
            await self._r.xgroup_create(self.stream, self.grupo, id="0", mkstream=True)
        except ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise

    async def leer(self, consumidor: str, cuantos: int, bloqueo_ms: int) -> list[tuple[str, str]]:
        respuesta = await self._r.xreadgroup(
            self.grupo, consumidor, {self.stream: ">"}, count=cuantos, block=bloqueo_ms
        )
        return [(mid, campos["id_sesion"]) for _, msgs in respuesta or [] for mid, campos in msgs]

    async def reclamar_pendientes(
        self, consumidor: str, inactivo_ms: int, cuantos: int = 10
    ) -> list[tuple[str, str]]:
        """Recupera eventos que otro worker leyó pero no confirmó (p. ej. porque se cayó)."""
        respuesta = await self._r.xautoclaim(
            self.stream, self.grupo, consumidor, min_idle_time=inactivo_ms, count=cuantos
        )
        mensajes = respuesta[1] if len(respuesta) > 1 else []
        return [(mid, campos["id_sesion"]) for mid, campos in mensajes if campos]

    async def confirmar(self, id_mensaje: str) -> None:
        await self._r.xack(self.stream, self.grupo, id_mensaje)


class CacheRedis:
    def __init__(self, cliente: aioredis.Redis) -> None:
        self._r = cliente

    async def ping(self) -> None:
        await self._r.ping()

    async def obtener(self, clave: str) -> Any | None:
        valor = await self._r.get(clave)
        return json.loads(valor) if valor is not None else None

    async def guardar(self, clave: str, valor: Any, ttl_s: int) -> None:
        await self._r.set(clave, json.dumps(valor, default=str), ex=ttl_s)

    async def invalidar(self, patron: str) -> int:
        borradas = 0
        async for clave in self._r.scan_iter(match=patron, count=100):
            borradas += await self._r.delete(clave)
        return borradas


def cliente_redis(url: str) -> aioredis.Redis:
    return aioredis.from_url(url, decode_responses=True, socket_timeout=10)


def clave_cache_setups(
    vehiculo: str, circuito: str, juego: str | None, condicion: str | None, limite: int
) -> str:
    return f"cache:setups:{vehiculo}:{circuito}:{juego or '*'}:{condicion or '*'}:{limite}"


def patron_cache_setups(vehiculo: str, circuito: str) -> str:
    return f"cache:setups:{vehiculo}:{circuito}:*"
