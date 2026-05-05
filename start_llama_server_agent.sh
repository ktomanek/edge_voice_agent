#!/bin/bash
llama-server \
    -m /root/dev/edge_voice_agent/models/llms/LFM2.5-1.2B-Instruct-Q4_K_M.gguf \
    --port 8080 > /var/log/llama-server.log 2>&1 &
