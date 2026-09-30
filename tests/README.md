# The contract between this compose file and the core it deploys

Compose passes a container only what the service **declares**. A value entered
in the platform's panel, a variable exported on the host: everything else stops
at the container wall, silently, and the application starts looking configured.

The three outages of 08/09/2026 are that sentence, three times:

| | what was missing | what you saw |
|---|---|---|
| hosting#23 | `ORCHESTRATOR` not declared | empty Orchestrator screen, 503, in front of a healthy th2etl |
| hosting#24 | 19 integration variables not declared | Azure credentials set in the panel, Outlook still refuses |
| hosting#25 | `OUTLOOK_MAIL_REDIRECT_URI: ${OUTLOOK_MAIL_REDIRECT_URI:-}` | `AADSTS90102` in production |

The third is the most expensive and the least visible: **a variable declared
empty is not an absent variable**. `pydantic-settings` counts it as
*provided* (`model_fields_set`), so it **overrides** the value the core would
have derived from `APP_PUBLIC_URL` instead of yielding to it.

Each one is a comparison between two lists that nobody was making.

## What is compared

Both sides are read the way the deployment reads them.

- **The compose file** goes through `docker compose config`, with an empty
  environment and `--env-file /dev/null`: a value is therefore what the
  container would really receive, nested fallbacks resolved and `${X:-}`
  rendered as the empty string it is.
- **The core** is read by running `probe_core.py` **inside the pinned image**
  (`docker run --entrypoint python`). Not a `git clone` of the same tag
  alongside: reaching `setup_status` from the sources requires `google-adk`,
  `boto3`, `asyncpg` and forty other packages, and would still only be a good
  approximation of the artifact. The image *is* the artifact.

## The seven checks

1. **Every name the product's checklist gives to an administrator is
   declared.** `GET /api/config/setup` returns the *names* of the variables
   still missing and the interface displays them. No exclusion list: naming a
   variable on screen and then dropping it at the container wall has no
   justification.
2. **Every core setting is declared, or excluded in writing** in
   `compose_contract.yml`. A new setting matches neither: the test goes red
   the next time that file is modified.
3. **No stale entry** in that exclusions file.
4. **No derived URL declared empty** — hosting#25.
5. **A derived URL that IS declared reproduces the core's derivation**:
   rendered against a real origin, it equals that origin plus the exact path
   the core appends.
6. **`APP_PUBLIC_URL` and `PUBLIC_BASE_URL` are never empty**: the first
   switches off all five derivations at once, the second sent Graph to
   `http://localhost:8000`.
7. **Nothing is declared that nobody reads**: a variable that is neither a
   core setting nor cited in its sources is a value the platform collects and
   that nobody picks up at the other end. A typo lands here.

## Running it

```bash
pip install -r tests/requirements.txt
cd tests && python -m pytest
```

Docker is required (`docker compose config` and the pinned image); the image is
pulled automatically on the first run.

## What it does not cover

It compares **names**, never values. A `MICROSOFT_INTEGRATION_CLIENT_ID`
properly declared and filled in with the identifier of another application
passes here and fails at Microsoft. It also says nothing about the `apowerb-ui`,
`th2etl` and `th2pulse` services, whose configuration does not go through
`Settings`.
