#!/bin/bash
#
# Starts llama.cpp server with the provided model file.
#
# Download gguf model first.
# Eg:
# wget https://huggingface.co/LiquidAI/LFM2-350M-GGUF/resolve/main/LFM2-350M-Q4_K_M.gguf
# Then start server:
# ./start_llama_server.sh LFM2-350M-Q4_K_M.gguf


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

# start server
nice -n 10 \
  llama-server -m $MODEL \
  -c 4096 --threads 2 --batch-size 1 \
  --port 8080


