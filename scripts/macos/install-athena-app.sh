#!/usr/bin/env bash
# Install the thin ATHENA Dock launcher (M-E4).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SOURCE_APP="$REPO_ROOT/packaging/macos/ATHENA.app"
DESTINATION="$HOME/Applications/ATHENA.app"
REVEAL=true

usage() {
  cat <<'EOF'
Install ATHENA.app into ~/Applications.

Usage:
  ./install-athena-app
  ./install-athena-app --destination "/Applications/ATHENA.app"
  ./install-athena-app --no-reveal

The app stores only the repository path. Secrets remain in the repo's .env.
EOF
}

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --destination)
      [[ "$#" -ge 2 ]] || { echo "ERROR: --destination needs a path" >&2; exit 2; }
      DESTINATION="$2"
      shift 2
      ;;
    --no-reveal)
      REVEAL=false
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "ERROR: ATHENA.app installer requires macOS." >&2
  exit 1
fi
if [[ ! -f "$SOURCE_APP/Contents/Info.plist" ]]; then
  echo "ERROR: launcher template missing: $SOURCE_APP" >&2
  exit 1
fi
if [[ ! -x "$REPO_ROOT/athena-serve" ]]; then
  echo "ERROR: athena-serve is not executable: $REPO_ROOT/athena-serve" >&2
  exit 1
fi

mkdir -p "$(dirname "$DESTINATION")"
/usr/bin/ditto "$SOURCE_APP" "$DESTINATION"
chmod +x "$DESTINATION/Contents/MacOS/ATHENA"
printf '%s\n' "$REPO_ROOT" >"$DESTINATION/Contents/Resources/repo-root"

/usr/bin/plutil -lint "$DESTINATION/Contents/Info.plist" >/dev/null
if command -v codesign >/dev/null 2>&1; then
  /usr/bin/codesign --force --deep --sign - "$DESTINATION" >/dev/null 2>&1
fi
/usr/bin/touch "$DESTINATION"

echo "Installed: $DESTINATION"
echo "Repository: $REPO_ROOT"
echo
echo "Next:"
echo "  1. Open ATHENA from ~/Applications (or your chosen destination)."
echo "  2. Drag ATHENA.app to the Dock."
echo "  3. Click it anytime: existing server opens immediately; otherwise it starts with cycles."
echo
echo "Logs: $REPO_ROOT/artifacts/logs/athena-serve.log"

if [[ "$REVEAL" == true ]]; then
  /usr/bin/open -R "$DESTINATION"
fi
