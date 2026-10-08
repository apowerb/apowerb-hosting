<div align="center">

<img src="https://avatars.githubusercontent.com/u/310538280?v=4&s=160" alt="apowerb" width="96" />

# apowerb-hosting

**Deployment assets for the open-source apowerb stack — Docker Compose, Kubernetes manifests and a Helm chart.**

[![Documentation](https://img.shields.io/badge/docs-apowerb.com-blue?style=for-the-badge&logo=googledocs&logoColor=white)](https://docs.apowerb.com/)
[![Docker](https://img.shields.io/docker/v/apowerb/apowerb?style=for-the-badge&logo=docker&logoColor=white&label=image)](https://hub.docker.com/r/apowerb/apowerb)
[![Helm](https://img.shields.io/badge/Helm-chart-0F1689?style=for-the-badge&logo=helm&logoColor=white)](https://github.com/apowerb/apowerb-hosting/tree/main/helm)
[![License](https://img.shields.io/badge/License-Apache_2.0-green.svg?style=for-the-badge)](LICENSE)
[![Discord](https://img.shields.io/badge/Community-Discord-5865F2?style=for-the-badge&logo=discord&logoColor=white)](https://discord.com/channels/1470717940075597896)

<p align="center">
  <a href="https://docs.apowerb.com/">Documentation</a> •
  <a href="https://docs.apowerb.com/quickstart">Quickstart</a> •
  <a href="https://docs.apowerb.com/api-reference/introduction">API Reference</a> •
  <a href="https://docs.apowerb.com/deployment/dockercompose">Deployment</a> •
  <a href="https://thaink2.com">thaink2</a>
</p>

</div>

---

This repository contains the deployment assets for the open-source **apowerb** stack.
It includes the service definitions for the FastAPI backend and the Next.js frontend,
and it is designed to run from published images or from a Kubernetes/Helm chart.

## Published assets

### Container images

- Backend image: [apowerb/apowerb on Docker Hub](https://hub.docker.com/r/apowerb/apowerb)
- Frontend image: [apowerb/apowerb-ui on Docker Hub](https://hub.docker.com/r/apowerb/apowerb-ui)

The GitHub Container Registry packages are not a pull source: measured on
2026-10-08, `ghcr.io` refuses an anonymous token for both (`403`). Pull from
Docker Hub.

### Helm chart OCI registries

- Docker Hub chart: [oci://registry-1.docker.io/apowerb/apowerb-chart](https://hub.docker.com/r/apowerb/apowerb-chart)

> GHCR was dropped on 2026-09-08: the push succeeded, but a package is born
> **private** in a GitHub organisation and `helm pull` answered `403` to an
> anonymous caller. Publishing where nobody can pull is not publishing.

> The `docker-compose.yml` at the repository root is **not** the self-hosted stack:
> it targets [Hostman App Platform](https://hostman.com), which reads a Compose file
> from the root and from nowhere else. It has no Postgres and expects a managed
> database. For a laptop or a plain VM, use `docker-compose/docker-compose.yml` --
> option 1 below.

## Deployment options

- [Docker Compose](docker-compose/README.md)
- [Kubernetes](k8s/README.md)
- [Helm](helm/apowerb-chart/README.md)

> **Docs come before deployment.** A PR that moves the chart — its name,
> its version, its path — fails as long as
> [`apowerb-docs`](https://github.com/apowerb/apowerb-docs) contradicts it. An
> **open** docs PR is enough to pass the guard: preparing both together is the
> expected practice, not a workaround. A line that deliberately cites the old
> state is marked `docs-in-sync: ignore`.
>
> On 8 September 2026, the site served a stale install command for an hour. It
> **worked** — the old chart can still be pulled — and installed the stack as it
> was before th2etl, th2pulse and the persistent volume. No error, no red
> check: it is this silence that
> `.github/workflows/docs-in-sync.yml` removes.
- [Single VM / HTTPS with Traefik](traefik/README.md)

### 1. Docker Compose

Use the published images from Docker Hub.

```bash
cp .env.example .env
./scripts/generate-secrets.sh

docker compose -f docker-compose/docker-compose.yml --env-file .env up -d
```

For the full Compose-specific details, including image overrides, port mapping, and secret handling, see [docker-compose/README.md](docker-compose/README.md).
To verify the result end to end, follow [docker-compose/TESTING.md](docker-compose/TESTING.md).

- Frontend: http://localhost:3000
- API: http://localhost:8000

### 2. Kubernetes

Plain manifests, applied with `kubectl` alone — rendered from the chart, so
both paths install the same stack. Step by step in [k8s/README.md](k8s/README.md).

```bash
scripts/generate-k8s-secret.sh
kubectl apply -f k8s/apowerb/00-namespace.yaml -f k8s/secret.yaml
kubectl apply -f k8s/apowerb/
```

### 3. Helm

Install the chart from the local source tree.

```bash
helm upgrade --install apowerb ./helm/apowerb-chart \
  --namespace apowerb \
  --create-namespace \
  --values ./helm/apowerb-chart/values.yaml
```

To enable ingress, set `ingress.enabled: true` in `helm/apowerb-chart/values.yaml` or, without Helm, use [k8s/apowerb-public/](k8s/apowerb-public/).

### 4. Single VM / HTTPS with Traefik

For a single-host deployment, overlay the Traefik HTTPS compose file on top of the Compose stack above.

```bash
cp .env.example .env
# set APP_HOST and ACME_EMAIL in .env

docker compose -f docker-compose/docker-compose.yml -f docker-compose/docker-compose.traefik.yml --env-file .env up -d
```

The app is served through `https://$APP_HOST`.

## After deploying, prove it

```bash
scripts/check-deployment.sh https://your-host.example
```

A container that is up proves nothing, and neither does a page that renders.
This probes the deployment from outside and exits non-zero if the frontend and
the backend are not the pair they should be -- the failure that twice left this
stack with a control panel rendering at `/admin` and answering 404 behind it.

Every assertion carries a witness, positive and negative, so a host answering
404 to everything fails the check instead of passing it.

## Notes

- `ENCRYPT_KEY` is required for startup and must be preserved.
- `scripts/generate-secrets.sh` creates the local secret values needed by the stack.
- The service ports are configured through `.env`.

## License

apowerb-hosting is distributed under the [Apache License 2.0](./LICENSE).
Copyright 2025-2026 thaink².

"apowerb" and "thaink²" are trademarks of thaink². The licence covers the code,
not the marks — see [TRADEMARK.md](https://github.com/apowerb/apowerb/blob/main/TRADEMARK.md).
