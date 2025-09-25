#!/bin/bash
#
# Starts llama.cpp server with the provided model file.
#
# Download gguf model first (eg with download_llm.sh).
# Then start server:
# ./start_llama_server.sh models/llms/LFM2-350M-Q4_K_M.gguf


# set model file
MODEL=$1

if [ -z "$MODEL" ]; then
  echo "No model file specified. Please specify gguf file to use."
  exit 1
fi
if [ ! -f "$MODEL" ]; then
  echo "Model file not found: $MODEL"
  exit 1
fi

# find llama-server binary path
LLAMA_SERVER=$(which llama-server 2>/dev/null)
if [ -z "$LLAMA_SERVER" ]; then
  echo "llama-server not found in PATH. Please install llama.cpp or add it to PATH."
  exit 1
fi

# start server
# note: settings mostly optimized for Raspberry Pi 5
nice -n 10 \
  "$LLAMA_SERVER" -m $MODEL \
  --cache-type-k f16 --cache-type-v f16 \
  -c 1024 \
  --threads 2 \
  --batch-size 16 \
  --ubatch-size 8 \
  --port 8080


