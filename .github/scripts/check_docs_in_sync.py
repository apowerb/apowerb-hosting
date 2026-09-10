#!/usr/bin/env python3
"""La doc publiee doit dire ce que ce depot deploie.

Le 08/09/2026, `docs.apowerb.com` a servi pendant une heure
`helm install apowerb oci://registry-1.docker.io/apowerb/apowerb --version 0.2.0`
alors que le chart s'appelait `apowerb-chart` et sortait en 0.4.1. La commande
FONCTIONNAIT -- l'ancien chart est toujours tirable -- et installait la pile
d'avant th2etl, th2pulse et le volume persistant. Aucune erreur pour le
lecteur, aucun rouge nulle part : c'est ce silence que ce garde supprime.

Il compare trois faits de ce depot a ce que le depot de doc ecrit :

    nom du chart      -> l'adresse OCI citee
    version du chart  -> le `--version` cite a cote
    chemin du chart   -> les `helm/<...>` cites

Quand la doc de `main` est en retard, le garde regarde les PR ouvertes du
depot de doc AVANT de refuser : preparer les deux ensemble est le geste
attendu, pas une entorse. Il n'exige rien d'autre -- ni tournure, ni page
particuliere -- pour ne pas devenir un correcteur de style qu'on finit par
contourner.
"""
from __future__ import annotations

import io
import json
import os
import pathlib
import re
import sys
import tarfile
import urllib.error
import urllib.request

DOCS_REPO = os.environ.get("DOCS_REPO", "apowerb/apowerb-docs")
CHART_DIR = os.environ.get("CHART_DIR", "helm/apowerb-chart")
API = "https://api.github.com"

OCI_RE = re.compile(r"oci://registry-1\.docker\.io/([A-Za-z0-9._-]+/[A-Za-z0-9._-]+)")
# GHCR a ete retire le 08/09/2026 : le push y reussissait, mais un paquet nait
# PRIVE dans une organisation GitHub, donc `helm pull` y repondait 403 en
# anonyme. Une adresse qui ne sert personne est pire qu'une adresse absente.
GHCR_RE = re.compile(r"oci://ghcr\.io/[A-Za-z0-9._-]+/[A-Za-z0-9._-]+")
VERSION_RE = re.compile(r"--version\s+([0-9][0-9A-Za-z.+-]*)")
HELM_PATH_RE = re.compile(r"helm/([A-Za-z0-9._-]+)")

# Une doc a le droit de citer ce qui n'est plus vrai -- c'est meme ainsi qu'on
# explique une panne. La ligne portant ce marqueur, ou la ligne juste avant,
# sort du controle. Explicite et visible en revue : un garde sans echappatoire
# se fait contourner autrement, en general en le desactivant tout entier.
IGNORE = "docs-in-sync: ignore"


