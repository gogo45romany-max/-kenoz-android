#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# KENOZ — build KENOZ-1.0.0.apk WITHOUT the Android SDK, Gradle or a full JDK.
#
# The normal (and supported) way to build is .github/workflows/build-apk.yml on
# GitHub Actions, which uses Gradle + the real Java sources in app/src/main.
# This script exists because some environments (including the one this project
# was first assembled in) can only reach the PyPI / npm / GitHub APIs: no
# dl.google.com, no Maven repositories, no Android SDK.
#
# Pipeline:
#   1. aapt2        compile + link res/manifest, pack assets/  -> base.apk
#   2. smali+dexlib assemble tools/local-apk/smali             -> classes.dex
#   3. python       add classes.dex to base.apk (4-byte aligned, stored)
#   4. node         write the APK Signature Scheme v2 block   -> APK
#   5. node/python  verify signature block, digests, manifest, zip
#
# Requirements: bash, python3, node >= 18, npm, pip, curl.
# Everything else is downloaded once into $KENOZ_APK_WORK (default
# ~/.cache/kenoz-local-apk).
#
# Usage:  tools/local-apk/build.sh [output-dir]     (default: dist/)
# ---------------------------------------------------------------------------
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
cd "$ROOT"

OUT_DIR=${1:-"$ROOT/dist"}
WORK=${KENOZ_APK_WORK:-"$HOME/.cache/kenoz-local-apk"}
TOOLS="$WORK/tools"
mkdir -p "$OUT_DIR" "$WORK" "$TOOLS"

PKG=com.kenoz.app
VERSION_NAME=1.0.0
VERSION_CODE=1
MIN_SDK=24
TARGET_SDK=35
P12="$ROOT/keystore/kenoz.p12"
P12_PASS=${KENOZ_KEYSTORE_PASSWORD:-kenoz2026}

say() { printf '\n\033[1m== %s\033[0m\n' "$*"; }

# ---------------------------------------------------------------------------
# 0. toolchain
# ---------------------------------------------------------------------------
if [ ! -x "$TOOLS/jdk/jdk4py/java-runtime/bin/java" ]; then
  say "fetching JDK runtime (pypi: jdk4py)"
  python3 -m pip install --quiet --no-warn-script-location \
    --target "$TOOLS/jdk" "jdk4py==17.0.9.2" >/dev/null
fi
JAVA="$TOOLS/jdk/jdk4py/java-runtime/bin/java"

if [ ! -x "$TOOLS/aaptjs/package/bin/x64/linux/aapt2" ]; then
  say "fetching aapt2 (npm: aaptjs3)"
  ( cd "$TOOLS" && npm pack --silent "aaptjs3@2.0.2" >/dev/null && \
    mkdir -p aaptjs && tar xzf aaptjs3-2.0.2.tgz -C aaptjs )
fi
AAPT2="$TOOLS/aaptjs/package/bin/x64/linux/aapt2"
chmod +x "$AAPT2"

if [ ! -f "$TOOLS/apktool/package/bin/apktool_2.4.1.jar" ]; then
  say "fetching apktool jar (npm: apktool-jar, contains smali + dexlib2)"
  ( cd "$TOOLS" && npm pack --silent "apktool-jar@2.4.1" >/dev/null && \
    mkdir -p apktool && tar xzf apktool-jar-2.4.1.tgz -C apktool )
fi
APKTOOL="$TOOLS/apktool/package/bin/apktool_2.4.1.jar"
[ -f "$APKTOOL" ] || { echo "apktool jar missing at $APKTOOL" >&2; exit 1; }

if ! python3 -c "import zipfile,sys; zipfile.ZipFile(sys.argv[1])" "$TOOLS/android.jar" 2>/dev/null; then
  say "fetching android.jar (github: Sable/android-platforms, API 35, ~27 MB)"
  rm -f "$TOOLS/android.jar"
  # Prefer the raw media type; fall back to the plain file URL.
  curl -sL --fail -H "Accept: application/vnd.github.raw" \
    ${GITHUB_TOKEN:+-H "Authorization: token $GITHUB_TOKEN"} \
    -o "$TOOLS/android.jar" \
    "https://api.github.com/repos/Sable/android-platforms/contents/android-35/android.jar?ref=master" \
    || curl -sL --fail -o "$TOOLS/android.jar" \
    "https://raw.githubusercontent.com/Sable/android-platforms/master/android-35/android.jar"
  python3 -c "import zipfile,sys; zipfile.ZipFile(sys.argv[1])" "$TOOLS/android.jar" \
    || { echo "android.jar download failed" >&2; exit 1; }
fi
ANDROID_JAR="$TOOLS/android.jar"

if [ ! -d "$ROOT/tools/local-apk/node_modules/node-forge" ]; then
  say "installing node-forge"
  ( cd "$ROOT/tools/local-apk" && npm install --silent --no-audit --no-fund >/dev/null )
