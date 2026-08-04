# Docker Compose deployment

Use this option to run the stack from the published container images.

## Files

- Compose entrypoint: [docker-compose.yml](docker-compose.yml)
- Traefik overlay: [docker-compose.traefik.yml](docker-compose.traefik.yml)
- Environment template: [../.env.example](../.env.example)
- Secret bootstrap script: [../scripts/generate-secrets.sh](../scripts/generate-secrets.sh)

## Prerequisites

- Docker Engine
- Docker Compose v2
- A local `.env` file created from `.env.example`

## Quick start

1. Copy the environment template.
2. Optional but recommended: run the bootstrap helper to populate missing secret values in `.env`.
3. Start the stack.

Run these from the repository root. The Compose file lives in this folder, so
it has to be named explicitly — there is none at the root.

```bash
cp .env.example .env
./scripts/generate-secrets.sh

docker compose -f docker-compose/docker-compose.yml --env-file .env up -d
```

To check that the result actually works — schema, sign-up, sign-in, and an agent
answering — follow [TESTING.md](TESTING.md).

## What this starts

The Compose stack runs three services:

- `postgres` on its internal Docker network
- `apowerb` backend on port `8000`
- `apowerb-ui` frontend on port `3000`

## Published images

The stack uses the published images below:

- Backend: `apowerb/apowerb`
- Frontend: `apowerb/apowerb-ui`

These can be overridden in `.env` with:

- `APOWERB_BACKEND_IMAGE`
- `APOWERB_BACKEND_TAG`
- `APOWERB_FRONTEND_IMAGE`
- `APOWERB_FRONTEND_TAG`

## Important environment variables

The Compose stack depends on these values from `.env`:

- `DB_NAME`
- `DB_USER`
- `DB_PASSWORD`
- `DB_SSLMODE`
- `ENCRYPT_KEY`
- `TEST_TOKEN`
- `TH2AGENT_PORT`
- `FRONT_PORT`
- `PUBLIC_API_URL`

## Secrets

`ENCRYPT_KEY` and `TEST_TOKEN` must be present before startup.
The helper script in [../scripts/generate-secrets.sh](../scripts/generate-secrets.sh) is a bootstrap convenience that fills missing values in `.env` without overwriting existing ones.

## Useful commands

```bash
docker compose -f docker-compose/docker-compose.yml --env-file .env ps
docker compose -f docker-compose/docker-compose.yml --env-file .env logs -f apowerb
docker compose -f docker-compose/docker-compose.yml --env-file .env logs -f apowerb-ui
docker compose -f docker-compose/docker-compose.yml --env-file .env down
```

## Single-host HTTPS overlay

For a public VM or a self-hosted host, run the overlay that adds Traefik:

```bash
docker compose -f docker-compose/docker-compose.yml -f docker-compose/docker-compose.traefik.yml --env-file .env up -d
```

This requires `APP_HOST` and `ACME_EMAIL` in `.env`.
