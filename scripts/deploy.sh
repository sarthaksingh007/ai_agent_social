#!/usr/bin/env bash
# Release deploy: the full stack plus the public Cloudflare tunnel.
#
# Fails fast with a readable message when the tunnel credentials are missing,
# rather than letting Docker bind-mount a directory over credentials.json and
# leaving cloudflared to crash-loop with a confusing parse error.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

for file in "$root/cloudflared/credentials.json" "$root/cloudflared/config.yml"; do
    if [ ! -f "$file" ]; then
        echo "Missing $file" >&2
        echo >&2
        echo "Release mode needs a Cloudflare tunnel. Set one up with:" >&2
        echo "  cloudflared tunnel login" >&2
        echo "  cloudflared tunnel create <name>" >&2
        echo "  cloudflared tunnel route dns <name> <hostname>" >&2
        echo "  cp ~/.cloudflared/<uuid>.json cloudflared/credentials.json" >&2
        echo "  cp cloudflared/config.example.yml cloudflared/config.yml  # then fill it in" >&2
        echo >&2
        echo "For local work you do not need any of this — just run:" >&2
        echo "  docker compose up -d" >&2
        exit 1
    fi
done

exec docker compose --project-directory "$root" \
    -f "$root/docker-compose.yml" \
    -f "$root/docker-compose.prod.yml" \
    up --build -d "$@"
