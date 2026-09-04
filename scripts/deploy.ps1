# Release deploy: the full stack plus the public Cloudflare tunnel.
#
# Fails fast with a readable message when the tunnel credentials are missing,
# rather than letting Docker bind-mount a directory over credentials.json and
# leaving cloudflared to crash-loop with a confusing parse error.
$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$creds = Join-Path $root 'cloudflared\credentials.json'
$conf = Join-Path $root 'cloudflared\config.yml'

foreach ($file in @($creds, $conf)) {
    if (-not (Test-Path $file -PathType Leaf)) {
        Write-Host "Missing $file" -ForegroundColor Red
        Write-Host ''
        Write-Host 'Release mode needs a Cloudflare tunnel. Set one up with:' -ForegroundColor Yellow
        Write-Host '  cloudflared tunnel login'
        Write-Host '  cloudflared tunnel create <name>'
        Write-Host '  cloudflared tunnel route dns <name> <hostname>'
        Write-Host '  copy ~/.cloudflared/<uuid>.json to cloudflared/credentials.json'
        Write-Host '  copy cloudflared/config.example.yml to cloudflared/config.yml and fill it in'
        Write-Host ''
        Write-Host 'For local work you do not need any of this — just run:' -ForegroundColor Cyan
        Write-Host '  docker compose up -d'
        exit 1
    }
}

docker compose --project-directory $root `
    -f (Join-Path $root 'docker-compose.yml') `
    -f (Join-Path $root 'docker-compose.prod.yml') `
    up --build -d @args
