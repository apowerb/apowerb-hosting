"""Contract for th2forecast as an opt-in service of the self-hosted stack
and the Helm chart.

th2forecast (Chronos-2 + statsforecast) has no published image yet
(apowerb/th2forecast-py does not exist on Docker Hub, no semver tag cut in
the engine repo). This test proves the service is wired OFF by default in
both installation paths, and that turning it on cannot silently point at a
version nobody published.

Root docker-compose.yml (Hostman App Platform) is untouched on purpose --
see tests/compose_contract.yml, the th2forecast exclusion entry.
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SELF_HOSTED_COMPOSE = REPO_ROOT / "docker-compose" / "docker-compose.yml"
CHART_VALUES = REPO_ROOT / "helm" / "apowerb-chart" / "values.yaml"
ENV_EXAMPLE = REPO_ROOT / ".env.example"
GENERATE_SECRETS = REPO_ROOT / "scripts" / "generate-secrets.sh"


def _compose() -> dict:
    return yaml.safe_load(SELF_HOSTED_COMPOSE.read_text(encoding="utf-8"))


def _values() -> dict:
    return yaml.safe_load(CHART_VALUES.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# Self-hosted docker-compose.yml
# --------------------------------------------------------------------------- #

def test_th2forecast_service_exists_and_is_opt_in():
    services = _compose()["services"]
    assert "th2forecast" in services, "no th2forecast service in the self-hosted compose file"
    assert services["th2forecast"].get("profiles") == ["forecast"], (
        "th2forecast must sit behind its own profile, off by default"
    )


def test_th2forecast_publishes_no_host_port():
    service = _compose()["services"]["th2forecast"]
    assert not service.get("ports"), "th2forecast must not publish a host port -- only the backend talks to it"


def test_th2forecast_image_tag_is_not_an_invented_version():
    import re

    service = _compose()["services"]["th2forecast"]
    image = service["image"]
    match = re.search(r"\$\{TH2FORECAST_TAG:-([^}]*)\}", image)
    assert match, f"TH2FORECAST_TAG default not found in {image!r}"
    default_tag = match.group(1)
    # No image on Docker Hub yet -- refuse a fabricated semver default.
    assert not any(ch.isdigit() for ch in default_tag), (
        f"th2forecast image default looks like an invented version tag: {default_tag!r}"
    )


def test_th2forecast_api_token_uses_soft_fallback_not_hard_required():
    service = _compose()["services"]["th2forecast"]
    token_line = service["environment"]["TH2FORECAST_API_TOKEN"]
    # `:?` on a profiled-off service still aborts `docker compose config`
    # for the whole file -- measured and documented at docker-compose.yml:281.
    assert ":?" not in token_line
    assert ":-" in token_line


def test_backend_declares_th2forecast_client_vars_with_soft_fallback():
    backend_env = _compose()["services"]["apowerb"]["environment"]
    for var in ("TH2FORECAST_URL", "TH2FORECAST_API_TOKEN", "TH2FORECAST_TIMEOUT_S"):
        assert var in backend_env, f"{var} must be declared on the apowerb service"
        assert ":?" not in backend_env[var]


# --------------------------------------------------------------------------- #
# .env.example / generate-secrets.sh
# --------------------------------------------------------------------------- #

def test_env_example_documents_th2forecast_token():
    text = ENV_EXAMPLE.read_text(encoding="utf-8")
    assert "TH2FORECAST_API_TOKEN=" in text


def test_generate_secrets_fills_th2forecast_token():
    text = GENERATE_SECRETS.read_text(encoding="utf-8")
    assert "TH2FORECAST_API_TOKEN" in text


# --------------------------------------------------------------------------- #
# Helm chart
# --------------------------------------------------------------------------- #

def test_helm_th2forecast_disabled_by_default():
    values = _values()
    assert values["th2forecast"]["enabled"] is False


def test_helm_th2forecast_image_tag_default_is_empty():
    values = _values()
    # No published image: the chart must not invent a tag either. An empty
    # default forces _validate.tpl to fail loudly if enabled without one.
    assert values["image"]["th2forecast"]["tag"] == ""


def test_helm_validate_fails_when_enabled_without_tag():
    validate = (REPO_ROOT / "helm" / "apowerb-chart" / "templates" / "_validate.tpl").read_text(encoding="utf-8")
    assert "th2forecast.enabled" in validate
    assert "image.th2forecast.tag" in validate


def test_helm_validate_fails_when_enabled_without_token():
    validate = (REPO_ROOT / "helm" / "apowerb-chart" / "templates" / "_validate.tpl").read_text(encoding="utf-8")
    assert "th2forecast.apiToken" in validate


def test_helm_th2forecast_deployment_template_exists():
    dep = REPO_ROOT / "helm" / "apowerb-chart" / "templates" / "th2forecast-deployment.yaml"
    svc = REPO_ROOT / "helm" / "apowerb-chart" / "templates" / "th2forecast-service.yaml"
    assert dep.exists() and svc.exists()
