#!/usr/bin/env python3
"""Build the static site from the repository-local template.

The relaxation-movie viewer is Kosmos's own built app, vendored under
docs/pages/traj/ and served as-is, so its MatterViz settings are byte-identical
to the reference site.

The scientific payload is loaded by the browser from docs/data.json and the
compressed side payloads in docs/{structures,trajs,dos}. This build step only
publishes the interface shell, which keeps it reproducible on any machine.
"""

from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
TEMPLATE = REPO / "site_src" / "template.html"
OUTPUT = REPO / "docs" / "index.html"
DATA = REPO / "docs" / "data.json"


def main() -> None:
    if not DATA.is_file():
        raise FileNotFoundError(f"Required site payload is missing: {DATA}")

    html = TEMPLATE.read_text(encoding="utf-8")
    if 'fetch("data.json")' not in html:
        raise RuntimeError("Template does not load the external data payload")

    OUTPUT.write_text(html, encoding="utf-8")
    print(f"Published {TEMPLATE.relative_to(REPO)} to {OUTPUT.relative_to(REPO)}")


if __name__ == "__main__":
    main()
