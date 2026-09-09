"""Read the two sides this contract compares: the root compose file, and the
core image that file pins.

The compose side goes through `docker compose config`, so a value is what the
container would actually receive -- nested fallbacks resolved, `${X:-}`
rendered as the empty string it really is. The core side is read by running
`probe_core.py` inside the pinned image: not a parse of the source, not a
checkout beside it, but the artifact this file deploys.
"""

from __future__ import annotations

import functools
import json
import os
import subprocess
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
COMPOSE_FILE = REPO_ROOT / "docker-compose.yml"
PROBE = Path(__file__).parent / "probe_core.py"

# The service this contract is about. The frontend and th2etl carry their own
# configuration; apowerb's Settings class settles none of it.
SERVICE = "apowerb"

_SENTINEL = "CONTRACT_JSON "

# The variables the file itself declares mandatory (`${X:?...}`). Rendering
# needs values for them; the values are never read, only their presence.
_REQUIRED_PLACEHOLDERS = {
    "DB_HOST": "db.invalid",
    "DB_NAME": "contract",
    "DB_USER": "contract",
    "DB_PASSWORD": "contract",
    "ENCRYPT_KEY": "contract",
    "TH2PULSE_INGEST_TOKEN": "contract",
    "TH2PULSE_QUERY_TOKEN": "contract",
}


def render(extra_env: dict[str, str] | None = None) -> dict:
    """`docker compose config` on the root file, with an environment holding
    nothing but what the file refuses to render without.

    `--env-file os.devnull` matters as much as the empty environment: without
    it Compose loads the `.env` sitting next to the file, and a developer's
    local values would decide what this contract sees.
    """
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": tempfile.gettempdir(),
    }
    env.update(_REQUIRED_PLACEHOLDERS)
    env.update(extra_env or {})
    out = subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE_FILE), "--env-file", os.devnull,
         "config", "--format", "json"],
        env=env, capture_output=True, text=True, check=False,
    )
    if out.returncode != 0:
        raise RuntimeError("docker compose config failed:\n" + out.stderr.strip())
    return json.loads(out.stdout)


def service_environment(extra_env: dict[str, str] | None = None) -> dict[str, str]:
    svc = render(extra_env)["services"][SERVICE]
    # Compose renders a value it cannot resolve as null; the container then
    # inherits nothing, which for this contract is an empty string.
    return {k: ("" if v is None else str(v)) for k, v in svc["environment"].items()}


def pinned_image() -> str:
    """The backend image this file deploys, taken from the rendered service
    rather than the `image:` line -- name and tag both live in `${...}`."""
    return render()["services"][SERVICE]["image"]


@functools.lru_cache(maxsize=None)
def probe(image: str, candidates: tuple[str, ...]) -> dict:
    """Run `probe_core.py` inside the pinned image and read its one JSON line.

    `docker run` pulls the image if the host does not have it, so this needs
    no separate step in CI.
    """
    out = subprocess.run(
        ["docker", "run", "--rm", "-i", "--entrypoint", "python", image, "-",
         *candidates],
        stdin=PROBE.open("rb"), capture_output=True, text=True, check=False,
    )
    if out.returncode != 0:
        raise RuntimeError(
            f"probing {image} failed (rc={out.returncode}):\n{out.stderr.strip()}"
        )
    for line in out.stdout.splitlines():
        # Importing apowerb writes a startup banner first; the answer is the
        # line behind the sentinel, and there is exactly one.
        if line.startswith(_SENTINEL):
            return json.loads(line[len(_SENTINEL):])
    raise RuntimeError(f"{image} printed no contract line:\n{out.stdout[-2000:]}")
