"""Read out of the core what the compose file has to agree with.

Runs INSIDE the image the compose file pins, never beside it. A checkout of
the same tag would need google-adk, boto3, asyncpg and forty more packages to
reach `setup_status`, and would still only be a good guess at what the
deployed artifact does; the image is the artifact.

Called as `python - NAME NAME ... < probe_core.py`; the names are variables to
look for in the core's own source. Answers one line of JSON behind a sentinel,
because importing apowerb writes a startup banner to stdout first.
"""

import json
import pathlib
import sys

from apowerb.configs.settings import Settings, _DERIVED_FROM_FRONT
from apowerb.core import setup_status


def blank_settings():
    """Everything empty, and nothing counted as provided.

    `model_construct` skips validation, and the blanking goes through
    `object.__setattr__` so `model_fields_set` stays empty: several core
    predicates read it to tell a default from a choice, and a settings object
    that claimed to be configured would hide half the checklist.
    """
    s = Settings.model_construct()
    for name, field in Settings.model_fields.items():
        if field.annotation is str:
            object.__setattr__(s, name, "")
    return s


def checklist_names():
    """Every variable name `GET /api/config/setup` can hand an administrator
    as still missing. `STORAGE_MODE=S3` is one of them: the checklist names
    the value it wants, this contract only cares about the variable."""
    caps = setup_status.capabilities(settings=blank_settings(), env={})
    return sorted({name.split("=", 1)[0] for c in caps for name in c.missing})


def names_the_source_mentions(candidates):
    """Which of these names appear anywhere in the core's source. The question
    for a variable that is not a Settings field: something has to read it, or
    the platform collects a value nobody collects at the other end."""
    root = pathlib.Path(setup_status.__file__).resolve().parents[1]
    blob = "\n".join(
        p.read_text(encoding="utf-8", errors="replace")
        for p in root.rglob("*.py")
        if "__pycache__" not in p.parts
    )
    return sorted({name for name in candidates if name in blob})


print("CONTRACT_JSON " + json.dumps({
    "fields": sorted(Settings.model_fields),
    "derived_from_front": _DERIVED_FROM_FRONT,
    "checklist": checklist_names(),
    "mentioned_in_source": names_the_source_mentions(sys.argv[1:]),
}))
