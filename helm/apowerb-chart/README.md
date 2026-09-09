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

- Docker Hub chart: https://hub.docker.com/r/apowerb/apowerb-chart
- Docker Hub images: https://hub.docker.com/r/apowerb/apowerb (le backend, pas le chart)

## Install from source

Three secrets have to be generated first. The chart **refuses to install**
without the two `th2pulse` tokens — that service does not start without them,
so failing at install is the honest moment to say it.

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

## Versions

La série courante est **0.4.x** (David, 08/09/26) : les correctifs et les
ajouts sortent en `0.4.1`, `0.4.2`… Ne pas repartir sur une mineure sans
raison — `0.3.0` a été taguée entre deux merges et ne porte pas les
correctifs qui l'ont suivie, ce qui a coûté un bump de rattrapage.

Bumper `version:` dans `Chart.yaml` fait publier : `chart-releaser` crée la
release au push sur `main`, et la publication OCI se lance à la main (voir
plus bas). Une version inchangée ne publie rien, quel que soit le contenu.

Le chart est publié sur **Docker Hub**, dans l'organisation d'où sortent déjà
les images du produit — mais dans un dépôt à lui, `apowerb/apowerb-chart` :

```bash
helm install apowerb oci://registry-1.docker.io/apowerb/apowerb-chart --version 0.4.1
```

> GHCR a été retiré le 08/09/26. Le push y réussissait, mais un paquet naît
> **privé** dans une organisation GitHub : `helm pull oci://ghcr.io/apowerb/apowerb`
> répondait `403 Forbidden` en anonyme. Publier là où personne ne peut tirer
> n'est pas publier.

> **Le chart s'appelle `apowerb-chart` depuis la 0.4.1**, et c'est ce nom qui
> devient le dépôt Docker Hub. Avant, chart et images partageaient
> `apowerb/apowerb` : `apowerb/apowerb:0.2.0` pèse 10 ko — c'était le chart ;
> `:0.2.12` pèse 250 Mo — c'est le backend. Deux séries de versions dans un
> seul espace de noms, dont l'une aurait fini par écraser l'autre.
>
> Le renommage ne touche **aucune ressource Kubernetes** : `apowerb.name` est
> figé sur `apowerb` plutôt que dérivé de `.Chart.Name`, sinon chaque objet
> serait devenu `apowerb-chart-backend` et un `helm upgrade` aurait tout
> recréé à côté de l'existant. Mesuré : `helm template` avant et après le
> renommage ne diffère que par les commentaires `# Source:` que Helm écrit
> lui-même — zéro ligne de contenu. `nameOverride` reste disponible pour ce à
> quoi il sert, faire cohabiter deux releases dans un namespace.
>
> Les versions publiées avant le renommage restent sous
> `oci://registry-1.docker.io/apowerb/apowerb` (0.2.0 et 0.4.0) : elles n'ont
> pas été déplacées.

## A smaller stack

Nothing beyond the product itself is mandatory:

```bash
helm upgrade --install apowerb ./helm/apowerb-chart \
  --set th2etl.enabled=false \
  --set th2pulse.enabled=false \
  --set otelCollector.enabled=false \
  --set backend.env.encryptKey="$(openssl rand -base64 32)"
```

Seven objects instead of sixteen. The interface then says which features are
not configured rather than failing on them — that is the point of
`GET /api/config/setup` and of the **Admin → Configuration** screen.

## HTTPS : le certificat ne ferme pas le port 80

`ingress.tlsEnabled` ajoute la section TLS ; il ne redirige pas. Mesuré le
09/09/26 sur une installation réelle : `http://` répondait **200**, pas 308 —
un visiteur qui tape l'adresse sans `https://` saisit ses identifiants en
clair.

Avec Traefik, la redirection tient en un Middleware, livré dans
`k8s/traefik/redirect-https.yaml`, et une annotation sur l'Ingress :

```bash
kubectl apply -f k8s/traefik/redirect-https.yaml   # namespace de la release
helm upgrade ... \
  --set ingress.annotations."traefik\.ingress\.kubernetes\.io/router\.middlewares"=<namespace>-redirect-https@kubernetescrd
```

Avec ingress-nginx, rien à faire : `ssl-redirect` est actif dès qu'un TLS est
déclaré.

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
