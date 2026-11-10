"""Health check del worker (no expone HTTP): comprueba MongoDB y Redis y sale con 0 o 1."""

import asyncio
import sys

from simracing.comun.config import Config
from simracing.comun.datos import RepositorioMongo, cliente_redis


async def comprobar() -> bool:
    config = Config.desde_entorno()
    redis = cliente_redis(config.redis_url)
    repo = RepositorioMongo(config.mongo_url, config.mongo_db)
    try:
        await asyncio.wait_for(redis.ping(), timeout=2)
        await asyncio.wait_for(repo.ping(), timeout=2)
        return True
    except Exception:
        return False
    finally:
        await redis.aclose()
        await repo.cerrar()


if __name__ == "__main__":
    sys.exit(0 if asyncio.run(comprobar()) else 1)
