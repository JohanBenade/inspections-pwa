#!/usr/bin/env bash
# api_deploy_add.sh v2 -- add/update ONE file on an EXISTING branch (no branch
# create, no PR create). Companion to api_deploy.sh for multi-file PRs:
# run api_deploy.sh once (creates branch + PR), then this for each extra file.
# v2: contents lookup HTTP code checked explicitly; sha parsed from JSON via
# python3 (top-level .sha only), not grep.
# USAGE: bash api_deploy_add.sh <repo> <local_file> <repo_path> <branch> "<msg>"
set -euo pipefail
TOKEN_FILE="${HOME}/.gh_deploy_token"
if [ "$#" -ne 5 ]; then
  echo "Usage: bash api_deploy_add.sh <repo> <local_file> <repo_path> <branch> \"<msg>\""; exit 1
fi
REPO="$1"; LOCAL_FILE="$2"; REPO_PATH="$3"; BRANCH="$4"; MESSAGE="$5"
API="https://api.github.com/repos/${REPO}"
[ -f "$TOKEN_FILE" ] || { echo "ERROR: no token at $TOKEN_FILE"; exit 1; }
[ -f "$LOCAL_FILE" ] || { echo "ERROR: no local file: $LOCAL_FILE"; exit 1; }
AUTH="Authorization: Bearer $(cat "$TOKEN_FILE")"
echo "== api_deploy_add == $REPO_PATH -> $BRANCH"
# 1. branch must exist
B_CODE="$(curl -s -o /dev/null -w "%{http_code}" -H "$AUTH" "${API}/git/refs/heads/${BRANCH}")"
[ "$B_CODE" = "200" ] || { echo "ERROR: branch '$BRANCH' not found (HTTP $B_CODE)."; exit 1; }
# 2. blob SHA on THAT branch: 200 = update mode, 404 = create mode, else = hard error
C_BODY="$(mktemp)"
C_CODE="$(curl -s -o "$C_BODY" -w "%{http_code}" -H "$AUTH" "${API}/contents/${REPO_PATH}?ref=${BRANCH}")"
if [ "$C_CODE" = "200" ]; then
  FILE_SHA="$(python3 -c 'import json,sys
d = json.load(open(sys.argv[1]))
print(d["sha"] if isinstance(d, dict) and "sha" in d else "")' "$C_BODY")"
  [ -n "$FILE_SHA" ] || { echo "ERROR: HTTP 200 but no top-level sha (path is a directory?)"; cat "$C_BODY"; rm -f "$C_BODY"; exit 1; }
  echo "[1/2] existing blob on branch: $FILE_SHA (update)"
elif [ "$C_CODE" = "404" ]; then
  FILE_SHA=""
  echo "[1/2] new file (create)"
else
  echo "ERROR: contents lookup failed (HTTP $C_CODE):"; cat "$C_BODY"; rm -f "$C_BODY"; exit 1
fi
rm -f "$C_BODY"
# 3. commit
CONTENT_B64="$(base64 < "$LOCAL_FILE" | tr -d '\n')"
PAYLOAD_FILE="$(mktemp)"
{
  printf '{'
  printf '"message":%s,' "$(printf '%s' "$MESSAGE" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))')"
  printf '"branch":"%s",' "$BRANCH"
  printf '"content":"%s"' "$CONTENT_B64"
  [ -n "$FILE_SHA" ] && printf ',"sha":"%s"' "$FILE_SHA"
  printf '}'
} > "$PAYLOAD_FILE"
PUT_CODE="$(curl -s -o /tmp/api_deploy_add.json -w "%{http_code}" -X PUT -H "$AUTH" -H "Content-Type: application/json" \
  --data-binary "@${PAYLOAD_FILE}" "${API}/contents/${REPO_PATH}")"
rm -f "$PAYLOAD_FILE"
if [ "$PUT_CODE" = "200" ] || [ "$PUT_CODE" = "201" ]; then echo "[2/2] committed (HTTP $PUT_CODE)"
else echo "ERROR: commit failed (HTTP $PUT_CODE):"; cat /tmp/api_deploy_add.json; exit 1; fi
