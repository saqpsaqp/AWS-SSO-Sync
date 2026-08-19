# Contributing

## Workflow: pull requests only

**No direct commits or pushes to `master`.** Every change — including
one-line fixes — goes through:

```bash
git checkout master
git pull --ff-only origin master
git checkout -b my-change
# ... commit your work ...
git push -u origin my-change
gh pr create
```

Always create feature branches from an up-to-date `master`. Pull (fast-forward
only) before branching so the new work starts from the current default tip,
not a stale local copy.

This applies to everyone, including automated tools. In this repo, a
project-level Claude Code hook (`.claude/hooks/git-push-guard.sh`, wired up
in `.claude/settings.json`) blocks any `git push` that targets `master`/
`main` directly, or that uses `--force`/`-f`, when working through Claude
Code — but the rule itself isn't conditional on the hook being active;
please follow it manually too (e.g. plain `git`/GitHub web UI usage).

If you have push access and are tempted to bypass this for something
"trivial," don't — enable branch protection on `master` in the repo
settings (require a PR before merging) so the rule holds regardless of who
or what is pushing.

## Keep the docs in sync

Every change that adds or modifies a feature (a new module, CLI flag, menu
option, or config field) must, in the same PR:

- Update **`CLAUDE.md`** — it's the map of the codebase for anyone (human
  or AI) picking this up next. A stale architecture section is worse than
  none.
- Update **`docs/USAGE.md`** (and `README.md`'s quick menu summary, if it's
  affected) — this is the only user-facing documentation; there's no other
  help text.

A PR that changes behavior without touching these should be treated as
incomplete.

## Security

See [SECURITY.md](SECURITY.md). In short: never commit real AWS
credentials, session tokens, or private key files to this repo — it's
public. A best-effort content-scanning hook
(`.claude/hooks/git-secret-guard.sh`) catches some of this automatically
when working through Claude Code, but review your own diffs before
committing regardless.

## Releasing

Versioning follows [SemVer](https://semver.org/) (`vMAJOR.MINOR.PATCH`).
`aws_sso_sync/__init__.py`'s `__version__` is the single source of truth —
`pyproject.toml` reads it dynamically (`dynamic = ["version"]`), so there's
only one place to bump.

1. Open a PR that bumps `__version__` in `aws_sso_sync/__init__.py`. Merge
   it like any other change (see above).
2. On an up-to-date `master`, tag and push the tag:
   ```bash
   git checkout master
   git pull --ff-only origin master
   git tag v1.2.3
   git push origin v1.2.3
   ```
   Pushing a tag isn't a push to `master`/`main`, so it isn't affected by
   the PR-only rule or `git-push-guard.sh` above.
3. `.github/workflows/release.yml` picks up the `v*.*.*` tag push and
   creates the GitHub Release automatically, with notes generated from the
   merged PRs since the last tag — nothing further to do.

Existing installs only pick this up when a user runs "Actualizar aplicación"
(or `update.sh`) — both fast-forward to the latest `vX.Y.Z` tag, not to the
tip of `master`. Until you tag, merged PRs sit on `master` unreleased and
no install will fetch them.

## Adding a language

All menu text goes through `aws_sso_sync/i18n/t(key, **kwargs)`, backed by
plain-dict catalogs under `aws_sso_sync/i18n/catalog/` (no `gettext`/`.mo`
compilation - this repo has no build step). `en.py` is the reference
catalog; every other catalog must carry the exact same keys.

1. Copy `aws_sso_sync/i18n/catalog/en.py` to
   `aws_sso_sync/i18n/catalog/<code>.py` (e.g. `fr.py` for French - use the
   two-letter code you want to appear after `--lang`-style selection in the
   `[4] Idioma / Language` menu).
2. Translate every value. Keep every key and every `{placeholder}`
   identical - only the surrounding text changes.
3. Register it in `aws_sso_sync/i18n/__init__.py`:
   ```python
   from .catalog import en, es, fr  # add the import

   CATALOGS = {"en": en.STRINGS, "es": es.STRINGS, "fr": fr.STRINGS}
   LANGUAGE_NAMES = {"en": "English", "es": "Español", "fr": "Français"}
   ```
4. Run `python3 scripts/check_i18n.py` - it fails if your new catalog is
   missing keys or has extra ones not in `en.py`. CI runs this on every PR.
5. Manually walk through a few menus with your language selected (`[4]
   Idioma / Language` in the running CLI) to sanity-check line lengths and
   that placeholders read naturally in your language's word order.

`logger.debug(...)` calls are not part of this - they stay as internal
Spanish diagnostics, unrelated to the user-facing language setting.

## Local development

No test suite is configured — this is an interactive CLI with no
automated coverage of the menu flows themselves; manually walk through
whatever you touched (see `docs/USAGE.md`) before opening a PR.

Linting and formatting use [ruff](https://docs.astral.sh/ruff/)
(config in `pyproject.toml`'s `[tool.ruff]`). Before opening a PR:

```bash
python3 -m py_compile aws_sso_sync/*.py
pip install ruff
ruff check .
ruff format .
```

`.github/workflows/ci.yml` runs the same checks (syntax, `ruff check`,
`ruff format --check`, plus `python3 scripts/check_i18n.py` if you touched
a translation catalog) on every PR — a red CI check means one of these
would have failed locally too. See [SECURITY.md](SECURITY.md) for the rest
of what runs automatically (CodeQL, Dependabot).
