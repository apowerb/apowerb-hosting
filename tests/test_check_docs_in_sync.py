"""The docs-in-sync guard must read chart paths, not URLs that look like them."""
from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / ".github" / "scripts" / "check_docs_in_sync.py"


def _module():
    spec = importlib.util.spec_from_file_location("check_docs_in_sync", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_artifact_hub_url_is_not_a_chart_path():
    # The badge docs.apowerb.com shows on the Helm chart page (apowerb-docs#51).
    line = '<a href="https://artifacthub.io/packages/helm/apowerb/apowerb-chart">'
    assert _module().HELM_PATH_RE.findall(line) == []


def test_a_stale_local_path_is_still_caught():
    line = "helm upgrade --install apowerb ./helm/apowerb --namespace apowerb"
    assert _module().HELM_PATH_RE.findall(line) == ["apowerb"]