def chart_facts(chart_dir: str) -> tuple[str, str]:
    """Nom et version lus dans Chart.yaml, sans dependance a PyYAML."""
    name = version = ""
    with open(f"{chart_dir}/Chart.yaml", encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("name:"):
                name = line.split(":", 1)[1].strip().strip("\"'")
            elif line.startswith("version:"):
                version = line.split(":", 1)[1].strip().strip("\"'")
    if not name or not version:
        sys.exit(f"{chart_dir}/Chart.yaml : nom ou version introuvable")
    return name, version


def api(path: str) -> object:
    """GET sur l'API GitHub. Le jeton est optionnel : les depots sont publics,
    mais sans lui le quota anonyme est de 60 appels par heure."""
    req = urllib.request.Request(f"{API}{path}")
    req.add_header("Accept", "application/vnd.github+json")
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as exc:
        sys.exit(f"GitHub {exc.code} sur {path} : {exc.reason}")


def mdx_sources(ref: str) -> dict[str, str]:
    """Les .mdx du depot de doc a une reference donnee.

    Par l'archive plutot que fichier par fichier : une quarantaine de pages
    faisaient autant d'appels a l'API, et le quota anonyme est de soixante par
    heure -- un garde qui s'epuise tout seul n'est pas un garde.
    """
    url = f"{API}/repos/{DOCS_REPO}/tarball/{ref}"
    req = urllib.request.Request(url)
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        sys.exit(f"GitHub {exc.code} sur {url} : {exc.reason}")

    out: dict[str, str] = {}
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tar:
        for member in tar.getmembers():
            if not member.isfile() or not member.name.endswith(".mdx"):
                continue
            # Le premier segment est le prefixe que GitHub ajoute
            # (`apowerb-apowerb-docs-<sha>/`), inutile dans un message.
            path = member.name.split("/", 1)[1]
            fh = tar.extractfile(member)
            if fh is not None:
                out[path] = fh.read().decode("utf-8", "replace")
    return out


def _commande(lines: list[str], n: int) -> str:
    """La ligne n et ses continuations `\\`, recollees.

    Une commande helm lisible tient sur plusieurs lignes ; la version y est
    alors sur sa propre ligne. En lisant ligne a ligne, le controle de version
    ne voyait que les commandes ecrites d'un seul tenant -- c'est-a-dire
    exactement celles qu'une documentation soignee n'ecrit pas.
    """
    bloc = [lines[n - 1]]
    i = n - 1
    while i < len(lines) and lines[i - 1].rstrip().endswith("\\"):
        bloc.append(lines[i])
        i += 1
    return "\n".join(bloc)


def offences(sources: dict[str, str], name: str, version: str, chart_dir: str
             ) -> list[str]:
    """Chaque mention qui contredit ce depot, avec son fichier et sa ligne."""
    want_repo = f"apowerb/{name}"
    want_path = chart_dir.split("/")[-1]
    found: list[str] = []
    for path, text in sorted(sources.items()):
        lines = text.splitlines()
        for n, line in enumerate(lines, 1):
            previous = lines[n - 2] if n >= 2 else ""
            if IGNORE in line or IGNORE in previous:
                continue
            for repo in OCI_RE.findall(line):
                # Une adresse OCI qui ne nomme pas ce chart : soit elle vise
                # l'ancien depot, soit elle vise les images. Les deux se
                # lisent pareil et une seule est une commande d'installation.
                if repo != want_repo:
                    found.append(f"{path}:{n} — adresse OCI `{repo}`, "
                                 f"attendu `{want_repo}`")
                # La commande entiere, continuations comprises.
                for v in VERSION_RE.findall(_commande(lines, n)):
                    if v != version:
                        found.append(f"{path}:{n} — `--version {v}` sur une "
                                     f"commande OCI, chart en {version}")
            for dead in GHCR_RE.findall(line):
                found.append(f"{path}:{n} — `{dead}` : GHCR a été retiré, "
                             f"le paquet y est privé et `helm pull` rend 403")
            for d in HELM_PATH_RE.findall(line):
                if d != want_path and d.startswith("apowerb"):
                    found.append(f"{path}:{n} — chemin `helm/{d}`, "
                                 f"attendu `helm/{want_path}`")
    return found


def open_doc_prs() -> list[tuple[int, str, str]]:
    prs = api(f"/repos/{DOCS_REPO}/pulls?state=open&per_page=50")
    return [(p["number"], p["title"], p["head"]["sha"]) for p in prs]


def local_sources() -> dict[str, str]:
    """Les README de CE depot.

    Ils décrivent l'installation du chart qu'ils accompagnent, donc ils
    peuvent le contredire exactement comme la doc en ligne -- et pendant que
    le garde ne regardait qu'ailleurs, `helm/apowerb-chart/README.md` a servi
    `--version 0.4.1` pendant que le chart était en 0.4.2.
    """
    out: dict[str, str] = {}
    for chemin in [pathlib.Path("README.md"), *pathlib.Path(".").glob("helm/*/README.md")]:
        if chemin.is_file():
            out[str(chemin)] = chemin.read_text(encoding="utf-8")
    return out


def main() -> int:
    name, version = chart_facts(CHART_DIR)
    print(f"Ce dépôt déploie : chart {name} {version} ({CHART_DIR})")

    # D'abord chez soi : une commande fausse ici n'a besoin de la PR de
    # personne pour être corrigée, donc elle ne bénéficie d'aucun sursis.
    chez_soi = offences(local_sources(), name, version, CHART_DIR)
    if chez_soi:
        print("\nLes README de ce dépôt le contredisent :")
        for line in chez_soi:
            print(f"  {line}")
        print("\nCorrigez-les dans cette PR : elles décrivent le chart "
              "qu'elles accompagnent, et une commande périmée s'installe "
              "sans erreur.")
        return 1

    bad = offences(mdx_sources("main"), name, version, CHART_DIR)
    if not bad:
        print(f"{DOCS_REPO}@main est d'accord. Rien à faire.")
        return 0

    print(f"\n{DOCS_REPO}@main contredit ce dépôt :")
    for line in bad:
        print(f"  {line}")

    # Le garde ne demande pas de merger la doc d'abord -- il demande qu'elle
    # soit ECRITE. Une PR ouverte qui corrige tout suffit.
    for number, title, sha in open_doc_prs():
        if not offences(mdx_sources(sha), name, version, CHART_DIR):
            print(f"\n…mais {DOCS_REPO}#{number} le corrige : « {title} ».")
            print("Mergez-la avant (ou avec) celle-ci.")
            return 0

    print(f"\nAucune PR ouverte de {DOCS_REPO} ne corrige ces lignes.")
    print("La doc en ligne enverra les lecteurs sur une commande périmée —")
    print("qui fonctionne, et installe la pile d'avant. Ouvrez la PR de doc.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
