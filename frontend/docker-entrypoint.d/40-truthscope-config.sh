#!/bin/sh
set -eu

: "${API_BASE_URL:?API_BASE_URL is required}"
: "${OAUTH_REDIRECT_URL:?OAUTH_REDIRECT_URL is required}"
: "${SUPABASE_URL:?SUPABASE_URL is required}"
: "${SUPABASE_PUBLISHABLE_KEY:?SUPABASE_PUBLISHABLE_KEY is required}"

validate_url() {
    variable_name="$1"
    variable_value="$2"
    if ! printf '%s' "$variable_value" \
        | grep -Eq '^https?://[A-Za-z0-9._~:/?#@!$&()*+,;=%-]+$'; then
        echo "$variable_name must be a safe HTTP(S) URL." >&2
        exit 1
    fi
}

validate_url "API_BASE_URL" "$API_BASE_URL"
validate_url "OAUTH_REDIRECT_URL" "$OAUTH_REDIRECT_URL"
validate_url "SUPABASE_URL" "$SUPABASE_URL"

if ! printf '%s' "$SUPABASE_PUBLISHABLE_KEY" | grep -Eq '^[A-Za-z0-9._-]+$'; then
    echo "SUPABASE_PUBLISHABLE_KEY contains unsupported characters." >&2
    exit 1
fi

envsubst \
    '${API_BASE_URL} ${OAUTH_REDIRECT_URL} ${SUPABASE_URL} ${SUPABASE_PUBLISHABLE_KEY}' \
    < /opt/truthscope/config.template.js \
    > /tmp/truthscope-config.js
