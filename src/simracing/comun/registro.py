"""Logs estructurados en JSON por stdout, para que el proveedor cloud pueda indexarlos."""

import json
import logging
import sys
from datetime import UTC, datetime

_CAMPOS_ESTANDAR = set(logging.makeLogRecord({}).__dict__) | {
    "message",
    "asctime",
    "color_message",  # uvicorn lo añade con códigos de color de terminal
}


class FormatoJSON(logging.Formatter):
    def __init__(self, servicio: str) -> None:
        super().__init__()
        self.servicio = servicio

    def format(self, record: logging.LogRecord) -> str:
        entrada = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "nivel": record.levelname,
            "servicio": self.servicio,
            "logger": record.name,
            "mensaje": record.getMessage(),
        }
        extra = {k: v for k, v in record.__dict__.items() if k not in _CAMPOS_ESTANDAR}
        entrada.update(extra)
        if record.exc_info:
            entrada["excepcion"] = self.formatException(record.exc_info)
        return json.dumps(entrada, ensure_ascii=False, default=str)


def configurar_registro(servicio: str, nivel: str = "INFO") -> None:
    manejador = logging.StreamHandler(sys.stdout)
    manejador.setFormatter(FormatoJSON(servicio))
    raiz = logging.getLogger()
    raiz.handlers[:] = [manejador]
    raiz.setLevel(nivel)
