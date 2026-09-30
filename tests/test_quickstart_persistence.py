"""The quickstart compose must actually persist what the backend writes.

The self-hosted stack mounts a named volume, `apowerb-data`, and pulls a fresh
image on every `up` (`pull_policy: always`). Everything the backend writes to
disk -- uploads, artifacts_store, bi_store -- is anchored to `runtime_root()`,
which defaults to the working directory (`/app`) unless `RUNTIME_ROOT` is set.
Mount a volume at `/app/data` without pointing the runtime root there and the
volume stays empty while the real data sits on the ephemeral layer, lost at the
next image update. `agents_pool` survives regardless (rebuilt from the DB), so
the loss is invisible in a smoke test that only exercises an agent.

This asserts the one line that ties the two together: the backend's
`RUNTIME_ROOT` resolves under a mounted volume.
"""

from pathlib import Path

import yaml

COMPOSE = Path(__file__).resolve().parent.parent / "docker-compose" / "docker-compose.yml"


def _volume_targets(service: dict) -> set[str]:
    targets = set()
    for entry in service.get("volumes", []):
        # short syntax "name:/container/path[:opts]" or long-syntax mapping
        if isinstance(entry, str):
            parts = entry.split(":")
            if len(parts) >= 2:
                targets.add(parts[1])
        elif isinstance(entry, dict) and entry.get("target"):
            targets.add(entry["target"])
    return targets


def _under(path: str, target: str) -> bool:
    return path == target or path.startswith(target.rstrip("/") + "/")


def test_backend_runtime_root_lands_in_a_mounted_volume():
    compose = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    backend = compose["services"]["apowerb"]

    env = backend.get("environment", {})
    assert isinstance(env, dict), "expected map-form environment"
    runtime_root = env.get("RUNTIME_ROOT")
    assert runtime_root, "apowerb service must declare RUNTIME_ROOT so writes are persisted"

    targets = _volume_targets(backend)
    assert any(_under(runtime_root, t) for t in targets), (
        f"RUNTIME_ROOT={runtime_root!r} is not under any mounted volume {sorted(targets)!r}: "
        "uploads/artifacts/bi_store would be lost on the next image pull"
    )
