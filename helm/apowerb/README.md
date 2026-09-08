# Helm chart deployment

This chart packages the full stack for a Helm-based deployment: the backend,
the interface, PostgreSQL, and — since 0.2.0 — the three services the Compose
stack already ran, plus a volume for what the backend writes to disk.

| Component | Enabled by default | What it is for |
|---|---|---|
| backend, frontend, PostgreSQL | yes | the product |
| `th2etl` + seed **Job** | yes | scheduled pipelines. Without an API key the backend reports orchestration as *not configured* and the screen says so |
| `th2pulse` | yes | the log and trace store the Logging screen reads |
| `otel-collector` | yes | ships the backend's traces and logs into `th2pulse` |
| `PersistentVolumeClaim` | yes | BI uploads, agent uploads, artifacts (`RUNTIME_ROOT=/data`) |

Each one is a single switch: `th2etl.enabled`, `th2pulse.enabled`,
`otelCollector.enabled`, `persistence.enabled`.

## OCI locations

- Docker Hub chart: https://hub.docker.com/r/apowerb/apowerb
- GitHub Container Registry chart: https://github.com/orgs/apowerb/packages

## Install from source

Three secrets have to be generated first. The chart **refuses to install**
without the two `th2pulse` tokens — that service does not start without them,
so failing at install is the honest moment to say it.

```bash
helm upgrade --install apowerb ./helm/apowerb \
  --namespace apowerb --create-namespace \
  --set backend.env.encryptKey="$(openssl rand -base64 32)" \
  --set th2etl.apiKey="$(openssl rand -hex 32)" \
  --set th2pulse.ingestToken="$(openssl rand -hex 32)" \
  --set th2pulse.queryToken="$(openssl rand -hex 32)" \
  --set postgres.password="$(openssl rand -hex 16)"
```

Keep those values: `helm upgrade` without them would rewrite the Secret with
empty strings. A `values-secrets.yaml` outside version control, passed with
`--values`, is the usual way.

## Install from a published release

> ⚠️ **Aucune version de ce chart n'est publiée pour l'instant.** Le workflow
> `release-helm.yml` échoue à chaque push sur `main` — `chart-releaser` sort en
> `exit status 128` faute de branche `gh-pages`, et les huit derniers runs sont
> tous en échec. Il n'existe donc ni tag `apowerb-x.y.z`, ni release, ni chart
> sur les deux registres, malgré les commandes ci-dessous.
>
> C'est réparable en une ligne (créer la branche `gh-pages`), mais publier
> viendra **après** un premier `helm install` réussi sur un vrai cluster : ce
> chart n'a encore été vérifié que par `helm lint` et `kubeconform`. En
> attendant, il s'installe depuis les sources — c'est la section précédente.

Docker Hub:

```bash
helm install apowerb oci://registry-1.docker.io/apowerb/apowerb --version 0.2.0
```

GitHub Container Registry:

```bash
helm install apowerb oci://ghcr.io/apowerb/apowerb --version 0.2.0
```

## A smaller stack

Nothing beyond the product itself is mandatory:

```bash
helm upgrade --install apowerb ./helm/apowerb \
  --set th2etl.enabled=false \
  --set th2pulse.enabled=false \
  --set otelCollector.enabled=false \
  --set backend.env.encryptKey="$(openssl rand -base64 32)"
```

Seven objects instead of sixteen. The interface then says which features are
not configured rather than failing on them — that is the point of
`GET /api/config/setup` and of the **Admin → Configuration** screen.

## Storage

`persistence.enabled=true` mounts one volume on `persistence.mountPath`
(`/data`) and points `RUNTIME_ROOT` at it. Everything the backend writes to
disk lives under it: `bi_store` (imported CSV/Excel files when S3 is not
configured), `uploads`, `artifacts_store`, `agents_pool`.

- Without the volume, an imported CSV is gone at the next backend restart —
  and so is the dashboard that reads it. `agents_pool` is the exception: it is
  regenerated from the database.
- The claim is `ReadWriteOnce` by default, so the backend stays at one replica
  unless the storage class offers `ReadWriteMany`.
- The claim carries `helm.sh/resource-policy: keep`: `helm uninstall` leaves
  the data behind rather than deleting the uploads with the release.
- Configuring S3 (`storage_mode`, `S3_*`) makes BI files bypass the disk
  entirely; the volume then only holds uploads and artifacts.

## Optional ingress

Enable ingress in `values.yaml` with `ingress.enabled: true`.

## The seed is a Job, deliberately

`th2etl-seed` posts the default pipelines and exits. As a Deployment,
Kubernetes would restart a container that exited 0 — a `CrashLoopBackOff` on a
success, which is precisely what `restart: "no"` avoids in Compose. It runs as
a `post-install,post-upgrade` hook and retries while th2etl migrates the
database (`th2etl.seed.attempts` × `th2etl.seed.delaySeconds`).

```bash
kubectl -n apowerb logs job/apowerb-th2etl-seed
```

## Checks that do not need a cluster

```bash
helm lint helm/apowerb
helm template rel helm/apowerb --set th2pulse.ingestToken=x --set th2pulse.queryToken=y | \
  kubeconform -strict -summary -kubernetes-version 1.30.0
```

## Notes

The chart standardizes defaults for namespace, storage, secrets, ingress, and
resource requests.
