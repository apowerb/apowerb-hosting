"""With the Traefik overlay, Traefik must be the only door into the stack.

The overlay used to write `ports: []` on the interface, meaning "publish
nothing, Traefik routes to you". Compose does not read it that way: it MERGES
`ports` across files, so an empty list adds nothing and removes nothing.
Measured on 08/10/2026 with `docker compose config`: the interface was still
published on 0.0.0.0:3000 and the API on 0.0.0.0:8000 -- plain HTTP, next to
the HTTPS Traefik serves, the authentication API included. `!reset []` is what
empties the list.

The assertion runs on the merged configuration, the way `up` reads it, not on
the overlay file alone: read by itself, `ports: []` looked right.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "docker-compose" / "docker-compose.yml"
OVERLAY = ROOT / "docker-compose" / "docker-compose.traefik.yml"

# Placeholders only: `config` interpolates, it starts nothing.
ENV = {
    "DB_NAME": "th2agent",
    "DB_USER": "th2agent",
    "DB_PASSWORD": "placeholder",
    "ENCRYPT_KEY": "placeholder",
    "APP_HOST": "apowerb.example.com",
    "ACME_EMAIL": "ops@example.com",
    "PATH": "/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin",
}


def _compose() -> list[str]:
    if shutil.which("docker"):
        return ["docker", "compose"]
    if shutil.which("docker-compose"):
        return ["docker-compose"]
    pytest.skip("neither `docker compose` nor `docker-compose` is installed")


def _merged() -> dict:
    out = subprocess.run(
        [*_compose(), "-f", str(BASE), "-f", str(OVERLAY),
         "--env-file", "/dev/null", "config", "--format", "json"],
        capture_output=True, text=True, env=ENV, cwd=ROOT,
    )
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def test_only_traefik_publishes_host_ports():
    services = _merged()["services"]
    published = {
        name: [p.get("published") for p in svc.get("ports", [])]
        for name, svc in services.items()
        if svc.get("ports")
    }
    assert published == {"traefik": ["80", "443"]}, published


def test_interface_is_still_routed_by_traefik():
    labels = _merged()["services"]["apowerb-ui"].get("labels", {})
    assert labels.get("traefik.enable") == "true"
    assert labels.get("traefik.http.routers.apowerb-ui.rule") == "Host(`apowerb.example.com`)"
