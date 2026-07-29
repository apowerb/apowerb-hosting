#!/usr/bin/env bash
# Remplit ENCRYPT_KEY et TEST_TOKEN dans `.env` s'ils sont vides.
#
# Ne remplace JAMAIS une valeur deja posee : regenerer ENCRYPT_KEY rendrait
# illisibles tous les jetons d'integration deja chiffres en base.

set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
    echo "Aucun .env — copiez .env.example d'abord :  cp .env.example .env" >&2
    exit 1
fi

# Cle Fernet = 32 octets aleatoires en base64 url-safe. `openssl` suffit, pas
# besoin d'un interpreteur Python sur la machine hote.
generer_cle_fernet() {
    openssl rand -base64 32 | tr '+/' '-_'
}

remplir_si_vide() {
    local cle="$1" valeur="$2"
    if grep -qE "^${cle}=.+$" .env; then
        echo "  ${cle} : deja renseignee, laissee telle quelle"
        return
    fi
    # Portable macOS/Linux : `sed -i` n'a pas la meme signature sur les deux.
    local tmp
    tmp="$(mktemp)"
    sed "s|^${cle}=.*|${cle}=${valeur}|" .env > "$tmp" && mv "$tmp" .env
    echo "  ${cle} : generee"
}

echo "Generation des secrets manquants dans .env"
remplir_si_vide ENCRYPT_KEY "$(generer_cle_fernet)"
remplir_si_vide TEST_TOKEN "$(openssl rand -hex 24)"

echo
echo "Pret. Lancez :  docker compose up -d --build"
