"""Le script de bump doit suivre CHAQUE chemin d'installation.

Sa premiere PR reussie (#61, 18/09/26) passait Hostman et le chart en 0.2.26
et laissait le quickstart -- ce qu'installe un nouveau venu -- sur l'image
d'avant. Ces tests rejouent le script sur une copie des vrais fichiers du
depot, reseau remplace : une release plus recente est publiee, tout doit
suivre.
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
    """Une copie des fichiers epingles, et un script qui ne sort pas sur le reseau.

    Seul le coeur a une release plus recente ; l'interface annonce une version
    plus vieille que celle epinglee, donc elle ne doit pas bouger.
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
    """`apowerb/apowerb` est un prefixe de `apowerb/apowerb-ui` : le bump du
    coeur ne doit jamais atteindre l'image du front."""
    racine, module = depot
    front_avant = _lire(racine, "k8s/04-frontend.yaml")

    module.main()

    assert _lire(racine, "k8s/04-frontend.yaml") == front_avant
    assert NEUVE not in _lire(racine, "k8s/04-frontend.yaml")


def test_un_suiveur_en_retard_seul_suffit_a_proposer(depot):
    """Le cas qui a produit #61, a l'envers : Hostman et le chart sont deja a
    jour, seul le quickstart est en retard. Il doit y avoir une PR."""
    racine, module = depot
    module.main()                                   # tout passe en 9.9.9
    qs = racine / "docker-compose/docker-compose.yml"
    qs.write_text(qs.read_text().replace(f"APOWERB_BACKEND_TAG:-{NEUVE}}}", "APOWERB_BACKEND_TAG:-0.0.2}"))

    module.main()

    assert f"APOWERB_BACKEND_TAG:-{NEUVE}}}" in qs.read_text()


def test_le_corps_de_pr_demande_la_pr_de_doc(depot):
    racine, module = depot
    module.main()
    corps = (racine / "bump-body.md").read_text()
    assert "PR de doc compagnon" in corps
    assert "deployment/helmchart.mdx" in corps


def test_rien_a_proposer_ne_touche_a_rien(depot, monkeypatch):
    racine, module = depot
    avant = {nom: _lire(racine, nom) for nom in FICHIERS}
    monkeypatch.setattr(module, "derniere_release", lambda repo, token: "0.0.1")

    assert module.main() == 0

    assert {nom: _lire(racine, nom) for nom in FICHIERS} == avant
    assert not (racine / "bump-body.md").exists()
