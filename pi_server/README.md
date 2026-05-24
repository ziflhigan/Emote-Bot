# VLM Stack (Ollama + FastAPI) (OUTDATED INFO WITH NEW CODE)

CPU-only, multi-arch (x86_64 + arm64). Tested target: Raspberry Pi 5 (8GB).

## Layout

```
.
├── Dockerfile                    # FastAPI service image
├── docker-compose.yml            # Production: only FastAPI port exposed
├── docker-compose.testing.yml    # Override: also publishes Ollama port
├── requirements.txt
├── app/
│   └── main.py                   # Your FastAPI app (replace placeholder)
└── scripts/
    └── ollama-init.sh            # First-run model pull + 64k-ctx variant
```

## First run

```bash
docker compose up -d --build
```

Initial boot pulls `qwen3.5:0.8b` and creates `qwen3.5-64k:0.8b` (num_ctx=64000).
This can take a while on first run (network + disk); subsequent boots skip both
because the named volume `ollama_models` persists everything.

Watch progress:

```bash
docker compose logs -f ollama
```

The `api` service waits on a healthcheck that confirms the custom model exists,
so it won't start serving 5xx errors during the initial pull.

## Testing mode (Ollama port exposed)

```bash
docker compose -f docker-compose.yml -f docker-compose.testing.yml up -d --build
```

Then from the host:

```bash
curl http://localhost:11434/api/tags
curl http://localhost:8000/health
```

## LAN access from other devices

The FastAPI service binds to `0.0.0.0:8000` on the host, so any device on the
same network can reach it at `http://<host-ip>:8000`.

Find the host IP:

- Linux/macOS: `ip -4 addr show | grep inet` or `ifconfig | grep inet`
- Raspberry Pi: `hostname -I`
- Windows: `ipconfig`

If you can't reach it from another device, the firewall is usually the cause:

- **Raspberry Pi OS / Debian / Ubuntu** (if `ufw` is active):
  ```bash
  sudo ufw allow 8000/tcp
  ```
- **Fedora / RHEL**:
  ```bash
  sudo firewall-cmd --add-port=8000/tcp --permanent && sudo firewall-cmd --reload
  ```
- **macOS**: System Settings → Network → Firewall → allow Docker.
- **Windows**: Windows Defender Firewall → Inbound Rules → New Rule → TCP 8000.

For a stable address across reboots, give the Pi a DHCP reservation in your
router, or use mDNS — Raspberry Pi OS publishes `<hostname>.local` by default,
so `http://raspberrypi.local:8000` typically just works from any device with
mDNS (macOS, iOS, most Linux, Windows 10+).

## Persistence

- `ollama_models` (named volume): stores pulled models + custom variants.
  Survives `docker compose down`. Wipe with `docker compose down -v`.
- `./app` is bind-mounted read-only into the api container so you can edit
  `main.py` and just `docker compose restart api` to pick up changes.

## Platform notes

Both `ollama/ollama:latest` and `python:3.12-slim` are multi-arch manifests, so
the same compose file runs on x86_64 dev machines and arm64 (Pi 5) without
modification. Docker pulls the right variant automatically. No `platform:` key
needed.

CPU-only inference on a Pi 5 with a sub-1B model should be usable but not fast;
expect a few seconds per short generation. If latency matters, keep prompts
short — note that `num_ctx=64000` allocates the KV cache up-front, which costs
RAM regardless of actual prompt length, so you may want to lower it if the Pi
starts swapping.

## Commands

```bash
# Up / down
docker compose up -d
docker compose down              # keep volumes
docker compose down -v           # wipe models too

# Logs
docker compose logs -f api
docker compose logs -f ollama

# Re-pull / rebuild custom model (e.g. after changing NUM_CTX)
docker compose exec ollama ollama rm qwen3.5-64k:0.8b
docker compose restart ollama
```
