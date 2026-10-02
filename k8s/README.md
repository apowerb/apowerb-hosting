# Kubernetes with `kubectl` alone

Two ways to install apowerb on a cluster: the **Helm chart**
([`helm/apowerb-chart`](../helm/apowerb-chart/README.md)), or the plain
manifests in this folder, applied with `kubectl` — no Helm on your machine or
in the cluster.

Both install the same stack: backend, interface, PostgreSQL, th2etl and its
seed `Job`, th2pulse, the OpenTelemetry collector and the data volume. The
manifests are **rendered from the chart** by
[`render_k8s_manifests.py`](../.github/scripts/render_k8s_manifests.py), and a
check fails whenever the two differ — so they cannot fall behind it. Do not
edit them by hand: change the chart, then re-run the script.

| Path | What it is |
| --- | --- |
| `apowerb/` | the whole stack, without a public address |
| `apowerb-public/` | the Ingress, and the backend Deployment carrying the public URL |
| `cert-manager/` | the Let's Encrypt issuers (cluster-wide) |
| `traefik/` | the HTTP → HTTPS redirect Middleware |

The cluster must have a default storage class first — see the docs' Kubernetes
page for the checks, the ingress controller and cert-manager.

## 1. The Secret

```bash
scripts/generate-k8s-secret.sh          # writes k8s/secret.yaml, mode 600
```

It holds real credentials: `k8s/secret.yaml` is in `.gitignore`. The script
refuses to overwrite an existing file — a new `ENCRYPT_KEY` would make every
connected integration unreadable, and a new `DB_PASSWORD` would no longer match
the database. Back the file up.

Optional credentials (a shared model key, SMTP, OAuth clients, S3, the first
administrator's password) are listed at the end of the file: add the ones you
use, never an empty one.

## 2. Install

```bash
kubectl apply -f k8s/apowerb/00-namespace.yaml -f k8s/secret.yaml
kubectl apply -f k8s/apowerb/
kubectl -n apowerb get pods
```

Six pods `Running` and `apowerb-th2etl-seed` `Completed`. A few restarts of
th2etl and th2pulse while PostgreSQL starts are expected. Reach the interface
with `kubectl -n apowerb port-forward svc/apowerb-frontend 13000:3000`.

## 3. A public address

`apowerb-public/` is written for `apowerb.example.com`, Traefik, and the
**staging** Let's Encrypt issuer. Copy it, put your own values in, then apply
the copy:

```bash
kubectl apply -f k8s/cert-manager/cluster-issuer-letsencrypt.yaml
cp -r k8s/apowerb-public my-public
sed -i.bak 's/apowerb\.example\.com/apowerb.your-domain.tld/' my-public/*.yaml
kubectl apply -f my-public/
kubectl -n apowerb get certificate
```

The backend Deployment in `apowerb-public/` replaces the one from `apowerb/`:
the public URL feeds the CORS origins and the OAuth callbacks, so it must not
be left out. With ingress-nginx, change `ingressClassName` and the issuer's
solver class. Once the staging certificate is `READY`, switch the
`cert-manager.io/cluster-issuer` annotation to `letsencrypt-prod` and delete
the `apowerb-tls` secret.

To close port 80 with Traefik:

```bash
kubectl apply -f k8s/traefik/redirect-https.yaml
kubectl -n apowerb annotate ingress apowerb \
  traefik.ingress.kubernetes.io/router.middlewares=apowerb-redirect-https@kubernetescrd
```

## 4. Upgrading

Pull this repository and keep the same `secret.yaml` — never a regenerated
one. The seed `Job` is immutable once created: delete it first so the new one
runs.

```bash
kubectl -n apowerb delete job apowerb-th2etl-seed --ignore-not-found
kubectl apply -f k8s/apowerb/
```

With a public address, refresh your copy of `apowerb-public/` the same way as
in step 3, and do **not** apply `apowerb/backend-deployment.yaml`: it has no
public URL, and applying it would remove that URL from the running backend —
CORS and OAuth callbacks break until the public copy is applied again.

```bash
kubectl -n apowerb delete job apowerb-th2etl-seed --ignore-not-found
for f in k8s/apowerb/*.yaml; do
  [ "${f##*/}" = backend-deployment.yaml ] || kubectl apply -f "$f"
done
kubectl apply -f my-public/
```

## Removing

`kubectl delete -f k8s/apowerb/` deletes the namespace, and with it both
volumes: the database and the files the backend wrote. Unlike the chart,
nothing here protects them. To stop the stack and keep the data, delete the
workloads only and leave `00-namespace.yaml` and `data-pvc.yaml` alone — the
database's claim survives its StatefulSet:

```bash
for f in k8s/apowerb/*.yaml; do
  case "$f" in */00-namespace.yaml|*/data-pvc.yaml) ;; *) kubectl delete -f "$f" --ignore-not-found ;; esac
done
```
