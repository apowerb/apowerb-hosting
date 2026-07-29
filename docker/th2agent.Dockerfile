# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# th2agent — le noyau open core (API FastAPI)
#
# Aucun `apt-get` : toutes les dependances natives arrivent en wheels
# precompiles. `psycopg2-binary` et `asyncpg` embarquent leur propre libpq,
# `cryptography` est distribue en wheel. Installer build-essential et
# libpq-dev n'apporterait rien et ajouterait une chaine de compilation
# complete a l'image.
#
# Effet de bord utile : la construction ne depend d'aucun miroir Debian, donc
# elle passe derriere un reseau qui filtre les depots de paquets.
# ---------------------------------------------------------------------------

FROM python:3.12-slim AS build

WORKDIR /app
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1

# Les metadonnees d'abord : tant que pyproject.toml ne bouge pas, Docker
# reutilise la couche d'installation et un changement de code ne reinstalle
# rien.
COPY pyproject.toml README.md ./
COPY src/ ./src/

RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip install .


FROM python:3.12-slim AS runtime

# Utilisateur non privilegie. Le conteneur ecrit dans ses repertoires de
# travail (agents_pool, artifacts_store, uploads) : ils lui appartiennent.
RUN useradd --create-home --uid 10001 th2

WORKDIR /app
COPY --from=build /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" PYTHONUNBUFFERED=1

# TH2AGENT_RUNTIME_ROOT rend les repertoires de travail configurables. Sans
# lui ils seraient resolus contre le repertoire courant, ce qui marche mais
# rend le montage d'un volume moins evident.
ENV TH2AGENT_RUNTIME_ROOT=/app/data
RUN mkdir -p /app/data && chown -R th2:th2 /app

USER th2
EXPOSE 8000

# Sonde en Python plutot qu'avec curl : elle evite d'installer un paquet
# systeme pour une requete HTTP que l'interpreteur deja present sait faire.
HEALTHCHECK --interval=30s --timeout=5s --start-period=45s --retries=3 \
    CMD python -c "import sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health', timeout=4).status == 200 else 1)"

CMD ["uvicorn", "th2agent.main:app", "--host", "0.0.0.0", "--port", "8000"]
