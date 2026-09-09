#!/usr/bin/env python3
"""Proposer le bump des images quand une version plus recente est PUBLIEE.

Sur cette plateforme le tag doit rester explicite : mesure du 04/09, avec
`latest` le deploiement ne montre AUCUNE ligne `Pulling`, finit en 5 s et
annonce un succes pendant que le conteneur garde l'image en cache. Ce
deploiement a servi trois semaines un backend du 18/08 sans que rien ne le
contredise. Le 09/09, la meme chose a piege un controle fait a la main.

Le tag explicite est donc obligatoire ; le changer A LA MAIN dans le panneau
ne l'est pas. Ce script compare les defauts du compose aux dernieres releases
et rend le nouveau contenu du fichier. Ouvrir la PR est le travail du workflow
qui l'appelle ; relire et merger reste celui d'un humain -- et c'est la que le
garde du contrat compose se prononce.

Deux refus deliberes :
  * on ne propose RIEN tant que l'image n'est pas sur Docker Hub. Une release
    peut exister pendant que sa construction tourne encore ; proposer alors un
    tag qui n'existe pas produirait un deploiement en echec.
  * on ne touche qu'aux DEFAUTS du compose. Une valeur posee dans le panneau
    gagne de toute facon, et la reecrire ici ne la changerait pas.

Usage :
    propose_bump.py            # ecrit le fichier si besoin, rend le resume
    propose_bump.py --dry-run  # ne touche a rien
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import sys
import urllib.error
import urllib.request

COMPOSE = pathlib.Path("docker-compose.yml")

# (variable du compose, depot GitHub, depot Docker Hub)
IMAGES = [
    ("APOWERB_BACKEND_TAG", "apowerb/apowerb", "apowerb/apowerb"),
    ("APOWERB_FRONTEND_TAG", "apowerb/apowerb-ui", "apowerb/apowerb-ui"),
]


def _get(url: str, token: str | None = None) -> dict | None:
    req = urllib.request.Request(url, headers={"User-Agent": "apowerb-bump"})
    if token and "api.github.com" in url:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as exc:
        print(f"  ! {url} -> HTTP {exc.code}")
    except Exception as exc:  # reseau, TLS
        print(f"  ! {url} -> {exc}")
    return None


def derniere_release(repo: str, token: str | None) -> str | None:
    d = _get(f"https://api.github.com/repos/{repo}/releases/latest", token)
    if not d or d.get("draft") or d.get("prerelease"):
        return None
    return (d.get("tag_name") or "").lstrip("v") or None


def image_publiee(depot: str, tag: str) -> bool:
    """L'image existe-t-elle VRAIMENT, et pour de vraies architectures ?

    Un tag peut exister et ne porter qu'une archive de quelques kilo-octets :
    le 08/09, un chart Helm a ete pousse dans le depot des images du produit.
    """
    d = _get(f"https://hub.docker.com/v2/repositories/{depot}/tags/{tag}")
    if not d or d.get("message"):
        return False
    archs = {i.get("architecture") for i in d.get("images", []) if i.get("architecture")}
    return bool(archs) and (d.get("full_size") or 0) > 10_000_000


def defaut_actuel(texte: str, variable: str) -> str | None:
    m = re.search(r"\$\{" + variable + r":-([^}]+)\}", texte)
    return m.group(1) if m else None


def plus_recent(a: str, b: str) -> bool:
    """`a` est-il strictement plus recent que `b` ? Comparaison numerique."""
    def cle(v: str) -> tuple:
        return tuple(int(x) for x in re.findall(r"\d+", v))
    try:
        return cle(a) > cle(b)
    except ValueError:
        return False


def main() -> int:
    dry = "--dry-run" in sys.argv
    token = os.environ.get("GITHUB_TOKEN")
    texte = COMPOSE.read_text()
    lignes: list[str] = []
    change = False

    for variable, repo, depot in IMAGES:
        actuel = defaut_actuel(texte, variable)
        if actuel is None:
            print(f"  ! {variable} introuvable dans {COMPOSE}")
            continue
        publie = derniere_release(repo, token)
        if not publie:
            print(f"  {variable} : aucune release lisible, on ne touche a rien")
            continue
        if not plus_recent(publie, actuel):
            print(f"  {variable} : {actuel} est a jour (derniere release {publie})")
            continue
        if not image_publiee(depot, publie):
            print(
                f"  {variable} : release {publie} annoncee mais l'image "
                f"{depot}:{publie} n'est pas (encore) publiee -- on attend"
            )
            continue
        texte = texte.replace(
            "${" + variable + ":-" + actuel + "}",
            "${" + variable + ":-" + publie + "}",
            1,
        )
        lignes.append(f"| `{variable}` | `{actuel}` | `{publie}` |")
        change = True
        print(f"  {variable} : {actuel} -> {publie}")

    if not change:
        print("Rien a proposer.")
        return 0

    if dry:
        print("\n--dry-run : le fichier n'a pas ete ecrit.")
    else:
        COMPOSE.write_text(texte)

    corps = pathlib.Path("bump-body.md")
    contenu = (
        "Les images epinglees par ce fichier sont en retard sur les dernieres "
        "releases publiees.\n\n"
        "| variable | avant | apres |\n|---|---|---|\n" + "\n".join(lignes) + "\n\n"
        "Sur cette plateforme le tag doit rester explicite : avec `latest`, le "
        "deploiement ne montre aucune ligne `Pulling`, finit en cinq secondes et "
        "annonce un succes pendant que le conteneur garde l'image en cache. Ce "
        "deploiement a servi trois semaines un backend du 18/08 sans que rien ne "
        "le contredise.\n\n"
        "L'image a ete verifiee presente sur Docker Hub, avec de vraies "
        "architectures, avant que cette PR soit ouverte.\n\n"
        "> **A faire par le relecteur.** Une PR ouverte par le jeton du workflow "
        "ne declenche pas les autres workflows (anti-boucle GitHub) : lancez "
        "**Contrat compose** en `workflow_dispatch` sur cette branche avant de "
        "merger. C'est lui qui dira si la nouvelle version du coeur apporte des "
        "reglages que ce fichier ne declare pas encore.\n"
    )
    if dry:
        print("\n--- corps de PR qui serait ecrit ---")
        print(contenu)
    else:
        corps.write_text(contenu)
    return 0


if __name__ == "__main__":
    sys.exit(main())
