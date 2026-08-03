# apowerb-hosting

Configurations de déploiement de la pile **apowerb** — l'édition open source de
th2agent.

Ce dépôt ne contient aucun code applicatif : il assemble
[`apowerb/th2agent`](https://github.com/apowerb/th2agent) (l'API) et
[`apowerb/th2agent-front`](https://github.com/apowerb/th2agent-front)
(l'interface) et leur fournit une base de données.

## Démarrer

Le dépôt peut être déployé avec des images publiées ou via une pile Kubernetes/Helm.

### Docker Compose

```bash
cd apowerb-hosting
cp .env.example .env
./scripts/generate-secrets.sh    # remplit ENCRYPT_KEY et TEST_TOKEN
docker compose up -d
```

L'interface répond sur <http://localhost:3000>, l'API sur
<http://localhost:8000>. Les ports se changent dans `.env`.

### Kubernetes

Des manifests prêts à appliquer sont présents dans `k8s/`.

```bash
kubectl apply -f k8s/
```

### Helm

Un chart Helm est présent dans `helm/apowerb/`.

```bash
helm upgrade --install apowerb ./helm/apowerb \
  --namespace apowerb \
  --create-namespace \
  --values ./helm/apowerb/values.yaml
```

Pour un ingress, activez `ingress.enabled: true` dans le `values.yaml` ou
appliquez l'exemple statique de [k8s/05-ingress.yaml](k8s/05-ingress.yaml).

### SSH / single VM + HTTPS (Traefik)

Pour un hôte unique, vous pouvez superposer l'overlay de proxy HTTPS sur le
compose existant :

```bash
cp .env.example .env
# renseignez APP_HOST et ACME_EMAIL dans .env

docker compose -f docker-compose.yml -f docker-compose.traefik.yml up -d
```

L'interface est ensuite servie via `https://$APP_HOST` et le reverse proxy
Traefik prend en charge le routage TLS et le challenge Let's Encrypt.

### Publication GitHub Actions vers Docker Hub

Le chart Helm peut être publié comme artefact OCI vers Docker Hub avec le
workflow GitHub Actions suivant :

- `.github/workflows/publish-dockerhub-helm.yml`

Prérequis de secrets GitHub Actions :

- `DOCKERHUB_USERNAME`
- `DOCKERHUB_TOKEN`

Le workflow exécute `helm lint`, `helm package`, puis `helm push` sur le
registre OCI de Docker Hub.

## Ce que la pile contient

| Service | Rôle | Port par défaut |
|---|---|---|
| `postgres` | base de données | interne |
| `apowerb` | API FastAPI | 8000 |
| `apowerb-ui` | interface Next.js | 3000 |

## L'édition open source est complète

Les composantes commerciales (connexion par fournisseur d'identité, second
facteur, comptabilisation des jetons et plafonds, facturation, prospection
B2B) **ne sont pas présentes et désactivées : elles sont absentes**. Il n'y a
aucun drapeau à activer, aucun code mort dans l'image.

Ce que ça donne, sur la pile réellement démarrée :

```
GET /api/config          → pas de clé "billing_enabled"
GET /api/usage/quota     → 404
GET /api/billing/packages→ 404
GET /api/auth/mfa/status → 404
```

Une clé **absente** et une clé **à `false`** ne disent pas la même chose : la
première dit que la fonctionnalité n'existe pas dans cette édition.

`TH2_EXTENSIONS` reste vide ici. C'est la variable par laquelle une édition
commerciale déclare ses briques — elle n'a rien à charger dans cette pile.

## Les secrets

`ENCRYPT_KEY` chiffre les jetons OAuth des intégrations stockés en base. Le
serveur refuse de démarrer sans elle. **La changer rend illisibles toutes les
intégrations déjà connectées** — sauvegardez-la avec vos autres secrets.

`scripts/generate-secrets.sh` ne remplace jamais une valeur déjà posée,
précisément pour éviter ça.

## Base de données

Le Postgres de cette pile ne fait pas de TLS et n'en a pas besoin : le trafic
ne quitte pas le réseau interne de Docker, d'où `DB_SSLMODE=disable`.

Contre une base gérée (Neon, RDS, OVH), pointez `DB_HOST` dessus et remettez
`DB_SSLMODE=require`, qui est le défaut du noyau.

## Déploiements fournis

- **Docker Compose** : démarre la pile à partir des images publiées
  `apowerb/apowerb` et `apowerb/apowerb-ui`.
- **Kubernetes** : manifests statiques dans `k8s/` pour lancer les mêmes
  services dans un cluster.
- **Helm chart** : chart `helm/apowerb/` pour déployer la pile avec des valeurs
  standardisées, des ressources, un secret généré et un ingress optionnel.

## Vérifié

`docker compose up` a été joué de bout en bout : les trois services passent
`healthy`, l'API répond `200` sur `/health`, l'interface sert `/` et `/login`,
et les routes commerciales répondent `404` côté API **comme** côté interface.

Deux choses ont été corrigées en montant cette pile, plutôt que contournées :

- le noyau imposait `sslmode=require` en dur sur un de ses moteurs, ce qui
  rendait tout auto-hébergement contre un Postgres local impossible ;
- les images n'installent aucun paquet système : `psycopg2-binary`, `asyncpg`
  et `cryptography` arrivent en wheels précompilés. Les sondes de santé sont
  écrites en Python et en Node plutôt qu'avec `curl`. La construction ne dépend
  donc d'aucun miroir Debian.
