# syntax=docker/dockerfile:1
# Servicio de Búsqueda (Read API). Contexto de construcción: raíz del repositorio.
#   docker build -f services/busqueda/Dockerfile -t simracing-busqueda .

ARG PYTHON_IMAGE=python:3.13.13-slim-trixie

# ---------- Etapa 1: dependencias en un entorno virtual aislado ----------
FROM ${PYTHON_IMAGE} AS dependencias
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"
COPY requirements/base.txt requirements/api.txt /tmp/requirements/
RUN pip install --no-cache-dir -r /tmp/requirements/api.txt

# ---------- Etapa 2: imagen final mínima, sin herramientas de construcción ----------
FROM ${PYTHON_IMAGE} AS final
LABEL org.opencontainers.image.title="simracing-telemetry-busqueda" \
      org.opencontainers.image.description="Read API: ranking de setups, sesiones y comparativas" \
      org.opencontainers.image.source="https://github.com/jjtcUGR/simracing-telemetry"

ENV PATH="/opt/venv/bin:${PATH}" \
    PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PUERTO=8000

RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app

COPY --from=dependencias /opt/venv /opt/venv
WORKDIR /app
COPY src/simracing/__init__.py simracing/__init__.py
COPY src/simracing/comun simracing/comun
COPY src/simracing/busqueda simracing/busqueda

USER app
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/health', timeout=2)"]
CMD ["python", "-m", "simracing.busqueda"]
