#!/usr/bin/env bash
set -euo pipefail
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
. "$root/packaging/release/app.conf"
work=$(mktemp -d)
trap 'rm -rf -- "$work"' EXIT
mkdir -p "$work/app/usr/bin" "$work/app/usr/share/$PAYLOAD_DIR"
touch "$work/app/usr/share/$PAYLOAD_DIR/game.toml"
cat > "$work/app/usr/bin/$EXE_NAME" <<'RUNTIME'
#!/bin/sh
test "$RECOMP_UI_BUILTIN_FILE_PICKER" = 1
test "$#" = 0
echo 'Built-in picker enabled without launch arguments'
RUNTIME
chmod +x "$work/app/usr/bin/$EXE_NAME"
sed -e 's|@VERSION@|test|g' -e "s|@APP_NAME@|$APP_NAME|g" \
    -e "s|@EXE_NAME@|$EXE_NAME|g" -e "s|@PAYLOAD_DIR@|$PAYLOAD_DIR|g" \
    -e "s|@ENV_PREFIX@|$ENV_PREFIX|g" -e "s|@ARTIFACT_NAME@|$ARTIFACT_NAME|g" \
    "$root/packaging/linux/AppRun" > "$work/app/AppRun"
env -u RECOMP_UI_BUILTIN_FILE_PICKER APPDIR="$work/app" \
    "${ENV_PREFIX}_DATA_DIR=$work/data" sh "$work/app/AppRun"
