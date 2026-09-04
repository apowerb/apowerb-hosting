#!/usr/bin/env bash
# Prove a deployment actually works, from outside, in ten seconds.
#
#   scripts/check-deployment.sh https://your-host.example
#   scripts/check-deployment.sh http://localhost:3000
#
# Why this exists: a container that is "up" proves nothing, and neither does a
# page that renders. Twice -- 19/08 and 04/09 -- a deployment of this stack came
# back with the interface updated and the backend left on its previous image.
# Both times the control panel rendered at /admin and answered 404 behind it.
# Nothing was down, nothing logged an error, and the deployment looked fine.
#
# What makes this check able to fail: every assertion carries a witness. A
# positive one (a route that must exist) and a negative one (a path that cannot
# exist, and must answer 404). Without the negative witness, a server answering
# 404 to everything -- unreachable, misrouted, behind the wrong proxy -- would
# sail through the "route is absent" branch of every test.

set -uo pipefail

BASE="${1:-}"
if [ -z "$BASE" ]; then
  echo "usage: $0 <base-url>" >&2; exit 2
fi
BASE="${BASE%/}"
FAIL=0

code() { curl -sL -o /dev/null -w "%{http_code}" --max-time 20 "$BASE$1" 2>/dev/null; }

check() { # <path> <expected> <what it proves>
  local got; got=$(code "$1")
  if [ "$got" = "$2" ]; then
    printf '  ok    %-34s %s\n' "$1" "$got"
  else
    printf '  FAIL  %-34s %s (expected %s) -- %s\n' "$1" "$got" "$2" "$3"
    FAIL=1
  fi
}

echo "checking $BASE"
echo
echo "witnesses"
# A backend is answering, and it is the backend -- not a proxy inventing errors.
check /api/agents 401 "no backend behind the interface, or it is not answering"
# Nothing serves this path. If it answers anything but 404, every 404 below is
# meaningless and this whole check is blind.
check "/api/admin/nope-$$-$RANDOM" 404 "this host answers non-404 to a path that cannot exist: the checks below cannot be trusted"

echo
echo "the frontend/backend pair"
# The frontend ships the control panel screen; the backend must serve its API.
# 404 here with /admin at 200 below is the exact partial-redeploy signature:
# the interface moved, the backend did not.
check /api/admin/users 401 "PARTIAL DEPLOYMENT: the backend is older than the interface (it does not serve /api/admin). Redeploy the BACKEND service by hand."
check /admin 200 "the interface does not ship the control panel screen"

echo
echo "the pages a user lands on"
check / 200 "the site does not serve"
check /login 200 "nobody can sign in"
check /agents 200 "the agent list does not serve"
check /chat 200 "the chat screen does not serve"

echo
if [ "$FAIL" -eq 0 ]; then
  echo "PASS -- the pair is consistent and the entry points serve."
  echo "Not proven here: an actual model answering. That needs DEFAULT_LLM_MODEL"
  echo "and DEFAULT_LLM_API_KEY set, and a signed-in conversation."
else
  echo "FAIL -- see the lines above. A deployment is not done until this passes."
fi
exit "$FAIL"
