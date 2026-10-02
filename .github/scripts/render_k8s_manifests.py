#!/usr/bin/env python3
"""Renders the plain Kubernetes manifests in `k8s/` from the Helm chart.

The chart stays the single source of truth. The manifests exist for people who
install with `kubectl` alone; they are GENERATED, never edited by hand,
because hand-written copies drift: the old `k8s/00-05` files did exactly
that, and `kubectl apply -f k8s/` ended up installing a stack without th2etl,
th2pulse, the collector or the data volume while looking complete.

  python3 .github/scripts/render_k8s_manifests.py           # rewrite k8s/
  python3 .github/scripts/render_k8s_manifests.py --check   # CI: fail on drift

Two sets are written:
  * `k8s/apowerb/` -- the whole stack without an Ingress;
  * `k8s/apowerb-public/` -- the two objects that change for a public address:
    the Ingress, and the backend Deployment carrying the public URL (CORS
    origins and OAuth callbacks derive from it).

No Secret is rendered (`secret.create=false`): the values passed below only
satisfy the chart's install-time checks and never reach a file. The Secret is
written by `scripts/generate-k8s-secret.sh`, outside version control.

Helm-only annotations are removed: on a `kubectl` install, `helm.sh/hook`
and `helm.sh/resource-policy` would claim a behaviour nobody provides.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
CHART = ROOT / "helm" / "apowerb-chart"
OUT_BASE = ROOT / "k8s" / "apowerb"
OUT_PUBLIC = ROOT / "k8s" / "apowerb-public"
NAMESPACE = "apowerb"
PUBLIC_HOST = "apowerb.example.com"

# Placeholders for `_validate.tpl` only. With `secret.create=false` they are
# rendered nowhere; `--check` and the tests prove it.
VALIDATION_ONLY = [
    "secret.create=false",
    "postgres.password=render-placeholder",
    "backend.env.encryptKey=render-placeholder",
    "th2pulse.ingestToken=render-placeholder",
    "th2pulse.queryToken=render-placeholder",
]
PUBLIC = [
    "ingress.enabled=true",
    "ingress.className=traefik",
    f"ingress.host={PUBLIC_HOST}",
    "ingress.tlsEnabled=true",
    r"ingress.annotations.cert-manager\.io/cluster-issuer=letsencrypt-staging",
]
PUBLIC_FILES = ("backend-deployment.yaml", "ingress.yaml")

HEADER = (
    "# GENERATED from helm/apowerb-chart by .github/scripts/render_k8s_manifests.py\n"
    "# -- do not edit: change the chart, then re-run the script.\n"
)
NAMESPACE_MANIFEST = f"""apiVersion: v1
kind: Namespace
metadata:
  name: {NAMESPACE}
"""


def helm_template(extra: list[str], out: pathlib.Path) -> pathlib.Path:
    cmd = ["helm", "template", "apowerb", str(CHART), "--namespace", NAMESPACE, "--output-dir", str(out)]
    for value in VALIDATION_ONLY + extra:
        cmd += ["--set", value]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
    return out / "apowerb-chart" / "templates"


def strip_helm_annotations(text: str) -> str:
    """Drops `helm.sh/*` annotations, then any `annotations:` left empty.

    An emptied block keeps its comments when they explain the object (the seed
    `Job`), and loses them when they explain Helm's behaviour (the data claim
    "survives an uninstall"): left in place, they would promise a protection a
    `kubectl` install does not have."""
    lines = [l for l in text.splitlines() if not re.match(r'\s*"?helm\.sh/', l)]
    kept: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r"^(\s*)annotations:\s*$", line)
        if m:
            indent = len(m.group(1))
            j = i + 1
            block: list[str] = []
            while j < len(lines) and (
                lines[j].strip() == "" or len(lines[j]) - len(lines[j].lstrip()) > indent
            ):
                block.append(lines[j])
                j += 1
            if not any(l.strip() and not l.strip().startswith("#") for l in block):
                comments = [l for l in block if l.strip().startswith("#")]
                if not any("helm" in l.lower() for l in comments):
                    kept.extend(" " * indent + l.strip() for l in comments)
                i = j
                continue
        kept.append(line)
        i += 1
    return "\n".join(kept) + "\n"


def render(base_dir: pathlib.Path, public_dir: pathlib.Path) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        base = helm_template([], tmp / "base")
        public = helm_template(PUBLIC, tmp / "public")
        base_dir.mkdir(parents=True, exist_ok=True)
        public_dir.mkdir(parents=True, exist_ok=True)
        # `kubectl apply -f <dir>` goes in alphabetical order: the Namespace
        # must come first, and the chart does not create one.
        (base_dir / "00-namespace.yaml").write_text(HEADER + "---\n" + NAMESPACE_MANIFEST)
        for src in sorted(base.glob("*.yaml")):
            (base_dir / src.name).write_text(HEADER + strip_helm_annotations(src.read_text()))
        for name in PUBLIC_FILES:
            text = strip_helm_annotations((public / name).read_text())
            (public_dir / name).write_text(HEADER + text)


def snapshot(*dirs: pathlib.Path) -> dict[str, str]:
    return {
        str(p.relative_to(d.parent)): p.read_text()
        for d in dirs if d.is_dir() for p in sorted(d.glob("*.yaml"))
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail if k8s/ differs from a fresh render")
    args = parser.parse_args()

    if not args.check:
        for d in (OUT_BASE, OUT_PUBLIC):
            for old in d.glob("*.yaml") if d.is_dir() else []:
                old.unlink()  # a template removed from the chart must disappear here too
        render(OUT_BASE, OUT_PUBLIC)
        print(f"Rendered {len(list(OUT_BASE.glob('*.yaml')))} + {len(list(OUT_PUBLIC.glob('*.yaml')))} manifests.")
        return 0

    with tempfile.TemporaryDirectory() as tmp:
        fresh_base = pathlib.Path(tmp) / "apowerb"
        fresh_public = pathlib.Path(tmp) / "apowerb-public"
        render(fresh_base, fresh_public)
        fresh = snapshot(fresh_base, fresh_public)
    current = snapshot(OUT_BASE, OUT_PUBLIC)
    drift = sorted(
        name for name in fresh.keys() | current.keys() if fresh.get(name) != current.get(name)
    )
    if drift:
        print("k8s/ does not match the chart. Re-run:")
        print("  python3 .github/scripts/render_k8s_manifests.py")
        for name in drift:
            state = "missing" if name not in current else "extra" if name not in fresh else "differs"
            print(f"  k8s/{name}: {state}")
        return 1
    print(f"k8s/ matches the chart ({len(fresh)} manifests).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
