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
| `th2forecast` | **no** | the forecasting engine (Chronos-2 + statsforecast) `POST /api/v1/forecast` relays to. Image `apowerb/th2forecast-py`, published per release of `apowerb/th2forecast` and pinned in `image.th2forecast.tag`; enabling it requires `th2forecast.apiToken` |
| `PersistentVolumeClaim` | yes | BI uploads, agent uploads, artifacts (`RUNTIME_ROOT=/data`) |

Each one is a single switch: `th2etl.enabled`, `th2pulse.enabled`,
`otelCollector.enabled`, `th2forecast.enabled`, `persistence.enabled`.

## OCI locations

- Docker Hub chart: https://hub.docker.com/r/apowerb/apowerb-chart
- Docker Hub images: https://hub.docker.com/r/apowerb/apowerb (the backend, not the chart)

## Install from source

Five values have to be generated first. The chart **refuses to install**
without four of them: `postgres.password` and `backend.env.encryptKey`, which
have no default on purpose, and the two `th2pulse` tokens — the backend and
th2pulse do not start without them, so failing at install is the honest moment
to say it.

```bash
helm upgrade --install apowerb ./helm/apowerb-chart \
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

The chart is published on **Docker Hub**, in the organization that already
ships the product images — but in a repository of its own,
`apowerb/apowerb-chart`:

```bash
helm upgrade --install apowerb oci://registry-1.docker.io/apowerb/apowerb-chart --version 0.4.22 \
  --namespace apowerb --create-namespace \
  --values values-secrets.yaml
```

`values-secrets.yaml` holds the five values above; without it, the install
stops on `postgres.password is empty`.

Versions published from 0.4.22 on are signed with cosign, keyless, by the
publishing workflow. To check that a chart comes from this repository:

```bash
cosign verify registry-1.docker.io/apowerb/apowerb-chart:0.4.22 \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  --certificate-identity-regexp '^https://github.com/apowerb/apowerb-hosting/\.github/workflows/publish-dockerhub-helm\.yml@'
```

> **Upgrading an existing install from 0.4.20 or earlier: check where the
> database lives before `helm upgrade`.** Since 0.4.21, PostgreSQL writes to
> `/var/lib/postgresql/data/pgdata` (a subdirectory of the volume) instead of
> its root: on an ext4 volume (OVH Cinder, most cloud block disks) the root's
> `lost+found` made `initdb` fail. An install that already ran — so on a
> volume without `lost+found` (k3s local-path, kind, NFS) — has its database
> at the root. After the upgrade PostgreSQL would find `pgdata/` empty and
> create a fresh database: the old data stays on the volume, but out of sight.
>
> Check:
> `kubectl exec -n <namespace> <release>-postgres-0 -- ls /var/lib/postgresql/data`.
> If `PG_VERSION` shows at the root, back up (`pg_dumpall`) before the
> upgrade, then restore into the new database. A fresh install is not
> affected.
>
> The backend also uses `strategy: Recreate` (`ReadWriteOnce` volume): each
> upgrade stops the old pod before starting the new one, so expect a few
> seconds of downtime.

## Versions

The current series is **0.4.x** (David, 08/09/26): fixes and additions ship
as `0.4.1`, `0.4.2`… Do not start a new minor without a reason — `0.3.0` was
tagged between two merges and lacks the fixes that followed it, which cost a
catch-up bump.

Bumping `version:` in `Chart.yaml` is what publishes: `chart-releaser` creates
the release on push to `main`, and the OCI publication is started by hand
(`publish-dockerhub-helm.yml`). An unchanged version publishes nothing,
whatever the content. The `artifacthub.io/changes` annotation in `Chart.yaml`
lists the changes of that version only: rewrite it at each bump.

> GHCR was dropped on 08/09/26. Pushing there succeeded, but a package is born
> **private** in a GitHub organization: `helm pull oci://ghcr.io/apowerb/apowerb` <!-- docs-in-sync: ignore -->
> answered `403 Forbidden` anonymously. Publishing where nobody can pull is
> not publishing.

> **The chart has been called `apowerb-chart` since 0.4.1**, and that name
> becomes the Docker Hub repository. Before, chart and images shared
> `apowerb/apowerb`: `apowerb/apowerb:0.2.0` weighs 10 kB — that was the
> chart; `:0.2.12` weighs 250 MB — that is the backend. Two version series in
> one namespace, one of which would eventually have overwritten the other.
>
> The rename touches **no Kubernetes resource**: `apowerb.name` is pinned to
> `apowerb` rather than derived from `.Chart.Name`, otherwise every object
> would have become `apowerb-chart-backend` and a `helm upgrade` would have
> recreated everything next to the existing one. Measured: `helm template`
> before and after the rename differs only by the `# Source:` comments Helm
> writes itself — zero content lines. `nameOverride` is still there for what
> it is for, running two releases in one namespace.
>
> Versions published before the rename stay under
> `oci://registry-1.docker.io/apowerb/apowerb` (0.2.0 and 0.4.0): they were <!-- docs-in-sync: ignore -->
> not moved.