fi

# ---------------------------------------------------------------------------
# 1. resources + manifest + assets
# ---------------------------------------------------------------------------
say "aapt2 compile"
"$AAPT2" compile --dir app/src/main/res -o "$WORK/res.zip"

say "aapt2 link (packs app/src/main/assets)"
python3 - "$ROOT" "$WORK" "$PKG" <<'PY'
import sys
root, work, pkg = sys.argv[1:4]
xml = open(f'{root}/app/src/main/AndroidManifest.xml', encoding='utf-8').read()
xml = xml.replace('<manifest xmlns:android="http://schemas.android.com/apk/res/android">',
                  '<manifest xmlns:android="http://schemas.android.com/apk/res/android" '
                  f'package="{pkg}">', 1)
assert 'package=' in xml
open(f'{work}/AndroidManifest.xml', 'w', encoding='utf-8').write(xml)
PY

"$AAPT2" link -o "$WORK/base.apk" \
  -I "$ANDROID_JAR" \
  --manifest "$WORK/AndroidManifest.xml" \
  -A app/src/main/assets \
  --min-sdk-version "$MIN_SDK" \
  --target-sdk-version "$TARGET_SDK" \
  --version-code "$VERSION_CODE" \
  --version-name "$VERSION_NAME" \
  "$WORK/res.zip"

# ---------------------------------------------------------------------------
# 2. dex
# ---------------------------------------------------------------------------
say "assembling smali -> classes.dex"
"$JAVA" -cp "$APKTOOL:$ROOT/tools/local-apk/classes" SmaliDriver \
  "$ROOT/tools/local-apk/smali" "$WORK/classes.dex" "$MIN_SDK"

say "verifying smali references + dex header"
python3 "$ROOT/tools/local-apk/verify_smali.py" \
  "$ROOT/tools/local-apk/smali" "$WORK/classes.dex" "$ANDROID_JAR"

say "round-trip check (baksmali)"
rm -rf "$WORK/baksmali-out"
"$JAVA" -cp "$APKTOOL:$ROOT/tools/local-apk/classes" BaksmaliDriver \
  "$WORK/classes.dex" "$WORK/baksmali-out" 2>&1 | tail -1

# ---------------------------------------------------------------------------
# 3. add classes.dex (uncompressed, 4-byte aligned)
# ---------------------------------------------------------------------------
say "adding classes.dex to the APK"
python3 - "$WORK" <<'PY'
import os, struct, sys, zipfile

work = sys.argv[1]
apk, dex = f'{work}/base.apk', f'{work}/classes.dex'

offset = os.path.getsize(apk) + 30 + len('classes.dex')
pad = (4 - offset % 4) % 4
if pad and pad < 4:
    pad += 4
extra = b'' if not pad else struct.pack('<HH', 0xffff, pad - 4) + b'\x00' * (pad - 4)

with zipfile.ZipFile(apk, 'a', zipfile.ZIP_STORED) as z:
    info = zipfile.ZipInfo('classes.dex', date_time=(2026, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_STORED
    info.extra = extra
    info.external_attr = 0o644 << 16
    z.writestr(info, open(dex, 'rb').read())

with zipfile.ZipFile(apk) as z:
    info = z.getinfo('classes.dex')
    with open(apk, 'rb') as f:
        f.seek(info.header_offset)
        head = f.read(30)
    nlen, elen = struct.unpack('<HH', head[26:30])
    data_off = info.header_offset + 30 + nlen + elen
print(f'classes.dex: {info.file_size} bytes, stored={info.compress_type == 0}, '
      f'data offset {data_off} (aligned: {data_off % 4 == 0})')
PY

# ---------------------------------------------------------------------------
# 4. sign (APK Signature Scheme v2)
# ---------------------------------------------------------------------------
say "signing (APK Signature Scheme v2, keystore/kenoz.p12)"
APK="$OUT_DIR/KENOZ-$VERSION_NAME.apk"
node tools/local-apk/sign_v2.mjs "$WORK/base.apk" "$APK" "$P12" "$P12_PASS"

# ---------------------------------------------------------------------------
# 5. verify
# ---------------------------------------------------------------------------
say "verifying signature + content digests"
node tools/local-apk/verify_apk.mjs "$APK" | tail -6

say "manifest / package check"
"$AAPT2" dump badging "$APK" 2>/dev/null | \
  grep -E "^(package|minSdkVersion|targetSdkVersion|application-label|launchable-activity)" || true

say "zip integrity"
python3 - "$APK" <<'PY'
import sys, zipfile
apk = sys.argv[1]
z = zipfile.ZipFile(apk)
print('entries:', len(z.namelist()), '| corrupt entry:', z.testzip())
PY

say "done -> $APK"
ls -lh "$APK"
sha256sum "$APK"
