#!/usr/bin/env bash
# Attach an episode's media to a GitHub Release.
#
# Why a release and not the repo: the video is ~15 MB per episode and git keeps
# every version forever, so ten episodes would be a ~150 MB repo that nobody can
# clone. Release assets are free, are not part of the clone, and get a permanent
# download URL that survives the sandbox being recycled.
#
# Usage: scripts/publish_release.sh <episode-dir> [tag]
set -u

EP_DIR="${1:?usage: publish_release.sh <episode-dir> [tag]}"
REPO="kongkeat938/ai-content-lab"
TAG="${2:-$(basename "$EP_DIR" | cut -d_ -f1)}"

if [ -z "${GH_TOKEN:-}" ] && [ -n "${KONGKEAT_GH_TOKEN:-}" ]; then
  export GH_TOKEN="$KONGKEAT_GH_TOKEN"
fi

mapfile -t FILES < <(ls "$EP_DIR"/*.mp4 "$EP_DIR"/*.mp3 2>/dev/null)
if [ ${#FILES[@]} -eq 0 ]; then
  echo "no .mp4/.mp3 in $EP_DIR — build the episode first" >&2
  exit 1
fi

echo "tag:  $TAG"
echo "repo: $REPO"
printf 'file: %s\n' "${FILES[@]}"

# Name the assets after the tag so several episodes can coexist and the URL
# reads sensibly: releases/download/<tag>/<tag>.mp4
staged=()
tmp="$(mktemp -d)"
for f in "${FILES[@]}"; do
  ext="${f##*.}"
  cp "$f" "$tmp/$TAG.$ext"
  staged+=("$tmp/$TAG.$ext")
done

if gh release view "$TAG" --repo "$REPO" >/dev/null 2>&1; then
  echo "release $TAG exists — uploading (clobbering same names)"
  gh release upload "$TAG" "${staged[@]}" --repo "$REPO" --clobber
else
  gh release create "$TAG" "${staged[@]}" --repo "$REPO" \
    --title "$TAG" --notes "Media for $TAG. Regenerable from scripts/."
fi

rm -rf "$tmp"

echo
echo "download URLs:"
for f in "${staged[@]}"; do
  echo "  https://github.com/$REPO/releases/download/$TAG/$(basename "$f")"
done
