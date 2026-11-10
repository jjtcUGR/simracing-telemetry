import asyncio
import signal
import socket

from simracing.analisis.worker import ejecutar
from simracing.comun.config import Config
from simracing.comun.datos import CacheRedis, ColaRedis, RepositorioMongo, cliente_redis
from simracing.comun.registro import configurar_registro


async def main() -> None:
    config = Config.desde_entorno()
    configurar_registro("analisis", config.log_level)
    redis = cliente_redis(config.redis_url)
    repo = RepositorioMongo(config.mongo_url, config.mongo_db)
    await repo.preparar()

    parar = asyncio.Event()
    bucle = asyncio.get_running_loop()
    for senal in (signal.SIGTERM, signal.SIGINT):
        bucle.add_signal_handler(senal, parar.set)

    try:
        await ejecutar(
            ColaRedis(redis, config.stream, config.grupo),
            repo,
            CacheRedis(redis),
            consumidor=socket.gethostname(),
            parar=parar,
        )
    finally:
        await redis.aclose()
        await repo.cerrar()


if __name__ == "__main__":
    asyncio.run(main())
