#!/usr/bin/env python3
"""Propose an image bump when a newer version has been PUBLISHED.

On this platform the tag must stay explicit: measured on 04/09, with
`latest` the deployment shows NO `Pulling` line, finishes in 5 s and
reports success while the container keeps the cached image. That
deployment served a backend from 18/08 for three weeks with nothing to
contradict it. On 09/09, the same thing trapped a check made by hand.

The explicit tag is therefore mandatory; changing it BY HAND in the panel
is not. This script compares the compose defaults with the latest releases
and produces the new file contents. Opening the PR is the job of the
workflow that calls it; reviewing and merging remains a human's -- and that
is where the compose contract guard weighs in.

Each installation path reads ITS own line, and all of them are watched:
  * `docker-compose.yml` -- what Hostman deploys;
  * `helm/apowerb-chart/values.yaml` -- what a Kubernetes installation
    gets. It escaped this script for a long time: on 10/09/26 the chart still
    served core 0.2.12 and interface 0.1.20, two versions behind, with
    nothing to flag it. A watch that covers only one file out of two makes
    people believe both are watched;
  * `docker-compose/docker-compose.yml` -- the self-hosted quickstart;
  * `.env.example` -- what people copy to get started;
  * `k8s/*.yaml` -- the raw manifests;
  * the `helm install` command in the chart's README, which cites its version.
The last four escaped this script until 18/09/26: the first PR it managed to
open (#61) moved Hostman and the chart to 0.2.26 and left the quickstart --
what a newcomer installs -- on the previous image.

Two deliberate refusals:
  * NOTHING is proposed until the image is on Docker Hub. A release can
    exist while its build is still running; proposing a tag that does not
    exist would produce a failed deployment.
  * only the compose DEFAULTS are touched. A value set in the panel wins
    anyway, and rewriting it here would not change it.

Usage:
    propose_bump.py            # writes the file if needed, prints the summary
    propose_bump.py --dry-run  # touches nothing
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
CHART_README = pathlib.Path("helm/apowerb-chart/README.md")
QUICKSTART = pathlib.Path("docker-compose/docker-compose.yml")
ENV_EXAMPLE = pathlib.Path(".env.example")
K8S_DIR = pathlib.Path("k8s")

# (compose variable, GitHub repo, Docker Hub repo)
IMAGES = [
    ("APOWERB_BACKEND_TAG", "apowerb/apowerb", "apowerb/apowerb"),
    ("APOWERB_FRONTEND_TAG", "apowerb/apowerb-ui", "apowerb/apowerb-ui"),
    # Forecasting engine: image published per release of apowerb/th2forecast
    # (apowerb/th2forecast#14). Not in the Hostman compose; followed in the
    # chart and the quickstart.
    ("TH2FORECAST_TAG", "apowerb/th2forecast", "apowerb/th2forecast-py"),
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
    except Exception as exc:  # network, TLS
        print(f"  ! {url} -> {exc}")
    return None


def derniere_release(repo: str, token: str | None) -> str | None:
    d = _get(f"https://api.github.com/repos/{repo}/releases/latest", token)
    if not d or d.get("draft") or d.get("prerelease"):
        return None
    return (d.get("tag_name") or "").lstrip("v") or None


def image_publiee(depot: str, tag: str) -> bool:
    """Does the image REALLY exist, and for real architectures?

    A tag can exist and carry only an archive of a few kilobytes:
    on 08/09, a Helm chart was pushed to the product's image repository.
    """
    d = _get(f"https://hub.docker.com/v2/repositories/{depot}/tags/{tag}")
    if not d or d.get("message"):
        return False
    archs = {i.get("architecture") for i in d.get("images", []) if i.get("architecture")}
    return bool(archs) and (d.get("full_size") or 0) > 10_000_000


def defaut_actuel(texte: str, variable: str) -> str | None:
    m = re.search(r"\$\{" + variable + r":-([^}]+)\}", texte)
    return m.group(1) if m else None


def valeur_env(texte: str, variable: str) -> str | None:
    """The value of ``VARIABLE=...`` in a .env file, whole line."""
    m = re.search(r"^" + variable + r"=(\S+)[ \t]*$", texte, re.M)
    return m.group(1) if m else None


def tag_k8s(texte: str, depot: str) -> str | None:
    """The tag of ``image: <repo>:<tag>``. The ``:`` after the repo is what
    distinguishes `apowerb/apowerb:` from `apowerb/apowerb-ui:`."""
    m = re.search(r"image:[ \t]*" + re.escape(depot) + r":(\S+)", texte)
    return m.group(1) if m else None


def _bloc_du_depot(texte: str, depot: str) -> tuple[int, int] | None:
    """Bounds of the YAML block that follows ``repository: <repo>``.

    Anchored at END OF LINE, and that is the whole point: `apowerb/apowerb` is
    a prefix of `apowerb/apowerb-ui`. Without the `$`, the backend's block
    would swallow the interface's and the script would pin the core's tag on
    the frontend image. A prefix describes what you think you named.
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
    """The tag pinned for *depot* in the chart's values."""
    bornes = _bloc_du_depot(texte, depot)
    if bornes is None:
        return None
    m = re.search(r"^[ \t]*tag:[ \t]*(\S+)[ \t]*$", texte[bornes[0]:bornes[1]], re.M)
    return m.group(1) if m else None


