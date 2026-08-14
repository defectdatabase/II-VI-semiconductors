#!/usr/bin/env python3
"""Build the static site from the repository-local template.

The relaxation-movie viewer is Kosmos's own built app, vendored under
docs/pages/traj/ and served as-is, so its MatterViz settings are byte-identical
to the reference site.

The scientific payload is loaded by the browser from docs/data.json and the
compressed side payloads in docs/{structures,trajs,dos}. This build step only
publishes the interface shell, which keeps it reproducible on any machine.
"""

import hashlib
import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
TEMPLATE = REPO / "site_src" / "template.html"
OUTPUT = REPO / "docs" / "index.html"
VERSION = REPO / "docs" / "version.json"
DATA = REPO / "docs" / "data.json"


def main() -> None:
    if not DATA.is_file():
        raise FileNotFoundError(f"Required site payload is missing: {DATA}")

    html = TEMPLATE.read_text(encoding="utf-8")
    if 'fetch("data.json")' not in html:
        raise RuntimeError("Template does not load the external data payload")

    # GitHub Pages serves index.html with cache-control: max-age=600, so a reader can sit on a
    # stale shell for ten minutes after a publish. Stamp the build and let the page notice.
    build_id = hashlib.sha256(html.encode("utf-8")).hexdigest()[:12]
    html = html.replace("__BUILD_ID__", build_id)
    OUTPUT.write_text(html, encoding="utf-8")
    VERSION.write_text(json.dumps({"id": build_id}), encoding="utf-8")
    print(f"Published {TEMPLATE.relative_to(REPO)} to {OUTPUT.relative_to(REPO)} (build {build_id})")


if __name__ == "__main__":
    main()
