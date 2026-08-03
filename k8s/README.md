# Kubernetes deployment

Use the manifests in this folder to deploy the same stack on a Kubernetes cluster.

## Resources

This folder includes:

- namespace
- secrets
- Postgres
- backend deployment
- frontend deployment
- ingress example

## Apply

```bash
kubectl apply -f k8s/
```

## Expected services

- `apowerb` API service
- `apowerb-ui` frontend service
- Postgres service for the database

## Ingress

The sample ingress is available in [05-ingress.yaml](05-ingress.yaml).

## Notes

This path is the raw Kubernetes deployment option. For a packaged deployment, use the Helm chart in the `helm/apowerb` folder.
