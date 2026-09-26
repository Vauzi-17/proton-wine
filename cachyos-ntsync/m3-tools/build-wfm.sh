#!/bin/sh
# Builds Files (programs/files of the patched Wine tree) as a standalone wfm.exe, to replace
# the Winlator File Manager in a container: C:\windows\system32\wfm.exe (keep a copy of the old one).
#
#   build-wfm.sh <patched wine source> <arch: x86_64 or arm64ec> <output.exe>
#
# Needs llvm-mingw (https://github.com/mstorsjo/llvm-mingw) in PATH.
set -e
src="$1/programs/files"
arch="$2"
out="$3"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

"$arch-w64-mingw32-windres" -I"$src" -i "$src/files.rc" -o "$tmp/files.res.o"
"$arch-w64-mingw32-clang" -O2 -std=gnu11 -DUNICODE -D_UNICODE -DCOBJMACROS -D_WIN32_WINNT=0x0601 \
    -Wall -Wno-missing-braces -Wno-unused-function -I"$src" \
    "$src"/content_view.c "$src"/file_actions.c "$src"/file_node.c "$src"/header.c "$src"/icons.c \
    "$src"/input_dialog.c "$src"/iso_image.c "$src"/main.c "$src"/material.c "$src"/treeview.c \
    "$tmp/files.res.o" -o "$out" -mwindows -s \
    -lcomctl32 -lshell32 -lole32 -luuid -lgdi32 -luser32 -ladvapi32
echo "$out"
