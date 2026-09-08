# Single VM / HTTPS deployment

This option adds TLS termination through Traefik on top of the existing Docker Compose stack.

## Files

- Compose base: [../docker-compose/docker-compose.yml](../docker-compose/docker-compose.yml)
- Traefik overlay: [../docker-compose/docker-compose.traefik.yml](../docker-compose/docker-compose.traefik.yml)
- Traefik config: [traefik.yml](traefik.yml)

## Quick start

```bash
cp .env.example .env
# set APP_HOST and ACME_EMAIL in .env

docker compose -f docker-compose/docker-compose.yml -f docker-compose/docker-compose.traefik.yml --env-file .env up -d
```

## Access

The frontend is served at `https://$APP_HOST`.

## Notes

- Traefik handles TLS and the Let's Encrypt challenge.
- **This is the Compose path only.** It routes by Docker labels and mounts the
  Docker socket, so none of it applies to Kubernetes. On a cluster, Traefik is
  an ingress controller — install it there (Hostman ships it as a one-click
  add-on) and the Helm chart's Ingress reaches it with
  `ingress.className=traefik`; the certificate then comes from cert-manager,
  not from the ACME resolver below. See
  [../helm/apowerb-chart/README.md](../helm/apowerb-chart/README.md).
- This path is intended for a single self-hosted VM with a public hostname.
- Run the commands from the repository ROOT: the Compose files live in
  `docker-compose/`, and the root `docker-compose.yml` is the Hostman file,
  not this stack.
