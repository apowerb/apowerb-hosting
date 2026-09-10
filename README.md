# apowerb-hosting

This repository contains the deployment assets for the open-source **apowerb** stack.
It includes the service definitions for the FastAPI backend and the Next.js frontend,
and it is designed to run from published images or from a Kubernetes/Helm chart.

## Published assets

### Container images

- Backend image: [apowerb/apowerb on Docker Hub](https://hub.docker.com/r/apowerb/apowerb)
- Frontend image: [apowerb/apowerb-ui on Docker Hub](https://hub.docker.com/r/apowerb/apowerb-ui)
- Backend package: [apowerb/apowerb on GitHub Container Registry](https://github.com/orgs/apowerb/packages)
- Frontend package: [apowerb/apowerb-ui on GitHub Container Registry](https://github.com/orgs/apowerb/packages)

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

> **La doc passe avant le déploiement.** Une PR qui déplace le chart — son nom,
> sa version, son chemin — échoue tant que
> [`apowerb-docs`](https://github.com/apowerb/apowerb-docs) la contredit. Une PR
> de doc **ouverte** suffit à passer le garde : préparer les deux ensemble est le
> geste attendu, pas une entorse. Une ligne qui cite volontairement l'ancien état
> se marque `docs-in-sync: ignore`.
>
> Le 8 septembre 2026, le site a servi pendant une heure une commande
> d'installation périmée. Elle **fonctionnait** — l'ancien chart est toujours
> tirable — et installait la pile d'avant th2etl, th2pulse et le volume
> persistant. Aucune erreur, aucun rouge : c'est ce silence que
> `.github/workflows/docs-in-sync.yml` supprime.
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

Apply the static manifests from the `k8s/` folder.

```bash
kubectl apply -f k8s/
```

### 3. Helm

Install the chart from the local source tree.

```bash
helm upgrade --install apowerb ./helm/apowerb-chart \
  --namespace apowerb \
  --create-namespace \
  --values ./helm/apowerb-chart/values.yaml
```

To enable ingress, set `ingress.enabled: true` in `helm/apowerb-chart/values.yaml` or use the example in [k8s/05-ingress.yaml](k8s/05-ingress.yaml).

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
