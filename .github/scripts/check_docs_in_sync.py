#!/usr/bin/env python3
"""The published docs must say what this repository deploys.

On 08/09/2026, `docs.apowerb.com` served for an hour
`helm install apowerb oci://registry-1.docker.io/apowerb/apowerb --version 0.2.0`
while the chart was called `apowerb-chart` and was at 0.4.1. The command
WORKED -- the old chart can still be pulled -- and installed the stack as it
was before th2etl, th2pulse and the persistent volume. No error for the
reader, no red anywhere: it is this silence that this guard removes.

It compares three facts from this repository with what the docs repository
says:

    chart name     -> the OCI address cited
    chart version  -> the `--version` cited next to it
    chart path     -> the `helm/<...>` paths cited

When the docs on `main` are behind, the guard looks at the docs repository's
open PRs BEFORE refusing: preparing both together is the expected practice,
not a workaround. It requires nothing else -- no particular wording, no
particular page -- so as not to become a style checker that people end up
working around.
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
# GHCR was removed on 08/09/2026: the push there succeeded, but a package is
# born PRIVATE in a GitHub organization, so `helm pull` answered 403
# anonymously there. An address that serves nobody is worse than no address.
GHCR_RE = re.compile(r"oci://ghcr\.io/[A-Za-z0-9._-]+/[A-Za-z0-9._-]+")
VERSION_RE = re.compile(r"--version\s+([0-9][0-9A-Za-z.+-]*)")
HELM_PATH_RE = re.compile(r"helm/([A-Za-z0-9._-]+)")

# A doc is allowed to cite what is no longer true -- that is even how an
# outage is explained. The line carrying this marker, or the line just before,
# is excluded from the check. Explicit and visible in review: a guard with no
# escape hatch gets worked around some other way, usually by disabling it
# altogether.
IGNORE = "docs-in-sync: ignore"


def chart_facts(chart_dir: str) -> tuple[str, str]:
    """Name and version read from Chart.yaml, without a PyYAML dependency."""
    name = version = ""
    with open(f"{chart_dir}/Chart.yaml", encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("name:"):
                name = line.split(":", 1)[1].strip().strip("\"'")
            elif line.startswith("version:"):
                version = line.split(":", 1)[1].strip().strip("\"'")
    if not name or not version:
        sys.exit(f"{chart_dir}/Chart.yaml: name or version not found")
    return name, version


def api(path: str) -> object:
    """GET on the GitHub API. The token is optional: the repositories are
    public, but without it the anonymous quota is 60 calls per hour."""
    req = urllib.request.Request(f"{API}{path}")
    req.add_header("Accept", "application/vnd.github+json")
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as exc:
        sys.exit(f"GitHub {exc.code} on {path}: {exc.reason}")


def mdx_sources(ref: str) -> dict[str, str]:
    """The .mdx files of the docs repository at a given reference.

    Through the archive rather than file by file: about forty pages meant as
    many API calls, and the anonymous quota is sixty per hour -- a guard that
    exhausts itself is not a guard.
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
        sys.exit(f"GitHub {exc.code} on {url}: {exc.reason}")

    out: dict[str, str] = {}
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tar:
        for member in tar.getmembers():
            if not member.isfile() or not member.name.endswith(".mdx"):
                continue
            # The first segment is the prefix GitHub adds
            # (`apowerb-apowerb-docs-<sha>/`), useless in a message.
            path = member.name.split("/", 1)[1]
            fh = tar.extractfile(member)
            if fh is not None:
                out[path] = fh.read().decode("utf-8", "replace")
    return out


def _commande(lines: list[str], n: int) -> str:
    """Line n and its `\\` continuations, joined back together.

    A readable helm command spans several lines; the version is then on its
    own line. Reading line by line, the version check only saw commands
    written in one piece -- that is, exactly the ones a careful documentation
    does not write.
    """
    bloc = [lines[n - 1]]
    i = n - 1
    while i < len(lines) and lines[i - 1].rstrip().endswith("\\"):
        bloc.append(lines[i])
        i += 1
    return "\n".join(bloc)


def offences(sources: dict[str, str], name: str, version: str, chart_dir: str
             ) -> list[str]:
    """Every mention that contradicts this repository, with its file and line."""
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
                # An OCI address that does not name this chart: either it targets
                # the old repository, or it targets the images. Both read the
                # same and only one is an install command.
                if repo != want_repo:
                    found.append(f"{path}:{n} — OCI address `{repo}`, "
                                 f"expected `{want_repo}`")
                # The whole command, continuations included.
                for v in VERSION_RE.findall(_commande(lines, n)):
                    if v != version:
                        found.append(f"{path}:{n} — `--version {v}` on an "
                                     f"OCI command, chart is at {version}")
            for dead in GHCR_RE.findall(line):
                found.append(f"{path}:{n} — `{dead}`: GHCR was removed, "
                             f"the package is private there and `helm pull` returns 403")
            for d in HELM_PATH_RE.findall(line):
                if d != want_path and d.startswith("apowerb"):
                    found.append(f"{path}:{n} — path `helm/{d}`, "
                                 f"expected `helm/{want_path}`")
    return found


def open_doc_prs() -> list[tuple[int, str, str]]:
    prs = api(f"/repos/{DOCS_REPO}/pulls?state=open&per_page=50")
    return [(p["number"], p["title"], p["head"]["sha"]) for p in prs]


def local_sources() -> dict[str, str]:
    """The READMEs of THIS repository.

    They describe how to install the chart they accompany, so they can
    contradict it exactly like the online docs -- and while the guard was
    looking only elsewhere, `helm/apowerb-chart/README.md` served
    `--version 0.4.1` while the chart was at 0.4.2.
    """
    out: dict[str, str] = {}
    for chemin in [pathlib.Path("README.md"), *pathlib.Path(".").glob("helm/*/README.md")]:
        if chemin.is_file():
            out[str(chemin)] = chemin.read_text(encoding="utf-8")
    return out


def main() -> int:
    name, version = chart_facts(CHART_DIR)
    print(f"This repository deploys: chart {name} {version} ({CHART_DIR})")

    # Our own files first: a wrong command here needs nobody else's PR to be
    # fixed, so it gets no grace period.
    chez_soi = offences(local_sources(), name, version, CHART_DIR)
    if chez_soi:
        print("\nThis repository's READMEs contradict it:")
        for line in chez_soi:
            print(f"  {line}")
        print("\nFix them in this PR: they describe the chart they "
              "accompany, and a stale command installs "
              "without any error.")
        return 1

    bad = offences(mdx_sources("main"), name, version, CHART_DIR)
    if not bad:
        print(f"{DOCS_REPO}@main agrees. Nothing to do.")
        return 0

    print(f"\n{DOCS_REPO}@main contradicts this repository:")
    for line in bad:
        print(f"  {line}")

    # The guard does not ask for the docs to be merged first -- it asks that
    # they be WRITTEN. An open PR that fixes everything is enough.
    for number, title, sha in open_doc_prs():
        if not offences(mdx_sources(sha), name, version, CHART_DIR):
            print(f"\n...but {DOCS_REPO}#{number} fixes it: \"{title}\".")
            print("Merge it before (or together with) this one.")
            return 0

    print(f"\nNo open PR in {DOCS_REPO} fixes these lines.")
    print("The online docs will send readers to a stale command --")
    print("one that works, and installs the previous stack. Open the docs PR.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
