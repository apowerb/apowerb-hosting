#!/usr/bin/env bash
# Fills ENCRYPT_KEY and TEST_TOKEN in `.env` when they are empty.
#
# NEVER replaces a value that is already set: regenerating ENCRYPT_KEY would
# make every integration token already encrypted in the database unreadable.

set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
    echo "No .env — copy the template first:  cp .env.example .env" >&2
    exit 1
fi

# A Fernet key is 32 random bytes in url-safe base64. `openssl` is enough, no
# Python interpreter needed on the host.
generate_fernet_key() {
    openssl rand -base64 32 | tr '+/' '-_'
}

fill_if_empty() {
    local key="$1" value="$2"
    if grep -qE "^${key}=.+$" .env; then
        echo "  ${key}: already set, left as is"
        return
    fi
    # Portable across macOS and Linux: `sed -i` does not take the same
    # arguments on both.
    local tmp
    tmp="$(mktemp)"
    sed "s|^${key}=.*|${key}=${value}|" .env > "$tmp" && mv "$tmp" .env
    echo "  ${key}: generated"
}

echo "Generating the missing secrets in .env"
fill_if_empty ENCRYPT_KEY "$(generate_fernet_key)"
fill_if_empty TEST_TOKEN "$(openssl rand -hex 24)"

echo
echo "Ready. Start with:  docker compose -f docker-compose/docker-compose.yml --env-file .env up -d"
