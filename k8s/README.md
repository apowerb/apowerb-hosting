# Kubernetes

Deployment is done with the **Helm chart** — [`helm/apowerb-chart`](../helm/apowerb-chart/README.md),
published at `oci://registry-1.docker.io/apowerb/apowerb-chart`. It covers the
backend, the interface, PostgreSQL, th2etl and its seed, th2pulse, the
OpenTelemetry collector, the data volume and the Ingress.

This folder now contains only what lives **alongside** a release: cluster-scoped
objects that an application's chart should not create.

## `cert-manager/`

The Let's Encrypt issuer. An installed cert-manager issues nothing until a
`ClusterIssuer` exists.

```bash
kubectl apply -f k8s/cert-manager/cluster-issuer-letsencrypt.yaml
kubectl get clusterissuer            # expect READY=True
```

Then the chart's Ingress hooks into it:

```bash
--set ingress.enabled=true \
--set ingress.className=traefik \
--set ingress.host=<the public name> \
--set ingress.tlsEnabled=true \
--set ingress.annotations."cert-manager\.io/cluster-issuer"=letsencrypt-prod
```

Test the chain with `letsencrypt-staging` first: its certificates are not
trusted by browsers, but its quotas are generous. Production blocks for a week
after five failures within an hour.

## The old manifests

`00-namespace.yaml` … `05-ingress.yaml` described a deployment that predates the
chart: no th2etl, no th2pulse, no collector, no volume for imported files, an
Ingress with `ingressClassName: nginx` on `apowerb.local`, and secrets to fill
in by hand. `kubectl apply -f k8s/` would therefore install an incomplete
stack that *looks like* the right one. They are kept while we check that nobody
uses them; use the chart.
