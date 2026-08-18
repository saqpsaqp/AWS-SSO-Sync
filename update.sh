#!/usr/bin/env bash
# Updates this aws-sso-sync checkout to the latest git revision and
# refreshes the editable install. Same logic as the CLI's "Actualizar
# aplicación" menu option, for users who'd rather run it directly.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$REPO_DIR/.venv"

echo "Actualizando aws-sso-sync en $REPO_DIR ..."
git -C "$REPO_DIR" pull --ff-only

if [ -x "$VENV_DIR/bin/pip" ]; then
    "$VENV_DIR/bin/pip" install -e "$REPO_DIR" --quiet
fi

echo "✅ Actualizado."
