#!/usr/bin/env bash
# Installs aws-sso-sync from this checkout: validates AWS CLI v2, backs up
# ~/.aws/credentials, creates a local venv, and wires an `aws-sso-sync`
# command into ~/.local/bin.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$REPO_DIR/.venv"
BIN_DIR="$HOME/.local/bin"
WRAPPER="$BIN_DIR/aws-sso-sync"

echo "== aws-sso-sync installer =="
echo "Repo: $REPO_DIR"
echo

if ! command -v python3 >/dev/null 2>&1; then
    echo "❌ No se encontró python3. Instálalo (Python >= 3.9) y vuelve a correr este script."
    exit 1
fi

if ! command -v aws >/dev/null 2>&1; then
    echo "❌ No se encontró el AWS CLI en el PATH."
    echo "   Instálalo: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
    exit 1
fi

AWS_VERSION_OUTPUT="$(aws --version 2>&1 || true)"
if [[ "$AWS_VERSION_OUTPUT" != *"aws-cli/2"* ]]; then
    echo "❌ Se requiere AWS CLI v2 (detectado: $AWS_VERSION_OUTPUT)."
    echo "   'aws configure export-credentials' no existe en AWS CLI v1."
    echo "   Instala/actualiza: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
    exit 1
fi
echo "✅ AWS CLI v2 detectado: $AWS_VERSION_OUTPUT"

CREDS_FILE="$HOME/.aws/credentials"
if [ -f "$CREDS_FILE" ]; then
    BACKUP_FILE="${CREDS_FILE}.backup-$(date +%Y%m%d%H%M%S)"
    cp "$CREDS_FILE" "$BACKUP_FILE"
    echo "✅ Backup de credentials existente: $BACKUP_FILE"
fi

echo
echo "Instalando en $VENV_DIR ..."
python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --upgrade pip --quiet
"$VENV_DIR/bin/pip" install -e "$REPO_DIR" --quiet
echo "✅ Paquete instalado (modo editable)."

mkdir -p "$BIN_DIR"
cat > "$WRAPPER" <<EOF
#!/usr/bin/env bash
export AWS_SSO_SYNC_HOME="$REPO_DIR"
exec "$VENV_DIR/bin/aws-sso-sync" "\$@"
EOF
chmod +x "$WRAPPER"
echo "✅ Comando instalado en $WRAPPER"

echo
case ":$PATH:" in
    *":$BIN_DIR:"*)
        echo "✅ $BIN_DIR ya está en tu PATH."
        ;;
    *)
        SHELL_RC="$HOME/.bashrc"
        case "${SHELL:-}" in
            */zsh) SHELL_RC="$HOME/.zshrc" ;;
        esac
        echo "⚠️  $BIN_DIR no está en tu PATH."
        echo "   Agrega esta línea a $SHELL_RC (o al rc de tu shell) y abre una terminal nueva:"
        echo
        echo "   export PATH=\"\$HOME/.local/bin:\$PATH\""
        echo
        ;;
esac

echo "Listo. Corre 'aws-sso-sync' para empezar."