def poser_tag_du_chart(texte: str, depot: str, tag: str) -> str:
    """Returns the text with the tag of *depot* replaced. Touches only its block."""
    debut, fin = _bloc_du_depot(texte, depot)  # type: ignore[misc]
    bloc = texte[debut:fin]
    bloc = re.sub(
        r"^([ \t]*tag:[ \t]*)\S+([ \t]*)$", r"\g<1>" + tag + r"\2", bloc, count=1, flags=re.M
    )
    return texte[:debut] + bloc + texte[fin:]


def version_suivante(version: str) -> str:
    """Patch increment. A modified values file without a bump would republish
    different content under an already-pulled number -- refused on 08/09/26,
    and the reason has not changed: a version number must designate only one
    piece of content."""
    parties = version.strip().split(".")
    parties[-1] = str(int(parties[-1]) + 1)
    return ".".join(parties)


def plus_recent(a: str, b: str) -> bool:
    """Is `a` strictly newer than `b`? Numeric comparison."""
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
    publies: list[tuple[str, str, str]] = []
    # Follower files rewritten: path -> new content.
    suiveurs: dict[pathlib.Path, str] = {}

    for variable, repo, depot in IMAGES:
        publie = derniere_release(repo, token)
        if not publie:
            print(f"  {depot}: no readable release, touching nothing")
            continue
        # This check applies to BOTH files: proposing a tag whose image does
        # not exist would produce a failed deployment, whether the tag is
        # pinned by the compose file or by the chart.
        if not image_publiee(depot, publie):
            print(
                f"  {depot}: release {publie} announced but image "
                f"{depot}:{publie} is not (yet) published -- waiting"
            )
            continue

        publies.append((variable, depot, publie))

        # --- the compose file -----------------------------------------------
        actuel = defaut_actuel(texte, variable)
        if actuel is None:
            print(f"  ! {variable} not found in {COMPOSE}")
        elif not plus_recent(publie, actuel):
            print(f"  {variable}: {actuel} is up to date (latest release {publie})")
        else:
            texte = texte.replace(
                "${" + variable + ":-" + actuel + "}",
                "${" + variable + ":-" + publie + "}",
                1,
            )
            lignes.append(f"| compose | `{variable}` | `{actuel}` | `{publie}` |")
            change = True
            print(f"  {variable}: {actuel} -> {publie}")

        # --- the chart ------------------------------------------------------
        # Above all NOT behind a compose `continue`: that is exactly how the
        # chart stayed two versions behind with nothing to flag it. The two
        # files are read independently.
        if chart is None:
            continue
        actuel_chart = tag_du_chart(chart, depot)
        if actuel_chart is None:
            print(f"  ! {depot} not found in {CHART_VALUES}")
            continue
        if not plus_recent(publie, actuel_chart):
            print(f"  chart {depot}: {actuel_chart} is up to date")
            continue
        chart = poser_tag_du_chart(chart, depot, publie)
        lignes.append(f"| chart | `{depot}` | `{actuel_chart}` | `{publie}` |")
        change = change_chart = True
        if depot == "apowerb/apowerb":
            tag_backend_publie = publie
        print(f"  chart {depot}: {actuel_chart} -> {publie}")

    # --- the followers -------------------------------------------------------
    # Each read on its own, like the chart: a file falls behind on its
    # own exactly when it is assumed to follow the others.
    def suivre(chemin: pathlib.Path, lire, poser, cle: str) -> None:
        nonlocal change
        if not chemin.exists():
            return
        texte_s = suiveurs.get(chemin, chemin.read_text())
        for variable, depot, publie in publies:
            actuel_s = lire(texte_s, variable, depot)
            if actuel_s is None or not plus_recent(publie, actuel_s):
                continue
            texte_s = poser(texte_s, variable, depot, actuel_s, publie)
            lignes.append(f"| {cle} | `{depot}` | `{actuel_s}` | `{publie}` |")
            change = True
            print(f"  {chemin} {depot}: {actuel_s} -> {publie}")
        if texte_s != chemin.read_text():
            suiveurs[chemin] = texte_s

    suivre(
        QUICKSTART,
        lambda t, v, d: defaut_actuel(t, v),
        lambda t, v, d, a, n: t.replace("${" + v + ":-" + a + "}", "${" + v + ":-" + n + "}", 1),
        "quickstart",
    )
    suivre(
        ENV_EXAMPLE,
        lambda t, v, d: valeur_env(t, v),
        lambda t, v, d, a, n: re.sub(
            r"^" + v + r"=" + re.escape(a) + r"([ \t]*)$", v + "=" + n + r"\1", t, count=1, flags=re.M
        ),
        ".env.example",
    )
    for manifeste in sorted(K8S_DIR.glob("*.yaml")) if K8S_DIR.is_dir() else []:
        suivre(
            manifeste,
            lambda t, v, d: tag_k8s(t, d),
            lambda t, v, d, a, n: t.replace(f"{d}:{a}", f"{d}:{n}"),
            f"k8s/{manifeste.name}",
        )

    if not change:
        print("Nothing to propose.")
        return 0

    chart_yaml = None
    version_chart_changee: tuple[str, str] | None = None
    if change_chart and CHART_YAML.exists():
        chart_yaml = CHART_YAML.read_text()
        m = re.search(r"^version:[ \t]*(\S+)[ \t]*$", chart_yaml, re.M)
        if m:
            neuve = version_suivante(m.group(1))
            chart_yaml = chart_yaml[:m.start(1)] + neuve + chart_yaml[m.end(1):]
            lignes.append(f"| chart | `version` | `{m.group(1)}` | `{neuve}` |")
            print(f"  chart version: {m.group(1)} -> {neuve}")
            version_chart_changee = (m.group(1), neuve)
            if CHART_README.exists():
                readme = CHART_README.read_text()
                ancienne = f"apowerb-chart --version {m.group(1)}"
                if ancienne in readme:
                    suiveurs[CHART_README] = readme.replace(
                        ancienne, f"apowerb-chart --version {neuve}"
                    )
                    lignes.append(f"| chart README | `--version` | `{m.group(1)}` | `{neuve}` |")
                    print(f"  chart README: --version {m.group(1)} -> {neuve}")
        # appVersion says which version of the PRODUCT this chart installs, not
        # which version the chart has. It therefore follows the core.
        if tag_backend_publie:
            a = re.search(r"^appVersion:[ \t]*\"?([^\"\s]+)\"?[ \t]*$", chart_yaml, re.M)
            if a and a.group(1) != tag_backend_publie:
                chart_yaml = (
                    chart_yaml[:a.start(1)] + tag_backend_publie + chart_yaml[a.end(1):]
                )
                lignes.append(
                    f"| chart | `appVersion` | `{a.group(1)}` | `{tag_backend_publie}` |"
                )
                print(f"  chart appVersion: {a.group(1)} -> {tag_backend_publie}")

    if dry:
        print("\n--dry-run: no file was written.")
    else:
        COMPOSE.write_text(texte)
        if change_chart:
            CHART_VALUES.write_text(chart)
            if chart_yaml is not None:
                CHART_YAML.write_text(chart_yaml)
        for chemin, contenu_s in suiveurs.items():
            chemin.write_text(contenu_s)

    corps = pathlib.Path("bump-body.md")
    contenu = (
        "The pinned images are behind the latest published releases. The "
        "compose file and the Helm chart are read separately: one can be up to "
        "date while the other is not.\n\n"
        "| file | key | before | after |\n|---|---|---|---|\n" + "\n".join(lignes) + "\n\n"
        "On this platform the tag must stay explicit: with `latest`, the "
        "deployment shows no `Pulling` line, finishes in five seconds and "
        "reports success while the container keeps the cached image. That "
        "deployment served a backend from 18/08 for three weeks with nothing "
        "to contradict it.\n\n"
        "The image was checked to be present on Docker Hub, with real "
        "architectures, before this PR was opened.\n\n"
        "> **To check by the reviewer.** **Compose contract** must appear "
        "among this PR's checks before merging: it will say whether the new "
        "core version brings settings that this file does not yet "
        "declare. Opened by `BUMP_TOKEN`, the PR triggers it "
        "by itself; if it is missing, run it with `workflow_dispatch` on this "
        "branch.\n"
    )
    if version_chart_changee:
        avant, apres = version_chart_changee
        contenu += (
            "\n> **Companion docs PR to open.** `apowerb/apowerb-docs` cites the "
            f"chart version in its `helm` commands: `--version {avant}` must "
            f"become `--version {apres}` (`deployment/helmchart.mdx`). The "
            "**Do the docs say what this "
            "repository deploys?** check fails until an open docs PR fixes it, "
            "and `BUMP_TOKEN` has no access to that repository. Merge after "
            "the chart's OCI publication, not before.\n"
        )
    if dry:
        print("\n--- PR body that would be written ---")
        print(contenu)
    else:
        corps.write_text(contenu)
    return 0


if __name__ == "__main__":
    sys.exit(main())
