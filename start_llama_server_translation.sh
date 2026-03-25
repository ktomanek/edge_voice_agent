#!/bin/bash
#
# Starts llama.cpp server optimized for single-turn translation (no context needed).
#
#   -c 1024              Context size limited to 1024 tokens. No conversation history
#                        needed for translation, so smaller = less memory, faster.
#   -np 1                Single parallel slot. Only one user, no concurrent requests.
#   -t N                 CPU threads for token generation (set to 4).
#   -tb N                CPU threads for prompt prefill/batch processing (set to 4).
#                        Both set to 4 intentionally for consistent performance.
#   --no-context-shift   Disables context shifting when full. Unnecessary overhead
#                        for single-turn requests that never exceed context.
#   --mlock              Lock model in RAM, prevent OS swapping to disk. Ensures
#                        consistent low-latency for the single dedicated model.
#   --no-mmap            Disable memory-mapped I/O. Combined with --mlock, forces
#                        the entire model into RAM. Critical for Pi where SD card
#                        or slow SSD would be a major bottleneck if model parts
#                        were swapped back to disk.

llama-server \
    -m /root/dev/edge_voice_agent/models/llms/gemma-3-1b-it-Q4_0.gguf \
    -c 1024 \
    -np 1 \
    -t 4 \
    -tb 4 \
    --no-context-shift \
    --mlock \
    --no-mmap \
    --port 8080 > /var/log/llama-server.log 2>&1 &
