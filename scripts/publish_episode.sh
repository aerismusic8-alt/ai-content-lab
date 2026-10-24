#!/usr/bin/env bash
# One command from finished files to a live YouTube post.
#
#   scripts/publish_episode.sh episodes/ep02_mattanaphatha [privacy]
#
# Does, in order:
#   1. rebuild the channel JSON so the API matches the files
#   2. attach the video and audio to a GitHub Release (permanent URLs)
#   3. upload to YouTube using the text from the channel
#   4. record the URL back on the channel
#
# Needs a token from `scripts/yt_auth.py` (once, with a browser).
set -u

EP_DIR="${1:?usage: publish_episode.sh <episode-dir> [private|unlisted|public]}"
PRIVACY="${2:-private}"
TAG="$(basename "$EP_DIR" | cut -d_ -f1)"

echo "== 1/4 channel =="
python3 scripts/build_api.py || exit 1

echo "== 2/4 release $TAG =="
scripts/publish_release.sh "$EP_DIR" "$TAG" || exit 1

echo "== 3/4 upload to YouTube ($PRIVACY) =="
python3 scripts/publish_youtube.py "$TAG" --privacy "$PRIVACY" --report || exit 1

echo "== 4/4 done =="
echo "The video is $PRIVACY. Review it in YouTube Studio before making it public."
