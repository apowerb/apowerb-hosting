# apowerb-hosting

Configurations de déploiement de la pile **apowerb** — l'édition open source de
th2agent.

Ce dépôt ne contient aucun code applicatif : il assemble
[`apowerb/th2agent`](https://github.com/apowerb/th2agent) (l'API) et
[`apowerb/th2agent-front`](https://github.com/apowerb/th2agent-front)
(l'interface) et leur fournit une base de données.

## Démarrer

Les trois dépôts se clonent côte à côte :

```bash
git clone https://github.com/apowerb/th2agent.git
git clone https://github.com/apowerb/th2agent-front.git
git clone https://github.com/apowerb/apowerb-hosting.git

cd apowerb-hosting
cp .env.example .env
./scripts/generate-secrets.sh    # remplit ENCRYPT_KEY et TEST_TOKEN
docker compose up -d --build
```

L'interface répond sur <http://localhost:3000>, l'API sur
<http://localhost:8000>. Les ports se changent dans `.env`.

## Ce que la pile contient

| Service | Rôle | Port par défaut |
|---|---|---|
| `postgres` | base de données | interne |
| `th2agent` | API FastAPI | 8000 |
| `th2agent-front` | interface Next.js | 3000 |

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

## Ce qui n'est pas encore là

- **Helm chart et manifestes Kubernetes.** Le `docker compose` ci-dessus est
  testé de bout en bout ; l'équivalent k8s ne l'est pas encore et n'est donc
  pas publié. Mieux vaut rien qu'un chart non vérifié.
- **Images publiées sur un registre.** Le compose construit depuis les sources.
  Quand les images `apowerb/*` seront publiées, les blocs `build:` deviendront
  des `image:` et les dépôts sources ne seront plus nécessaires.

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
