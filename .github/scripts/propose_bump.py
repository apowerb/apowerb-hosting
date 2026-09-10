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

Deux fichiers epinglent des images, et les DEUX sont surveilles :
  * `docker-compose.yml` -- ce que Hostman deploie ;
  * `helm/apowerb-chart/values.yaml` -- ce qu'une installation Kubernetes
    obtient. Il a longtemps echappe a ce script : le 10/09/26 le chart servait
    encore le coeur 0.2.12 et l'interface 0.1.20, deux versions derriere, sans
    que rien ne le signale. Une surveillance qui ne couvre qu'un fichier sur
    deux laisse croire que les deux sont surveilles.

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
CHART_VALUES = pathlib.Path("helm/apowerb-chart/values.yaml")
CHART_YAML = pathlib.Path("helm/apowerb-chart/Chart.yaml")

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


def _bloc_du_depot(texte: str, depot: str) -> tuple[int, int] | None:
    """Bornes du bloc YAML qui suit ``repository: <depot>``.

    Ancre en FIN DE LIGNE, et c'est tout l'interet : `apowerb/apowerb` est un
    prefixe de `apowerb/apowerb-ui`. Sans le `$`, le bloc du backend
    engloberait celui de l'interface et le script epinglerait le tag du coeur
    sur l'image du front. Un prefixe decrit ce qu'on croit avoir nomme.
    """
    m = re.search(
        r"^[ \t]*repository:[ \t]*" + re.escape(depot) + r"[ \t]*$", texte, re.M
    )
    if not m:
        return None
    suivant = re.search(r"^[ \t]*repository:", texte[m.end():], re.M)
    fin = m.end() + (suivant.start() if suivant else len(texte) - m.end())
    return m.end(), fin


def tag_du_chart(texte: str, depot: str) -> str | None:
    """Le tag epingle pour *depot* dans le values du chart."""
    bornes = _bloc_du_depot(texte, depot)
    if bornes is None:
        return None
    m = re.search(r"^[ \t]*tag:[ \t]*(\S+)[ \t]*$", texte[bornes[0]:bornes[1]], re.M)
    return m.group(1) if m else None


def poser_tag_du_chart(texte: str, depot: str, tag: str) -> str:
    """Rend le texte avec le tag de *depot* remplace. Ne touche que son bloc."""
    debut, fin = _bloc_du_depot(texte, depot)  # type: ignore[misc]
    bloc = texte[debut:fin]
    bloc = re.sub(
        r"^([ \t]*tag:[ \t]*)\S+([ \t]*)$", r"\g<1>" + tag + r"\2", bloc, count=1, flags=re.M
    )
    return texte[:debut] + bloc + texte[fin:]


def version_suivante(version: str) -> str:
    """Increment du patch. Un values modifie sans bump republierait un contenu
    different sous un numero deja tire -- refuse le 08/09/26, et la raison n'a
    pas change : un numero de version ne doit designer qu'un seul contenu."""
    parties = version.strip().split(".")
    parties[-1] = str(int(parties[-1]) + 1)
    return ".".join(parties)


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
    chart = CHART_VALUES.read_text() if CHART_VALUES.exists() else None
    lignes: list[str] = []
    change = False
    change_chart = False
    tag_backend_publie = None

    for variable, repo, depot in IMAGES:
        publie = derniere_release(repo, token)
        if not publie:
            print(f"  {depot} : aucune release lisible, on ne touche a rien")
            continue
        # Ce controle vaut pour les DEUX fichiers : proposer un tag dont
        # l image n existe pas produirait un deploiement en echec, que le tag
        # soit epingle par le compose ou par le chart.
        if not image_publiee(depot, publie):
            print(
                f"  {depot} : release {publie} annoncee mais l image "
                f"{depot}:{publie} n est pas (encore) publiee -- on attend"
            )
            continue

        # --- le compose -----------------------------------------------------
        actuel = defaut_actuel(texte, variable)
        if actuel is None:
            print(f"  ! {variable} introuvable dans {COMPOSE}")
        elif not plus_recent(publie, actuel):
            print(f"  {variable} : {actuel} est a jour (derniere release {publie})")
        else:
            texte = texte.replace(
                "${" + variable + ":-" + actuel + "}",
                "${" + variable + ":-" + publie + "}",
                1,
            )
            lignes.append(f"| compose | `{variable}` | `{actuel}` | `{publie}` |")
            change = True
            print(f"  {variable} : {actuel} -> {publie}")

        # --- le chart -------------------------------------------------------
        # Surtout PAS derriere un `continue` du compose : c est exactement
        # comme ca que le chart est reste deux versions en arriere sans que
        # rien ne le signale. Les deux fichiers se lisent independamment.
        if chart is None:
            continue
        actuel_chart = tag_du_chart(chart, depot)
        if actuel_chart is None:
            print(f"  ! {depot} introuvable dans {CHART_VALUES}")
            continue
        if not plus_recent(publie, actuel_chart):
            print(f"  chart {depot} : {actuel_chart} est a jour")
            continue
        chart = poser_tag_du_chart(chart, depot, publie)
        lignes.append(f"| chart | `{depot}` | `{actuel_chart}` | `{publie}` |")
        change = change_chart = True
        if depot == "apowerb/apowerb":
            tag_backend_publie = publie
        print(f"  chart {depot} : {actuel_chart} -> {publie}")

    if not change:
        print("Rien a proposer.")
        return 0

    chart_yaml = None
    if change_chart and CHART_YAML.exists():
        chart_yaml = CHART_YAML.read_text()
        m = re.search(r"^version:[ \t]*(\S+)[ \t]*$", chart_yaml, re.M)
        if m:
            neuve = version_suivante(m.group(1))
            chart_yaml = chart_yaml[:m.start(1)] + neuve + chart_yaml[m.end(1):]
            lignes.append(f"| chart | `version` | `{m.group(1)}` | `{neuve}` |")
            print(f"  chart version : {m.group(1)} -> {neuve}")
        # appVersion dit quelle version du PRODUIT ce chart installe, pas
        # quelle version le chart a. Elle suit donc le coeur.
        if tag_backend_publie:
            a = re.search(r"^appVersion:[ \t]*\"?([^\"\s]+)\"?[ \t]*$", chart_yaml, re.M)
            if a and a.group(1) != tag_backend_publie:
                chart_yaml = (
                    chart_yaml[:a.start(1)] + tag_backend_publie + chart_yaml[a.end(1):]
                )
                lignes.append(
                    f"| chart | `appVersion` | `{a.group(1)}` | `{tag_backend_publie}` |"
                )
                print(f"  chart appVersion : {a.group(1)} -> {tag_backend_publie}")

    if dry:
        print("\n--dry-run : aucun fichier n a ete ecrit.")
    else:
        COMPOSE.write_text(texte)
        if change_chart:
            CHART_VALUES.write_text(chart)
            if chart_yaml is not None:
                CHART_YAML.write_text(chart_yaml)

    corps = pathlib.Path("bump-body.md")
    contenu = (
        "Les images epinglees sont en retard sur les dernieres releases "
        "publiees. Le compose et le chart Helm sont lus separement : l un peut "
        "etre a jour pendant que l autre ne l est pas.\n\n"
        "| fichier | cle | avant | apres |\n|---|---|---|---|\n" + "\n".join(lignes) + "\n\n"
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
