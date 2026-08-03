# Docker Compose deployment

This folder keeps the container build context used by the published Compose stack.

## Images

- Backend image: https://hub.docker.com/r/apowerb/apowerb
- Frontend image: https://hub.docker.com/r/apowerb/apowerb-ui
- OCI packages on GHCR: https://github.com/orgs/apowerb/packages

## Quick start

```bash
cp .env.example .env
./scripts/generate-secrets.sh

docker compose up -d
```

## Access

- Frontend: http://localhost:3000
- API: http://localhost:8000

## Notes

- The compose file references the published backend and frontend images.
- Environment overrides live in `.env`.
- `ENCRYPT_KEY` is required for the stack to start correctly.
