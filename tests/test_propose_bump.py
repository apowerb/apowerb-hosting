"""The bump script must follow EVERY installation path.

Its first successful PR (#61, 18/09/26) moved Hostman and the chart to 0.2.26
and left the quickstart -- what a newcomer installs -- on the previous image.
These tests replay the script on a copy of the repository's real files, with
the network replaced: a newer release is published, everything must follow.
"""

from __future__ import annotations

import importlib.util
import pathlib
import shutil

import pytest

RACINE = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = RACINE / ".github" / "scripts" / "propose_bump.py"
FICHIERS = [
    "docker-compose.yml",
    "docker-compose/docker-compose.yml",
    ".env.example",
    "k8s/03-backend.yaml",
    "k8s/04-frontend.yaml",
    "helm/apowerb-chart/values.yaml",
    "helm/apowerb-chart/Chart.yaml",
    "helm/apowerb-chart/README.md",
]
NEUVE = "9.9.9"


def _charger():
    spec = importlib.util.spec_from_file_location("propose_bump", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def depot(tmp_path, monkeypatch):
    """A copy of the pinned files, and a script that does not go out on the network.

    Only the core has a newer release; the interface announces a version
    older than the pinned one, so it must not move.
    """
    for nom in FICHIERS:
        cible = tmp_path / nom
        cible.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(RACINE / nom, cible)
    monkeypatch.chdir(tmp_path)
    module = _charger()
    monkeypatch.setattr(
        module, "derniere_release",
        lambda repo, token: NEUVE if repo == "apowerb/apowerb" else "0.0.1",
    )
    monkeypatch.setattr(module, "image_publiee", lambda depot, tag: True)
    monkeypatch.setattr(module.sys, "argv", ["propose_bump.py"])
    return tmp_path, module


def _lire(racine, nom):
    return (racine / nom).read_text()


def test_chaque_chemin_d_installation_suit_le_coeur(depot):
    racine, module = depot
    version_avant = module.re.search(
        r"^version:\s*(\S+)", _lire(racine, "helm/apowerb-chart/Chart.yaml"), module.re.M
    ).group(1)

    assert module.main() == 0

    assert f"APOWERB_BACKEND_TAG:-{NEUVE}}}" in _lire(racine, "docker-compose.yml")
    assert f"APOWERB_BACKEND_TAG:-{NEUVE}}}" in _lire(racine, "docker-compose/docker-compose.yml")
    assert f"APOWERB_BACKEND_TAG={NEUVE}" in _lire(racine, ".env.example")
    assert f"image: apowerb/apowerb:{NEUVE}" in _lire(racine, "k8s/03-backend.yaml")
    assert f"tag: {NEUVE}" in _lire(racine, "helm/apowerb-chart/values.yaml")
    chart = _lire(racine, "helm/apowerb-chart/Chart.yaml")
    assert f'appVersion: "{NEUVE}"' in chart
    version_apres = module.version_suivante(version_avant)
    assert f"version: {version_apres}" in chart
    assert f"--version {version_apres}" in _lire(racine, "helm/apowerb-chart/README.md")
    assert f"--version {version_avant}" not in _lire(racine, "helm/apowerb-chart/README.md")


def test_l_interface_ne_suit_pas_le_coeur(depot):
    """`apowerb/apowerb` is a prefix of `apowerb/apowerb-ui`: the core's bump
    must never reach the frontend image."""
    racine, module = depot
    front_avant = _lire(racine, "k8s/04-frontend.yaml")

    module.main()

    assert _lire(racine, "k8s/04-frontend.yaml") == front_avant
    assert NEUVE not in _lire(racine, "k8s/04-frontend.yaml")


def test_un_suiveur_en_retard_seul_suffit_a_proposer(depot):
    """The case that produced #61, reversed: Hostman and the chart are already
    up to date, only the quickstart is behind. There must be a PR."""
    racine, module = depot
    module.main()                                   # everything moves to 9.9.9
    qs = racine / "docker-compose/docker-compose.yml"
    qs.write_text(qs.read_text().replace(f"APOWERB_BACKEND_TAG:-{NEUVE}}}", "APOWERB_BACKEND_TAG:-0.0.2}"))

    module.main()

    assert f"APOWERB_BACKEND_TAG:-{NEUVE}}}" in qs.read_text()


def test_le_corps_de_pr_demande_la_pr_de_doc(depot):
    racine, module = depot
    module.main()
    corps = (racine / "bump-body.md").read_text()
    assert "Companion docs PR" in corps
    assert "deployment/helmchart.mdx" in corps
    # Since apowerb-docs#51, only the Helm page pins the chart version.
    assert "deployment/kubernetes.mdx" not in corps


def test_rien_a_proposer_ne_touche_a_rien(depot, monkeypatch):
    racine, module = depot
    avant = {nom: _lire(racine, nom) for nom in FICHIERS}
    monkeypatch.setattr(module, "derniere_release", lambda repo, token: "0.0.1")

    assert module.main() == 0

    assert {nom: _lire(racine, nom) for nom in FICHIERS} == avant
    assert not (racine / "bump-body.md").exists()


def test_le_moteur_de_prevision_suit_sa_release(depot, monkeypatch):
    """th2forecast publishes its images per release (apowerb/th2forecast#14):
    a newer release must reach the chart and the quickstart, without touching
    the core or the interface."""
    racine, module = depot
    monkeypatch.setattr(
        module, "derniere_release",
        lambda repo, token: NEUVE if repo == "apowerb/th2forecast" else "0.0.1",
    )
    k8s_avant = {nom: _lire(racine, nom) for nom in FICHIERS if nom.startswith("k8s/")}

    assert module.main() == 0

    assert f"TH2FORECAST_TAG:-{NEUVE}}}" in _lire(racine, "docker-compose/docker-compose.yml")
    values = _lire(racine, "helm/apowerb-chart/values.yaml")
    assert module.tag_du_chart(values, "apowerb/th2forecast-py") == NEUVE
    assert module.tag_du_chart(values, "apowerb/apowerb") != NEUVE
    assert f"APOWERB_BACKEND_TAG:-{NEUVE}}}" not in _lire(racine, "docker-compose.yml")
    assert {nom: _lire(racine, nom) for nom in k8s_avant} == k8s_avant
