#!/usr/bin/env python3
"""
generate_formula.py — regenerate the Homebrew formula for ai-data-platform.

Usage
-----
    python generate_formula.py --version 0.3.0
    python generate_formula.py --version 0.3.0 --output Formula/ai-data-platform.rb
    python generate_formula.py --version 0.3.0 --dry-run

How it works
------------
1. Fetch PyPI JSON metadata for the requested version.
2. Locate the sdist artifact and extract its SHA256 digest.
3. Use homebrew-pypi-poet to generate `resource` blocks for all transitive
   dependencies of ai-data-platform[all].
4. Patch poet's output: url, sha256, depends_on (python@3.12), desc, homepage.
5. Write the resulting formula to --output (or stdout).

One-time poet setup
-------------------
    pip install homebrew-pypi-poet

Homebrew best practice: regenerate resource blocks on every release so that
transitive dependency pins never go stale.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

PACKAGE_NAME = "ai-data-platform"
PYPI_JSON_URL_TEMPLATE = "https://pypi.org/pypi/{name}/{version}/json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def fetch(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.loads(resp.read().decode())


def sha256_of_url(url: str) -> str:
    with urllib.request.urlopen(url, timeout=60) as resp:
        h = hashlib.sha256()
        while chunk := resp.read(65536):
            h.update(chunk)
        return h.hexdigest()


def run_poet(package: str, version: str) -> str:
    """
    Call homebrew-pypi-poet to generate a complete formula.
    poet must be installed and on PATH.
    """
    cmd = ["poet", "-f", f"{package}=={version}"]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def patch_formula(
    formula_text: str,
    version: str,
    pypi_url: str,
    sha256: str,
) -> str:
    """
    Patch poet's output formula:
    - Replace the top-level URL with the sdist URL for the specific version
    - Replace the top-level SHA256 with the actual digest
    - Leave resource URLs/SHAs untouched (they have their own values)
    - Ensure depends_on python@3.12 (poet sometimes uses python@3.y)
    - Set desc and homepage to our values
    """
    lines = formula_text.splitlines(keepends=True)
    result_lines: list[str] = []
    in_resource = False

    for line in lines:
        stripped = line.strip()

        # Track whether we're inside a resource block (indented lines after "resource ")
        if stripped.startswith("resource "):
            in_resource = True
            result_lines.append(line)
            continue
        # Top-level lines are at 2 spaces; resource body is at 4+ spaces
        if in_resource and line.startswith("    "):
            result_lines.append(line)
            continue
        # Exited resource block
        in_resource = False

        # Patch top-level URL line
        if stripped.startswith("url "):
            result_lines.append(f'  url "{pypi_url}"\n')
        # Patch top-level SHA256 line
        elif stripped.startswith("sha256 "):
            result_lines.append(f'  sha256 "{sha256}"\n')
        # Force python@3.12
        elif stripped.startswith("depends_on ") and "python" in stripped:
            result_lines.append('  depends_on "python@3.12"\n')
        # Replace placeholder desc
        elif stripped.startswith('desc "') and "Shiny new formula" in stripped:
            result_lines.append(
                '  desc "AI Data Platform: synthetic data, catalog, semantic models, MCP server"\n'
            )
        # Replace placeholder homepage
        elif stripped.startswith("homepage ") and ("None" in stripped or "example.com" in stripped):
            result_lines.append(
                '  homepage "https://github.com/Yogi776/data-generation-sdk"\n'
            )
        else:
            result_lines.append(line)

    return "".join(result_lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Regenerate the Homebrew formula for ai-data-platform."
    )
    parser.add_argument(
        "--version", required=True, help="Package version to generate formula for (e.g. 0.3.0)"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output path for the formula file (default: stdout)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print to stdout instead of writing --output",
    )
    parser.add_argument(
        "--extras",
        default="[all]",
        help="PyPI extras to include (default: [all])",
    )
    args = parser.parse_args()

    version = args.version.strip()
    extras = args.extras.strip()
    # poet -f package==version handles [extras] natively
    poet_pkg = f"{PACKAGE_NAME}{extras}" if extras else PACKAGE_NAME

    # Step 1 — PyPI metadata
    pypi_json = fetch(PYPI_JSON_URL_TEMPLATE.format(name=PACKAGE_NAME, version=version))
    sdist_entry = None
    for entry in pypi_json["urls"]:
        if entry["packagetype"] == "sdist":
            sdist_entry = entry
            break

    if sdist_entry is None:
        print(
            f"ERROR: No sdist found for {PACKAGE_NAME}=={version}",
            file=sys.stderr,
        )
        return 1

    pypi_url: str = sdist_entry["url"]
    sha256: str = sdist_entry["digests"]["sha256"]

    print(f"  Package : {poet_pkg}=={version}", file=sys.stderr)
    print(f"  URL     : {pypi_url}", file=sys.stderr)
    print(f"  SHA256  : {sha256}", file=sys.stderr)

    # Step 2 — homebrew-pypi-poet generates a complete formula
    try:
        poet_output = run_poet(poet_pkg, version)
    except FileNotFoundError:
        print(
            "ERROR: homebrew-pypi-poet not found. Install with: pip install homebrew-pypi-poet",
            file=sys.stderr,
        )
        return 1
    except subprocess.CalledProcessError as exc:
        print(f"ERROR: poet exited {exc.returncode}: {exc.stderr}", file=sys.stderr)
        return 1

    # Validate class name
    if "class AiDataPlatform" not in poet_output:
        print("ERROR: poet output missing 'class AiDataPlatform'; formula may be malformed.", file=sys.stderr)
        return 1

    # Step 3 — patch poet's output: url, sha256, depends_on, desc, homepage
    formula = patch_formula(poet_output, version, pypi_url, sha256)

    # Step 4 — output
    if args.dry_run or args.output is None:
        print(formula)
    else:
        Path(args.output).write_text(formula, encoding="utf-8")
        print(f"Written: {args.output}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
