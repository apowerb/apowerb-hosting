"""Contract for the plain Kubernetes manifests (k8s/apowerb, k8s/apowerb-public).

They are rendered from the chart by .github/scripts/render_k8s_manifests.py;
the k8s-manifests workflow proves they match it. These tests prove what a
`kubectl apply` install needs on top of that: no Helm leftovers, no rendering
placeholder in a file, and a Secret generator that provides every key the
pods require.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
BASE = REPO_ROOT / "k8s" / "apowerb"
PUBLIC = REPO_ROOT / "k8s" / "apowerb-public"
GENERATOR = REPO_ROOT / "scripts" / "generate-k8s-secret.sh"


def _docs(directory: Path) -> list[dict]:
    docs = []
    for path in sorted(directory.glob("*.yaml")):
        docs += [d for d in yaml.safe_load_all(path.read_text(encoding="utf-8")) if d]
    return docs


def _secret_refs(docs: list[dict]) -> tuple[set[str], set[str]]:
    """Keys of `apowerb-secrets` the pods read: (required, optional)."""
    required, optional = set(), set()

    def walk(node):
        if isinstance(node, dict):
            ref = node.get("secretKeyRef")
            if isinstance(ref, dict) and ref.get("name") == "apowerb-secrets":
                (optional if ref.get("optional") else required).add(ref["key"])
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(docs)
    return required, optional - required


@pytest.fixture(scope="module")
def generated_secret(tmp_path_factory) -> dict:
    out = tmp_path_factory.mktemp("secret") / "secret.yaml"
    subprocess.run(["bash", str(GENERATOR), str(out)], check=True, capture_output=True)
    return yaml.safe_load(out.read_text(encoding="utf-8")) | {"_path": out}


def test_the_stack_is_complete():
    kinds = {(d["kind"], d["metadata"]["name"]) for d in _docs(BASE)}
    for expected in [
        ("Namespace", "apowerb"),
        ("Deployment", "apowerb-backend"),
        ("Deployment", "apowerb-frontend"),
        ("StatefulSet", "apowerb-postgres"),
        ("Deployment", "apowerb-th2etl"),
        ("Job", "apowerb-th2etl-seed"),
        ("Deployment", "apowerb-th2pulse"),
        ("Deployment", "apowerb-otel-collector"),
        ("PersistentVolumeClaim", "apowerb-data"),
    ]:
        assert expected in kinds, f"{expected} missing from k8s/apowerb"
    assert not any(kind == "Secret" for kind, _ in kinds), "a Secret must never be committed"
    assert not any(kind == "Ingress" for kind, _ in kinds), "the Ingress belongs to k8s/apowerb-public"


def test_everything_lives_in_the_namespace():
    for doc in _docs(BASE) + _docs(PUBLIC):
        if doc["kind"] != "Namespace":
            assert doc["metadata"].get("namespace") == "apowerb", doc["metadata"]["name"]


def test_no_helm_leftovers_and_no_placeholder():
    for path in list(BASE.glob("*.yaml")) + list(PUBLIC.glob("*.yaml")):
        text = path.read_text(encoding="utf-8")
        assert "helm.sh/" not in text, f"{path.name}: Helm annotation on a kubectl install"
        assert "render-placeholder" not in text, f"{path.name}: a rendering value leaked into a file"
        assert "{{" not in text, f"{path.name}: unrendered template"


def test_public_set_carries_the_url_and_the_ingress():
    docs = {d["kind"]: d for d in _docs(PUBLIC)}
    assert set(docs) == {"Deployment", "Ingress"}
    env = {
        e["name"]: e.get("value")
        for c in docs["Deployment"]["spec"]["template"]["spec"]["containers"]
        for e in c.get("env", [])
    }
    assert env.get("APP_PUBLIC_URL") == "https://apowerb.example.com"
    assert env.get("PUBLIC_BASE_URL") == "https://apowerb.example.com"
    assert docs["Ingress"]["spec"]["rules"][0]["host"] == "apowerb.example.com"
    # The base backend has no public URL: the two Deployments differ only there.
    base_backend = next(d for d in _docs(BASE) if d["metadata"]["name"] == "apowerb-backend")
    base_env = {
        e["name"] for c in base_backend["spec"]["template"]["spec"]["containers"] for e in c.get("env", [])
    }
    assert "APP_PUBLIC_URL" not in base_env


def test_generated_secret_provides_every_required_key(generated_secret):
    required, optional = _secret_refs(_docs(BASE) + _docs(PUBLIC))
    data = generated_secret["stringData"]
    assert generated_secret["metadata"] == {"name": "apowerb-secrets", "namespace": "apowerb"}
    missing = required - data.keys()
    assert not missing, f"pods would stay in CreateContainerConfigError: {sorted(missing)}"
    # An optional key present but empty is read as a choice by the core.
    assert not (optional & data.keys()), "optional keys must be absent, not empty"
    for key in ("DB_PASSWORD", "ENCRYPT_KEY", "TH2ETL_API_KEY", "TH2PULSE_INGEST_TOKEN", "TH2PULSE_QUERY_TOKEN"):
        assert data[key], f"{key} is empty"


def test_generated_dsn_matches_the_database(generated_secret):
    data = generated_secret["stringData"]
    postgres = next(d for d in _docs(BASE) if d["kind"] == "Service" and d["metadata"]["name"] == "apowerb-postgres")
    assert data["TH2PULSE_DB_DSN"] == (
        f"postgresql://{data['DB_USER']}:{data['DB_PASSWORD']}@{postgres['metadata']['name']}:5432/{data['DB_NAME']}"
    )


def test_generated_secret_is_private_and_never_overwritten(generated_secret):
    path = generated_secret["_path"]
    assert oct(os.stat(path).st_mode & 0o777) == "0o600"
    before = path.read_text(encoding="utf-8")
    result = subprocess.run(["bash", str(GENERATOR), str(path)], capture_output=True, text=True)
    assert result.returncode != 0
    assert path.read_text(encoding="utf-8") == before


def test_default_secret_path_is_ignored_by_git():
    ignored = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "k8s/secret.yaml" in ignored
