#!/bin/sh
# Runs inside the ollama container on every start.
# Idempotent: only pulls / builds if missing.
set -eu

BASE_MODEL="${BASE_MODEL:-qwen3.5:0.8b}"
CUSTOM_MODEL="${CUSTOM_MODEL:-qwen3.5-64k:0.8b}"
NUM_CTX="${NUM_CTX:-64000}"
OLLAMA_HOST_URL="http://127.0.0.1:11434"

# Start the ollama server in the background.
echo "[init] starting ollama server..."
/bin/ollama serve &
OLLAMA_PID=$!

# Wait for the API to come up (max ~60s).
echo "[init] waiting for ollama API..."
i=0
until ollama list >/dev/null 2>&1; do
    i=$((i + 1))
    if [ "$i" -gt 60 ]; then
        echo "[init] ollama failed to start within 60s" >&2
        exit 1
    fi
    sleep 1
done
echo "[init] ollama is up."

# Pull base model if absent.
if ollama list | awk '{print $1}' | grep -qx "$BASE_MODEL"; then
    echo "[init] base model '$BASE_MODEL' already present."
else
    echo "[init] pulling base model '$BASE_MODEL'..."
    ollama pull "$BASE_MODEL"
fi

# Build the 64k-context variant if absent.
if ollama list | awk '{print $1}' | grep -qx "$CUSTOM_MODEL"; then
    echo "[init] custom model '$CUSTOM_MODEL' already present."
else
    echo "[init] creating custom model '$CUSTOM_MODEL' with num_ctx=$NUM_CTX..."
    MODELFILE="$(mktemp)"
    cat > "$MODELFILE" <<EOF
FROM $BASE_MODEL
PARAMETER num_ctx $NUM_CTX
EOF
    ollama create "$CUSTOM_MODEL" -f "$MODELFILE"
    rm -f "$MODELFILE"
fi

echo "[init] ready. handing off to ollama server (pid $OLLAMA_PID)."
# Wait on the server so the container's lifecycle is tied to it.
wait "$OLLAMA_PID"
