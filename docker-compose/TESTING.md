# Testing the Compose stack

A end-to-end check that a fresh install actually works: the stack starts, the
schema is complete, an account can be created, and an agent answers. About 15
minutes, most of it spent pulling images.

Every command below is run from the repository root.

## Prerequisites

- Docker Engine with Compose v2 (`docker compose version`)
- ~4 GB of free disk: the two images are ~2.8 GB, Postgres ~300 MB
- Ports `3000`, `8000` and `5432` free — see [On a host that already runs
  something](#on-a-host-that-already-runs-something) otherwise
- The published images cover `linux/amd64` and `linux/arm64`

## 1. Configure

```bash
cp .env.example .env && ./scripts/generate-secrets.sh
```

The script fills `ENCRYPT_KEY` (a Fernet key) and `TEST_TOKEN`, and never
replaces a value that is already set. Then change `DB_PASSWORD`, which ships as
a placeholder, and restrict the file: `chmod 600 .env`.

## 2. Start

```bash
docker compose -f docker-compose/docker-compose.yml --env-file .env up -d
```

## 3. Health checks

Containers — `postgres` healthy, the two others running:

```bash
docker compose -f docker-compose/docker-compose.yml --env-file .env ps
```

API — expects `{"status":"ok"}`:

```bash
curl -s http://127.0.0.1:8000/health
```

API surface — expects **193** routes:

```bash
curl -s http://127.0.0.1:8000/openapi.json | python3 -c "import sys,json;print(len(json.load(sys.stdin)['paths']),'routes')"
```

Startup errors — expects **0**:

```bash
docker compose -f docker-compose/docker-compose.yml --env-file .env logs apowerb | grep -c ERROR
```

Schema — expects **16** tables, including `user`:

```bash
docker compose -f docker-compose/docker-compose.yml --env-file .env exec -T postgres psql -U th2agent -d th2agent -c "\dt"
```

> With a backend image older than `apowerb 0.1.7`, this returns **6** tables,
> the error count is in the hundreds and account creation fails with a 500: the
> `user` table was never created on an empty database. Run
> `docker compose ... pull` to get a build that carries the fix.

Frontend — expects `200`:

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:3000/login
```

## 4. Create an account and sign in

Expects `201` and a `user_id`:

```bash
curl -s -X POST http://127.0.0.1:8000/api/users/ -H 'Content-Type: application/json' -d '{"email":"test@example.com","password":"Test1234!","first_name":"Test","last_name":"User"}' -w "\nHTTP=%{http_code}\n"
```

Expects `200` and a bearer token:

```bash
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/auth/token -H 'Content-Type: application/x-www-form-urlencoded' -d 'username=test@example.com&password=Test1234!' | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
```

Expects `200` and a list:

```bash
curl -s -o /dev/null -w "%{http_code}\n" -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/api/agents
```

Then sign in at <http://localhost:3000/login> with the same account.

## 5. Make an agent answer

This is the only check that proves the whole chain. It needs a model.

**Either** give each agent its own key from the UI — nothing to change here.

**Or** enable the shared model. Check whether it is on:

```bash
curl -s http://127.0.0.1:8000/api/config
```

`"default_llm_available": false` means `DEFAULT_LLM_MODEL` and
`DEFAULT_LLM_API_KEY` are not both set in `.env`. Fill them, restart, and the
same call must answer `true`. A missing one is silent — nothing is logged.

Create an agent on that model:

```bash
curl -s -X POST http://127.0.0.1:8000/api/agents -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{"agent_name":"smoke_test_agent","agent_model":"thaink2/default","agent_description":"Compose smoke test","agent_instruction":"You are a terse assistant.","agent_type":"llm"}'
```

Open a session and run it. **The `app_name` of a run is the `agent_id` returned
above (`agent1`), not the display name** — passing the name fails with
`Agent not found ... /app/agents_pool/<name>`:

```bash
SID=$(curl -s -X POST "http://127.0.0.1:8000/apps/agent1/users/test@example.com/sessions" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{}' | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")
```

```bash
curl -s -X POST http://127.0.0.1:8000/run -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d "{\"app_name\":\"agent1\",\"user_id\":\"test@example.com\",\"session_id\":\"$SID\",\"new_message\":{\"role\":\"user\",\"parts\":[{\"text\":\"Reply with exactly: compose smoke test ok\"}]}}"
```

Expects `200` and the model's text in the returned events.

## 6. Survive an image update

`agents_pool/` sits in no volume, but it is rebuilt from the database at
startup, so an agent still answers after the container is replaced:

```bash
docker compose -f docker-compose/docker-compose.yml --env-file .env up -d --force-recreate apowerb
```

Re-run the request from step 5 — it answers again.

## 7. Tear down

```bash
docker compose -f docker-compose/docker-compose.yml --env-file .env down -v
```

`-v` drops the volumes, and therefore the database. Leave it out to keep the
data for a later run.

## Pass criteria

| Check | Expected |
|---|---|
| containers | 3 running, `postgres` healthy |
| `/health` | `{"status":"ok"}` |
| API surface | 193 routes |
| startup errors | 0 |
| schema | 16 tables, `user` present |
| `/login` | 200 |
| account creation | 201 |
| sign-in | 200 + token |
| agent run | 200 + the model's answer |

## On a host that already runs something

Shift the ports and bind them to the loopback interface. Careful: Compose
**merges** `ports:` lists across files, so a plain override adds a second
mapping on the same port and startup fails with `address already in use`. The
`!override` tag replaces the list instead:

```yaml
services:
  apowerb:
    ports: !override ["127.0.0.1:19110:8000"]
  apowerb-ui:
    ports: !override ["127.0.0.1:19130:3000"]
```

Set `TH2AGENT_PORT`, `FRONT_PORT` and `PUBLIC_API_URL` in `.env` accordingly.

## HTTPS with Traefik

Needs a public domain pointing at the machine and ports 80/443 open — Let's
Encrypt validates through a TLS challenge, so this cannot be tested locally.
Set `APP_HOST` and `ACME_EMAIL` in `.env` first.

```bash
docker compose -f docker-compose/docker-compose.yml -f docker-compose/docker-compose.traefik.yml --env-file .env up -d
```
