#!/usr/bin/env bash
set -euo pipefail
release="${1:?Release tag required}"
[[ "$release" =~ ^[a-z0-9-]+$ ]] || { echo 'Invalid release tag'; exit 2; }
release_dir="/opt/exitforge/releases/$release"
[[ "$(realpath "$release_dir")" == "$release_dir" ]] || exit 2
[[ -f "$release_dir/Dockerfile" ]] || exit 2
[[ -s /opt/exitforge/secrets/baseten_api_key ]] || { echo 'Install the authorized private Baseten key first'; exit 2; }
image="exitforge:$release"
tunnel_image='cloudflare/cloudflared@sha256:9b49eed8f62806d5d45ddf59ecefb5710429598ea6d3fcccd2af938f621b2b07'
fixed_origin=/opt/exitforge/runtime/fixed-origin.txt
tunnel_token=/opt/exitforge/secrets/cloudflared_token
if [[ -e "$fixed_origin" ]]; then
  [[ -s "$tunnel_token" ]] || { echo 'Fixed domain requires its dedicated tunnel token'; exit 2; }
  python3 - "$release_dir" <<'PY'
import sys
from pathlib import Path
sys.path.insert(0,str(Path(sys.argv[1])/'deploy'))
from watch_origin import choose_origin
choose_origin(Path('/opt/exitforge/runtime/fixed-origin.txt'),'')
PY
  if docker container inspect exitforge-tunnel >/dev/null 2>&1; then
    [[ "$(docker inspect --format '{{index .Config.Labels "exitforge-tunnel-mode"}}' exitforge-tunnel)" == 'fixed' ]] || { echo 'Run the controlled domain cutover before fixed-mode deployment'; exit 2; }
  fi
fi

for name in exitforge-web exitforge-tunnel; do
  if docker container inspect "$name" >/dev/null 2>&1; then
    [[ "$(docker inspect --format '{{index .Config.Labels "managed-by"}}' "$name")" == 'exitforge' ]] || { echo 'Container name is owned elsewhere'; exit 2; }
  fi
done
docker build --pull=false -t "$image" "$release_dir"
docker network inspect exitforge-preview >/dev/null 2>&1 || docker network create --label managed-by=exitforge exitforge-preview >/dev/null
[[ "$(docker network inspect --format '{{index .Labels "managed-by"}}' exitforge-preview)" == 'exitforge' ]] || exit 2
install -d -m 0755 /opt/exitforge/runtime
install -d -m 0700 /opt/exitforge/data
python3 -c "import os; os.chown('/opt/exitforge/data',10001,10001)"
ln -sfn "$release_dir" /opt/exitforge/current
for name in exitforge-web; do
  if docker container inspect "$name" >/dev/null 2>&1; then docker stop "$name" >/dev/null; docker rm "$name" >/dev/null; fi
done
docker run -d --name exitforge-web --label managed-by=exitforge --label "release=$release" \
  --restart unless-stopped --network exitforge-preview -p 127.0.0.1:8766:8000 \
  --read-only --tmpfs /tmp:rw,noexec,nosuid,size=32m --cap-drop ALL --security-opt no-new-privileges:true \
  --memory 1g --memory-swap 1g --cpus 1 --pids-limit 128 \
  --log-opt max-size=5m --log-opt max-file=2 \
  -e "EXITFORGE_RELEASE=$release" -e EXITFORGE_PUBLIC_ORIGIN_FILE=/run/exitforge/public-origin.txt \
  -e EXITFORGE_PUBLIC_AI=1 -e EXITFORGE_ALLOW_CLOUD=1 -e EXITFORGE_TRUST_TUNNEL=1 \
  -e EXITFORGE_AI_LEDGER=/var/lib/exitforge/allowance.sqlite3 \
  -e EXITFORGE_AI_ALLOWANCE_MICROUSD=750000 \
  -e EXITFORGE_BASETEN_KEY_FILE=/run/secrets/baseten_api_key \
  --mount type=bind,src=/opt/exitforge/runtime,dst=/run/exitforge,readonly \
  --mount type=bind,src=/opt/exitforge/data,dst=/var/lib/exitforge \
  --mount type=bind,src=/opt/exitforge/secrets/baseten_api_key,dst=/run/secrets/baseten_api_key,readonly "$image" >/dev/null
for attempt in $(seq 1 30); do
  if python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8766/healthz',timeout=2).read()" 2>/dev/null; then break; fi
  sleep 1
done
python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8766/healthz',timeout=3).read()"
if ! docker container inspect exitforge-tunnel >/dev/null 2>&1; then
  tunnel_arguments=(tunnel --no-autoupdate --protocol http2 --url http://exitforge-web:8000)
  tunnel_mounts=()
  tunnel_mode=preview
  if [[ -e "$fixed_origin" ]]; then
    tunnel_mode=fixed
    tunnel_arguments=(tunnel --no-autoupdate --protocol http2 run --token-file /run/secrets/cloudflared_token)
    tunnel_mounts=(--mount type=bind,src="$tunnel_token",dst=/run/secrets/cloudflared_token,readonly)
  fi
  docker run -d --name exitforge-tunnel --label managed-by=exitforge --restart unless-stopped \
  --label "exitforge-tunnel-mode=$tunnel_mode" "${tunnel_mounts[@]}" \
  --network exitforge-preview --read-only --cap-drop ALL --security-opt no-new-privileges:true \
  --memory 256m --memory-swap 256m --cpus 0.25 --pids-limit 64 \
  --log-opt max-size=2m --log-opt max-file=2 \
    "$tunnel_image" "${tunnel_arguments[@]}" >/dev/null
else
  docker start exitforge-tunnel >/dev/null
fi
install -m 0644 "$release_dir/deploy/exitforge-origin-watch.service" /etc/systemd/system/exitforge-origin-watch.service
systemctl daemon-reload
systemctl enable --now exitforge-origin-watch.service
systemctl restart exitforge-origin-watch.service
for attempt in $(seq 1 40); do
  if [[ -s /opt/exitforge/runtime/public-origin.txt ]]; then
    python3 -c "import urllib.request; origin=open('/opt/exitforge/runtime/public-origin.txt').read().strip(); urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:8766/healthz',headers={'Host':origin.removeprefix('https://')}),timeout=3).read()" 2>/dev/null && break
  fi
  sleep 1
done
printf 'Release: %s\nOrigin: ' "$release"
cat /opt/exitforge/runtime/public-origin.txt
