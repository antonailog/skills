#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
app_path="$HOME/Applications/Agent Context Trace Opener.app"
bundle_id='org.agent-context-trace.opener'
registrar='/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister'

# Refuse to overwrite an unrelated application with the same display name.
if [ -e "$app_path" ]; then
    existing_id=$(/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "$app_path/Contents/Info.plist" 2>/dev/null || true)
    if [ "$existing_id" != "$bundle_id" ]; then
        printf '%s\n' '同名应用不是本工具，未覆盖。' >&2
        exit 1
    fi
fi
stage_dir=$(mktemp -d "${TMPDIR:-/tmp}/agent-context-trace-opener.XXXXXX")
trap 'rm -rf "$stage_dir"' EXIT HUP INT TERM
stage_app="$stage_dir/Agent Context Trace Opener.app"
/usr/bin/osacompile -o "$stage_app" "$script_dir/opener.applescript"
plist="$stage_app/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Set :CFBundleIdentifier $bundle_id" "$plist" 2>/dev/null ||
    /usr/libexec/PlistBuddy -c "Add :CFBundleIdentifier string $bundle_id" "$plist"
/usr/libexec/PlistBuddy -c 'Add :CFBundleURLTypes array' "$plist"
/usr/libexec/PlistBuddy -c 'Add :CFBundleURLTypes:0 dict' "$plist"
/usr/libexec/PlistBuddy -c "Add :CFBundleURLTypes:0:CFBundleURLName string $bundle_id" "$plist"
/usr/libexec/PlistBuddy -c 'Add :CFBundleURLTypes:0:CFBundleURLSchemes array' "$plist"
/usr/libexec/PlistBuddy -c 'Add :CFBundleURLTypes:0:CFBundleURLSchemes:0 string agent-context-trace' "$plist"
mkdir -p "$HOME/Applications"
if [ -e "$app_path" ]; then mv "$app_path" "$stage_dir/previous.app"; fi
mv "$stage_app" "$app_path"
"$registrar" -f "$app_path"
printf '已安装：%s\n' "$app_path"
