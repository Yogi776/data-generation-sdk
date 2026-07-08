# Homebrew Packaging — Maintainer Docs

This directory contains the tooling that maintains the Homebrew tap
(`Yogi776/homebrew-tap`) for `ai-data-platform`.

## Files

| File | Purpose |
|------|---------|
| `generate_formula.py` | Regenerates `Formula/ai-data-platform.rb` from PyPI + poet |
| `formula_template.rb` | Stable Ruby header/footer merged with poet output |
| `sync_tap.sh` | Local dry-run helper (runs generate_formula.py + shows diff) |

## How the automation works

Every GitHub Release on `data-generation-sdk` triggers `update-homebrew-tap`
in `.github/workflows/publish.yml`. That job:

1. Waits 90 s for PyPI to index the new artifact.
2. Reads the version from `github.event.release.tag_name` (strips leading `v`).
3. Calls `generate_formula.py` which:
   - Fetches the sdist URL + SHA256 from PyPI JSON API.
   - Runs `homebrew-pypi-poet -f ai-data-platform[all]==VERSION` to generate
     `resource` blocks for every transitive dependency.
   - Merges poet output into `formula_template.rb`.
4. Commits the new `Formula/ai-data-platform.rb` to `homebrew-tap` via
   `HOMEBREW_TAP_TOKEN` (fine-grained PAT).
5. Pushes to `homebrew-tap main`.
6. Sends a `repository_dispatch` event to trigger `brew-test.yml` in the tap.

## One-time setup

```bash
# Install poet
pip install homebrew-pypi-poet

# Verify formula generation locally
cd packaging/homebrew
./generate_formula.py --version 0.3.0 --dry-run | head -50

# Dry-run sync
../sync_tap.sh --version 0.3.0 --dry-run
```

## Manual formula update (no release)

If PyPI is lagging and you need to force-regenerate:

```bash
cd packaging/homebrew
python generate_formula.py --version 0.3.0 --output /tmp/ai-data-platform.rb
# inspect /tmp/ai-data-platform.rb then copy to the tap repo
```

## Adding the token secret

1. Create a fine-grained PAT on GitHub.com:
   - **Account**: Yogi776
   - **Repository access**: Only `homebrew-tap`
   - **Permissions**: Contents: Read and write
2. Add the token to `data-generation-sdk` → Settings → Secrets as
   `HOMEBREW_TAP_TOKEN`.
3. Verify the tap workflow has `workflow_dispatch` trigger so you can test
   manually before the next release.

## First bootstrap (one-time only)

When releasing the **very first version**:

```bash
# 1. Create the empty tap repo on GitHub: Yogi776/homebrew-tap
# 2. Generate the formula for the current version
python generate_formula.py --version 0.3.0 --output ../homebrew-tap-formula.rb

# 3. Manually push the bootstrap commit to the tap repo
#    (the automated workflow will keep it updated after this)
cd $HOME/projects/homebrew-tap
git checkout -b main
mkdir -p Formula
cp $HOME/projects/data-generation-sdk/packaging/homebrew/homebrew-tap-formula.rb Formula/ai-data-platform.rb
git add Formula/ai-data-platform.rb
git commit -m "ai-data-platform 0.3.0"
git remote add origin git@github.com:Yogi776/homebrew-tap.git
git push -u origin main

# 4. Verify locally (on a Mac with Homebrew installed)
brew tap yogi776/tap
brew install ai-data-platform
adp version
brew uninstall ai-data-platform
```

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `poet: error: argument -f: invalid value` | Use `ai-data-platform[all]` (with quotes) |
| SHA256 mismatch after PyPI re-release | Re-run `generate_formula.py` with the new version |
| Formula not updating after release | Check `HOMEBREW_TAP_TOKEN` still valid; manually trigger `update-homebrew-tap` via workflow dispatch |
| `brew install` fails with PEP 668 | Formula correctly uses isolated `libexec` venv — this should not happen; if seen, Homebrew may need `without_pip: false` |
