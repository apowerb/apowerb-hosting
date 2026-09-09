"""The root compose file against the core it deploys.

Compose passes a container only what the service declares. Everything else --
a value typed into the platform's panel, a variable exported on the host --
stops at the container wall, silently, and the application comes up looking
configured. Three outages of 2026-09-08 are that one sentence:

  * ORCHESTRATOR undeclared: the backend asked a MageAI that does not exist
    here while a healthy th2etl sat beside it, and the Orchestrator screen
    stayed empty behind a 503 (hosting#23);
  * nineteen integration variables undeclared: the Azure credentials were set
    in the panel and Outlook still refused, because this file named none of
    them (hosting#24);
  * OUTLOOK_MAIL_REDIRECT_URI declared as `${OUTLOOK_MAIL_REDIRECT_URI:-}`:
    an empty value is not an absent one. pydantic-settings counts it as
    provided, so it REPLACED the URL the core deduces instead of falling back
    to it, and Microsoft was handed "" -- AADSTS90102 in production
    (hosting#25).

Each of the three is a comparison between two lists that nobody was making.
These tests make it, against the core version this file actually pins.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

import compose_contract as cc

CONTRACT_FILE = Path(__file__).parent / "compose_contract.yml"


# --------------------------------------------------------------------------- #
# Fixtures: the two sides, read once.
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="session")
def contract() -> dict:
    return yaml.safe_load(CONTRACT_FILE.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def compose_env() -> dict[str, str]:
    """The service's environment as the container would receive it on a host
    that exports nothing -- what an operator gets before typing anything into
    the platform's panel."""
    return cc.service_environment()


@pytest.fixture(scope="session")
def core(compose_env, contract) -> dict:
    """What the pinned image says about itself. The variables it is asked to
    look for in its own source are exactly the ones this file declares, since
    those are the only ones whose reader is in question."""
    return cc.probe(cc.pinned_image(), tuple(sorted(compose_env)))


@pytest.fixture(scope="session")
def excluded(contract) -> dict[str, str]:
    """Setting name -> the reason it is deliberately not declared."""
    return {
        name: group["reason"]
        for group in contract["settings_not_declared"]
        for name in group["names"]
    }


@pytest.fixture(scope="session")
def core_fields(core) -> set[str]:
    return {name.upper() for name in core["fields"]}


# --------------------------------------------------------------------------- #
# 1. What the product itself tells an administrator to set must arrive.
# --------------------------------------------------------------------------- #

def test_every_variable_the_setup_checklist_names_is_declared(core, compose_env):
    """`GET /api/config/setup` hands an administrator the NAMES of the
    variables still missing, and the interface prints them. Each one has to be
    a variable this file passes through, or the administrator sets it, the
    checklist keeps saying it is missing, and nothing they can see explains
    why. That was hosting#24, one integration family at a time.

    Deliberately without an exclusion list: this side of the contract is the
    product's own promise, and there is no defensible reason to name a
    variable on a screen and drop it at the container wall.
    """
    named = set(core["checklist"])
    assert named, "the checklist named nothing -- the probe is wrong, not the file"
    missing = sorted(named - set(compose_env))
    assert not missing, (
        "the setup checklist names these variables to administrators, and the "
        f"compose service does not declare them: {missing}"
    )


# --------------------------------------------------------------------------- #
# 2. Every core setting is either declared, or refused for a written reason.
# --------------------------------------------------------------------------- #

def test_every_core_setting_is_declared_or_written_off(core_fields, compose_env, excluded):
    """The broad net. A setting the core can read is either passed through or
    listed in compose_contract.yml with the reason it is not.

    A new setting added to the core matches neither, so this turns red on the
    next change to this file -- which is the only moment somebody is looking.
    """
    unaccounted = sorted(core_fields - set(compose_env) - set(excluded))
    assert not unaccounted, (
        "core settings that this file neither declares nor writes off in "
        f"tests/compose_contract.yml: {unaccounted}"
    )