## A smaller stack

Nothing beyond the product itself is mandatory:

```bash
helm upgrade --install apowerb ./helm/apowerb-chart \
  --set th2etl.enabled=false \
  --set th2pulse.enabled=false \
  --set otelCollector.enabled=false \
  --set backend.env.encryptKey="$(openssl rand -base64 32)" \
  --set postgres.password="$(openssl rand -hex 16)"
```

Eight objects instead of sixteen. The interface then says which features are
not configured rather than failing on them — that is the point of
`GET /api/config/setup` and of the **Admin → Configuration** screen.

## HTTPS: the certificate does not close port 80

`ingress.tlsEnabled` adds the TLS section; it does not redirect. Measured on
09/09/26 on a real install: `http://` answered **200**, not 308 — a visitor
who types the address without `https://` enters their credentials in clear.

With Traefik, the redirect is one Middleware, shipped in
`k8s/traefik/redirect-https.yaml`, plus an annotation on the Ingress:

```bash
kubectl apply -f k8s/traefik/redirect-https.yaml   # in the release namespace
helm upgrade ... \
  --set ingress.annotations."traefik\.ingress\.kubernetes\.io/router\.middlewares"=<namespace>-redirect-https@kubernetescrd
```

With ingress-nginx, nothing to do: `ssl-redirect` is on as soon as TLS is
declared.

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

## Features and their credentials

Everything the product can be told to do lives under a handful of values. Each
one is passed to the backend **only when it has a value** — a variable set to
an empty string is not an absent variable: pydantic-settings counts it as
provided and it replaces the core's default instead of deferring to it. That is
what sent an empty `redirect_uri` to Microsoft on the demo (`AADSTS90102`).

| Value | Environment | Without it |
|---|---|---|
| `defaultLlm.model`, `defaultLlm.apiKey` | `DEFAULT_LLM_*` | no shared model: every user must bring their own key to run an agent |
| `integrations.microsoft.clientId` / `clientSecret` | `MICROSOFT_INTEGRATION_*` | no Outlook connection, no Outlook webhook, no agent-sent mail |
| `integrations.google.clientId` / `clientSecret` | `GOOGLE_INTEGRATION_*` | no Drive, Gmail or Calendar |
| `storage.mode`, `storage.s3.*` | `STORAGE_MODE`, `S3_*` | uploads stay on the volume (see *Storage*) |
| `mail.host`, `mail.port`, `mail.from` | `SMTP_*` | no e-mail verification, no password reset |
| `superadmin.email`, `password` | `DEFAULT_SUPERADMIN_*` | no administrator account is created on first boot |

Sensitive halves (`apiKey`, `clientSecret`, `accessKeySecret`, `mail.password`,
`superadmin.password`, `ragWebhookSecret`) go through the Secret, referenced
with `optional: true` — so a Secret you provide yourself
(`secret.create=false`) can carry those keys without repeating the values here.

Whatever is left unset is not a silent hole: `Admin → Configuration` in the
product lists exactly what is missing, by variable name, to administrators
only.

## Public URLs

`publicUrls.appPublicUrl` is the origin the **front** answers on, and the core
derives from it the CORS origins and the GitHub, Google and Outlook Mail
callbacks — one value for nine settings. `publicUrls.publicBaseUrl` is the
origin **webhook providers dial**; unset, it follows the front, since the
ingress routes everything to the front and the front relays `/api`.

Leave both empty with an ingress enabled and they are derived from
`ingress.host` and `ingress.tlsEnabled`. Leave them empty without an ingress
and nothing is passed at all: the core keeps its localhost defaults, and the
Configuration screen says so — which beats inventing an origin no OAuth
provider will accept.

`ORCHESTRATOR=th2etl` is set alongside `TH2ETL_BASE_URL` whenever th2etl is
enabled. The core picks its orchestration client from that variable and
defaults to `mage`, so address and key alone leave the Orchestrator screen
empty next to a perfectly healthy th2etl — measured on the demo, 2026-09-08.

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
helm lint helm/apowerb-chart
helm template rel helm/apowerb-chart --set th2pulse.ingestToken=x --set th2pulse.queryToken=y | \
  kubeconform -strict -summary -kubernetes-version 1.30.0
```

## Notes

The chart standardizes defaults for namespace, storage, secrets, ingress, and
resource requests.
