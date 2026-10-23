#!/bin/bash
# Tesler installer for macOS.
#   curl -fsSL https://raw.githubusercontent.com/llamaboi55/DragShift/main/install-mac.sh | bash
# Downloads the right build for this Mac from the latest GitHub release, installs it to
# /Applications and opens it. Files fetched by curl aren't marked "downloaded from the
# internet", so macOS doesn't show the "could not verify" warning. Read it first if you like —
# it's short.
set -euo pipefail

REPO="llamaboi55/DragShift"
case "$(uname -m)" in
  arm64) ASSET="Tesler-mac-apple-silicon.dmg" ;;
  *)     ASSET="Tesler-mac-intel.dmg" ;;
esac
URL="https://github.com/$REPO/releases/latest/download/$ASSET"
TMP="$(mktemp -d)"
trap 'hdiutil detach "$TMP/mnt" -quiet 2>/dev/null || true; rm -rf "$TMP"' EXIT

echo "→ Downloading $ASSET"
curl -fL --progress-bar "$URL" -o "$TMP/Tesler.dmg"

echo "→ Installing to /Applications"
hdiutil attach "$TMP/Tesler.dmg" -mountpoint "$TMP/mnt" -nobrowse -quiet
osascript -e 'quit app "Tesler"' 2>/dev/null || true
pkill -x Tesler 2>/dev/null || true
DEST="/Applications/Tesler.app"
if [ -w /Applications ]; then
  rm -rf "$DEST"; ditto "$TMP/mnt/Tesler.app" "$DEST"
else
  sudo rm -rf "$DEST"; sudo ditto "$TMP/mnt/Tesler.app" "$DEST"
fi
xattr -dr com.apple.quarantine "$DEST" 2>/dev/null || true

echo "→ Opening Tesler (look for it in the menu bar)"
open "$DEST"
echo "✓ Done. Drag any file in Finder and press Shift."
