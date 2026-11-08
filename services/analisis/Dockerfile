# syntax=docker/dockerfile:1
# Worker de Análisis (sin HTTP). Contexto de construcción: raíz del repositorio.
#   docker build -f services/analisis/Dockerfile -t simracing-analisis .

# ---------- Etapa 1: dependencias (sin FastAPI ni Uvicorn: el worker no las necesita) ----------
FROM python:3.13.13-slim-trixie AS dependencias
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"
COPY requirements/base.txt /tmp/requirements/
RUN pip install --no-cache-dir -r /tmp/requirements/base.txt

# ---------- Etapa 2: imagen final mínima ----------
FROM python:3.13.13-slim-trixie AS final
LABEL org.opencontainers.image.title="simracing-telemetry-analisis" \
      org.opencontainers.image.description="Worker que analiza sesiones y actualiza el ranking de setups" \
      org.opencontainers.image.source="https://github.com/jjtcUGR/simracing-telemetry"

ENV PATH="/opt/venv/bin:${PATH}" \
    PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app

COPY --from=dependencias /opt/venv /opt/venv
WORKDIR /app
COPY src/simracing/__init__.py simracing/__init__.py
COPY src/simracing/comun simracing/comun
COPY src/simracing/analisis simracing/analisis

USER app
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD ["python", "-m", "simracing.analisis.salud"]
CMD ["python", "-m", "simracing.analisis"]