def test_no_stale_entry_in_the_contract_file(core_fields, compose_env, excluded):
    """An exclusion that no longer names a setting, or names one the file has
    since started declaring, is a reason nobody will reread. Both make the
    list above less trustworthy than an empty one."""
    gone = sorted(name for name in excluded if name not in core_fields)
    now_declared = sorted(name for name in excluded if name in compose_env)
    assert not gone, f"written off but no longer a core setting: {gone}"
    assert not now_declared, (
        f"written off and declared anyway -- drop the entry: {now_declared}"
    )


# --------------------------------------------------------------------------- #
# 3. An empty declaration must not suppress a value the core deduces.
# --------------------------------------------------------------------------- #

def test_a_deduced_url_is_never_declared_empty(core, compose_env):
    """The trap that cost the most: `${X:-}` is not "unset".

    The core fills these URLs in from APP_PUBLIC_URL, but only for the ones
    the environment did not provide -- and pydantic-settings counts a
    declared-but-empty variable as provided. Declaring one of them empty
    therefore hands the application "" where it would otherwise have built a
    real callback, which is what Microsoft answered AADSTS90102 to.
    """
    # Absent is the safe state: the core deduces what it was not handed.
    blank = sorted(
        var for var in (n.upper() for n in core["derived_from_front"])
        if var in compose_env and not compose_env[var].strip()
    )
    assert not blank, (
        f"declared with a fallback that renders empty: {blank}. The core "
        "deduces each of these from APP_PUBLIC_URL when it is absent; declared "
        "empty, it counts as provided and the deduction is skipped. Either drop "
        "the line or give it a non-empty fallback."
    )


def test_a_declared_deduced_url_reproduces_the_core_deduction(core):
    """A non-empty fallback is not enough: it has to say the same thing the
    core would have said.

    The compose file rebuilds two of these URLs itself so the platform's panel
    can show them. Rendered against a deployment's real origin, each one must
    come out as that origin plus the exact path the core appends -- otherwise
    the file quietly overrides the deduction with a different answer, and the
    provider is handed a callback that is not registered.
    """
    origin = "https://contract.example"
    env = cc.service_environment({"APP_PUBLIC_URL": origin})
    checked = 0
    for name, path in core["derived_from_front"].items():
        var = name.upper()
        if var not in env or not env[var].strip():
            continue
        assert env[var] == f"{origin}{path}", (
            f"{var} renders as {env[var]!r} for a deployment on {origin}, "
            f"where the core would deduce {origin + path!r}"
        )
        checked += 1
    assert checked, "no deduced URL is declared -- this test proved nothing"


def test_the_public_origin_is_never_declared_empty(compose_env):
    """APP_PUBLIC_URL is the base every deduction above starts from, and
    PUBLIC_BASE_URL is what webhook providers dial. Empty, the first silently
    switches the deduction off for all five URLs at once and the second sent
    Graph to http://localhost:8000 -- HTTP 400, scheme 'http' is not
    supported."""
    for var in ("APP_PUBLIC_URL", "PUBLIC_BASE_URL"):
        assert compose_env.get(var, "").strip(), (
            f"{var} must carry a non-empty fallback; it is what this "
            "deployment's callbacks and webhook URLs are built from"
        )


# --------------------------------------------------------------------------- #
# 4. Nothing is declared that nobody reads.
# --------------------------------------------------------------------------- #

def test_every_declared_variable_is_read_by_something(core, core_fields, compose_env, contract):
    """A variable this file declares that is neither a core setting nor a name
    the core's source mentions is a value the platform collects and nobody
    collects at the other end -- an undeclared variable seen from the far
    side, and just as quiet. A typo in a name lands here."""
    by_a_library = {
        entry["name"] for entry in contract["read_by_a_library_not_by_apowerb"]
    }
    mentioned = set(core["mentioned_in_source"])
    orphans = sorted(
        var for var in compose_env
        if var not in core_fields and var not in by_a_library and var not in mentioned
    )
    assert not orphans, (
        "declared in the compose service, read by nothing in the core: "
        f"{orphans}. If a library in the image reads it, say so in "
        "tests/compose_contract.yml."
    )