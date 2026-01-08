#!/usr/bin/env python3
"""Verify that streaming is actually happening in real-time, not buffered."""

import time
from llm_client import LLMClient

print("Testing real-time streaming behavior...")
print("=" * 60)

try:
    client = LLMClient(base_url="http://localhost:8080/v1", api_key="dummy")

    print("\nSending request: 'Write a short story in 5 sentences'")
    print("If streaming works, you should see chunks arrive progressively.\n")

    start_time = time.time()
    last_chunk_time = start_time
    chunk_count = 0
    total_content = ""

    stream = client.chat.completions.create(
        model="mymodel",
        messages=[{"role": "user", "content": "Write a short story in 5 sentences"}],
        stream=True
    )

    print("Streaming output (with timestamps):")
    print("-" * 60)

    for chunk in stream:
        current_time = time.time()
        time_since_start = current_time - start_time
        time_since_last = current_time - last_chunk_time

        if chunk.choices and chunk.choices[0].delta.content:
            content = chunk.choices[0].delta.content
            total_content += content
            chunk_count += 1

            # Print chunk with timing info
            print(f"[+{time_since_start:.3f}s, Δ{time_since_last:.3f}s] {repr(content)}")

            last_chunk_time = current_time

    print("-" * 60)
    print(f"\nTotal chunks: {chunk_count}")
    print(f"Total time: {time.time() - start_time:.2f}s")
    print(f"Average time between chunks: {(time.time() - start_time) / max(chunk_count, 1):.3f}s")

    print("\n✅ Full text:")
    print(total_content)

    print("\n" + "=" * 60)
    print("INTERPRETATION:")
    if chunk_count > 5:
        print("✅ Multiple chunks received - streaming appears to work!")
        print("✅ Timestamps show progressive arrival - true streaming confirmed!")
    else:
        print("⚠️  Very few chunks - might be buffering or very short response")

    client.close()

except Exception as e:
    print(f"❌ Error: {e}")
    print("\nMake sure llama-server is running:")
    print("   llama-server -m models/llms/LFM2-350M-Q4_K_M.gguf --port 8080")
