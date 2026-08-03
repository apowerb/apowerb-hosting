# Single VM / HTTPS deployment

This option adds TLS termination through Traefik on top of the existing Docker Compose stack.

## Files

- Compose base: [../docker-compose.yml](../docker-compose.yml)
- Traefik overlay: [../docker-compose.traefik.yml](../docker-compose.traefik.yml)
- Traefik config: [traefik.yml](traefik.yml)

## Quick start

```bash
cp .env.example .env
# set APP_HOST and ACME_EMAIL in .env

docker compose -f docker-compose.yml -f docker-compose.traefik.yml up -d
```

## Access

The frontend is served at `https://$APP_HOST`.

## Notes

- Traefik handles TLS and the Let's Encrypt challenge.
- This path is intended for a single self-hosted VM with a public hostname.
