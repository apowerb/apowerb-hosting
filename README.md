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

- Docker Hub chart: [oci://registry-1.docker.io/apowerb/apowerb](https://hub.docker.com/r/apowerb/apowerb)
- GitHub Container Registry chart: [oci://ghcr.io/apowerb/apowerb](https://github.com/orgs/apowerb/packages)

## Deployment options

- [Docker Compose](docker/README.md)
- [Kubernetes](k8s/README.md)
- [Helm](helm/apowerb/README.md)
- [Single VM / HTTPS with Traefik](traefik/README.md)
- [Release publishing workflow](.github/workflows/README.md)

### 1. Docker Compose

Use the published images from Docker Hub.

```bash
cp .env.example .env
./scripts/generate-secrets.sh

docker compose up -d
```

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
helm upgrade --install apowerb ./helm/apowerb \
  --namespace apowerb \
  --create-namespace \
  --values ./helm/apowerb/values.yaml
```

To enable ingress, set `ingress.enabled: true` in `helm/apowerb/values.yaml` or use the example in [k8s/05-ingress.yaml](k8s/05-ingress.yaml).

### 4. Single VM / HTTPS with Traefik

For a single-host deployment, overlay the Traefik HTTPS compose file on top of the existing stack.

```bash
cp .env.example .env
# set APP_HOST and ACME_EMAIL in .env

docker compose -f docker-compose.yml -f docker-compose.traefik.yml up -d
```

The app is served through `https://$APP_HOST`.

### 5. Helm release publishing

Release-only publishing is handled by [.github/workflows/publish-dockerhub-helm.yml](.github/workflows/publish-dockerhub-helm.yml).

Required repository secrets:

- `DOCKERHUB_USERNAME`
- `DOCKERHUB_TOKEN`

The workflow packages the chart and pushes the same OCI artifact to both registries.

Install from the published release:

```bash
helm install apowerb oci://registry-1.docker.io/apowerb/apowerb --version 0.1.0
```

```bash
helm install apowerb oci://ghcr.io/apowerb/apowerb --version 0.1.0
```

## Notes

- `ENCRYPT_KEY` is required for startup and must be preserved.
- `scripts/generate-secrets.sh` creates the local secret values needed by the stack.
- The service ports are configured through `.env`.
