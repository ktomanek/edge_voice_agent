#!/bin/bash
llama-server \
    -m /root/dev/edge_voice_agent/models/llms/LFM2-1.2B-Q4_0.gguf \
    --port 8080 > /var/log/llama-server.log 2>&1 &
