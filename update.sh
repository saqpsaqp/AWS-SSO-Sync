#!/usr/bin/env bash
# Updates this aws-sso-sync checkout to the latest published release tag
# (vX.Y.Z) and refreshes the editable install. Same logic as the CLI's
# "Actualizar aplicación" menu option, for users who'd rather run it
# directly. Deliberately does not just `git pull` to the tip of master:
# only tagged releases (see CONTRIBUTING.md's "Releasing" section) reach
# installs, so merged-but-unreleased commits never land here.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$REPO_DIR/.venv"

echo "Actualizando aws-sso-sync en $REPO_DIR ..."
git -C "$REPO_DIR" fetch --tags --quiet

LATEST_TAG="$(git -C "$REPO_DIR" tag --list 'v*.*.*' --sort=-v:refname | head -n1)"
if [ -z "$LATEST_TAG" ]; then
    echo "⚠️  Todavía no hay ningún release publicado (falta un tag vX.Y.Z)."
    exit 1
fi

git -C "$REPO_DIR" merge --ff-only "$LATEST_TAG"

if [ -x "$VENV_DIR/bin/pip" ]; then
    "$VENV_DIR/bin/pip" install -e "$REPO_DIR" --quiet
fi

echo "✅ Actualizado a $LATEST_TAG."
