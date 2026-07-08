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
4. Merge poet's output with the stable header/footer in formula_template.rb.
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
FORMULA_TEMPLATE_PATH = Path(__file__).parent / "formula_template.rb"


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


def run_poet(package_with_extras: str, version: str) -> str:
    """
    Call homebrew-pypi-poet to generate resource blocks.
    poet must be installed and on PATH.
    """
    cmd = ["poet", "-f", package_with_extras]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=True,
        env={**os.environ, "PIP_CONSTRAINT": ""},
    )
    return result.stdout


def substitute_template(
    template: str,
    version: str,
    pypi_url: str,
    sha256: str,
    poet_output: str,
) -> str:
    """
    Fill in the formula template with version-specific values.
    The template uses {{placeholder}} syntax.
    """
    substitutions = {
        "{{version}}": version,
        "{{pypi_url}}": pypi_url,
        "{{sha256}}": sha256,
        "{{poet_resources}}": poet_output,
    }
    result = template
    for placeholder, value in substitutions.items():
        result = result.replace(placeholder, value)
    return result


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
    package_with_extras = f"{PACKAGE_NAME}{args.extras}".replace("[all]", "")
    # homebrew-pypi-poet expects plain "pkg" or "pkg[extra]" without the [all] extras
    poet_package = PACKAGE_NAME + args.extras if args.extras else PACKAGE_NAME
    # poet -f expects the full package spec with extras
    poet_arg = f"{PACKAGE_NAME}{args.extras}"

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

    print(f"  Package : {PACKAGE_NAME}=={version}", file=sys.stderr)
    print(f"  URL     : {pypi_url}", file=sys.stderr)
    print(f"  SHA256  : {sha256}", file=sys.stderr)

    # Step 2 — homebrew-pypi-poet
    try:
        poet_output = run_poet(poet_package, version)
    except FileNotFoundError:
        print(
            "ERROR: homebrew-pypi-poet not found. Install with: pip install homebrew-pypi-poet",
            file=sys.stderr,
        )
        return 1
    except subprocess.CalledProcessError as exc:
        print(f"ERROR: poet exited {exc.returncode}: {exc.stderr}", file=sys.stderr)
        return 1

    # Step 3 — merge with template
    template_path = FORMULA_TEMPLATE_PATH
    if template_path.exists():
        template = template_path.read_text(encoding="utf-8")
    else:
        # Inline fallback template when run outside the repo
        template = _FALLBACK_TEMPLATE

    formula = substitute_template(template, version, pypi_url, sha256, poet_output)

    # Validate class name
    if "class AiDataPlatform" not in formula:
        print("ERROR: poet output missing 'class AiDataPlatform'; formula may be malformed.", file=sys.stderr)
        return 1

    # Step 4 — output
    if args.dry_run or args.output is None:
        print(formula)
    else:
        Path(args.output).write_text(formula, encoding="utf-8")
        print(f"Written: {args.output}", file=sys.stderr)

    return 0


_FALLBACK_TEMPLATE = """\
class AiDataPlatform < Formula
  include Language::Python::Virtualenv

  desc "AI Data Platform: synthetic data, catalog, semantic models, MCP server"
  homepage "https://github.com/Yogi776/data-generation-sdk"
  url "{{pypi_url}}"
  sha256 "{{sha256}}"
  license "Apache-2.0"

  depends_on "python@3.12"

{{poet_resources}}

  def install
    virtualenv_install_with_resources
  end

  test do
    assert_match version.to_s, shell_output("#{bin}/adp version")
    shell_output("#{bin}/adp --help")
    shell_output("#{bin}/adp mcp-server --help")
    cd testpath do
      system bin/"adp", "init", "--name", "brew-smoke"
      assert_path_exists testpath/"adp.yaml"
    end
  end
end
"""


if __name__ == "__main__":
    raise SystemExit(main())
