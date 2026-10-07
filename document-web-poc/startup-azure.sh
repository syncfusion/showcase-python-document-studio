#!/usr/bin/env bash
# Azure App Service's built-in Python/Linux stack only; not for local Windows use.
set -euo pipefail
cd "$(dirname "$0")"

# OS packages do not persist when App Service replaces the running instance.
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
  ca-certificates curl libfontconfig1 libfreetype6 fontconfig fonts-liberation \
  libicu-dev libssl-dev zlib1g libstdc++6 libgomp1

# /home is persistent on the built-in App Service stack. Keep the runtime here.
export DOTNET_ROOT=/home/document-poc-dotnet
export PATH="$DOTNET_ROOT:$PATH"
if [[ ! -x "$DOTNET_ROOT/dotnet" ]] || ! "$DOTNET_ROOT/dotnet" --list-runtimes | grep -q '^Microsoft.NETCore.App 10\.0\.'; then
  installer_path="$(mktemp /tmp/document-poc-dotnet-install.XXXXXX)"
  trap 'rm -f "$installer_path"' EXIT
  curl --fail --silent --show-error --location --retry 3 \
    https://dot.net/v1/dotnet-install.sh --output "$installer_path"
  bash "$installer_path" --channel 10.0 --runtime dotnet --architecture x64 \
    --install-dir "$DOTNET_ROOT" --no-path
  rm -f "$installer_path"
  trap - EXIT
fi

# Oryx activates the Python environment built from requirements.txt before this script.
dotnet --list-runtimes
exec python -m uvicorn app:app --host 0.0.0.0 --port 8000 --loop asyncio
