#!/bin/sh
set -eu

app_path="$HOME/Applications/Agent Context Trace Opener.app"
bundle_id='org.agent-context-trace.opener'
registrar='/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister'
if [ ! -e "$app_path" ]; then exit 0; fi
existing_id=$(/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "$app_path/Contents/Info.plist" 2>/dev/null || true)
if [ "$existing_id" != "$bundle_id" ]; then
    printf '%s\n' '同名应用不是本工具，未删除。' >&2
    exit 1
fi
"$registrar" -u "$app_path"
rm -rf "$app_path"
printf '已卸载：%s\n' "$app_path"
