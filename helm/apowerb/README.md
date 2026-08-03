# Helm chart deployment

This chart packages the full stack for a Helm-based deployment.

## OCI locations

- Docker Hub chart: https://hub.docker.com/r/apowerb/apowerb
- GitHub Container Registry chart: https://github.com/orgs/apowerb/packages

## Install from source

```bash
helm upgrade --install apowerb ./helm/apowerb \
  --namespace apowerb \
  --create-namespace \
  --values ./helm/apowerb/values.yaml
```

## Install from a published release

Docker Hub:

```bash
helm install apowerb oci://registry-1.docker.io/apowerb/apowerb --version 0.1.0
```

GitHub Container Registry:

```bash
helm install apowerb oci://ghcr.io/apowerb/apowerb --version 0.1.0
```

## Optional ingress

Enable ingress in `values.yaml` with `ingress.enabled: true`.

## Notes

The chart standardizes defaults for namespace, storage, secrets, ingress, and resource requests.
