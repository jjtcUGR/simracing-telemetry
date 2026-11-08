import os

import uvicorn

from simracing.busqueda.app import SERVICIO, crear_app
from simracing.comun.registro import configurar_registro


def main() -> None:
    configurar_registro(SERVICIO, os.environ.get("LOG_LEVEL", "INFO").upper())
    uvicorn.run(
        crear_app(),
        host="0.0.0.0",  # dentro del contenedor hay que escuchar en todas las interfaces
        port=int(os.environ.get("PUERTO", "8000")),
        log_config=None,
        proxy_headers=True,
    )


if __name__ == "__main__":
    main()
