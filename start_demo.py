#!/usr/bin/env python3
"""
Start script for Edge Voice Agent with fitness coach system prompt
Usage: ./start.py [--kokoro] [other voice_agent_cli.py args]
"""

import subprocess
import sys
import time
import os
from pathlib import Path

prompt_file = "coach_demo_prompt.txt"

def start_llama_server():
    """Start llama server with the default model"""
    # model_path = "models/llms/LFM2-1.2B-Q4_K_M.gguf"
    model_path = "models/llms/LFM2-350M-Q4_K_M.gguf"
    
    if not Path(model_path).exists():
        print(f"❌ Model not found: {model_path}")
        print("   Run 'python setup.py' first to download models")
        sys.exit(1)
    
    print("🦙 Starting llama server...")
    cmd = [
        "llama-server",
        "-m", model_path,
        "--port", "8080",
        "--host", "127.0.0.1",
        "-c", "2048",
        "-ngl", "0",
        "--temp", "0.7"
    ]
    
    try:
        return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except FileNotFoundError:
        print("❌ llama-server not found in PATH")
        print("   Please install llama.cpp first (see setup.py for instructions)")
        sys.exit(1)

def start_voice_agent():
    """Start the voice agent with fitness coach configuration"""
    if not Path(prompt_file).exists():
        print("❌ prompt file not found:", prompt_file)
        sys.exit(1)
    
    # Check for kokoro flag
    use_kokoro = "--kokoro" in sys.argv
    if use_kokoro:
        sys.argv.remove("--kokoro")  # Remove it so it doesn't get passed to voice_agent_cli
        print("🎙️  Starting voice agent with fitness coach (Kokoro TTS)...")
    else:
        print("🎙️  Starting voice agent with fitness coach (Piper TTS)...")
    
    # Read system prompt
    with open(prompt_file, "r") as f:
        system_prompt = f.read().strip()
    
    cmd = [
        sys.executable, "voice_agent_cli.py",
        "--system_prompt", system_prompt,
        "--start_message", "Coach reporting for duty! Ready to crush it! What's up!"
    ]
    
    # Add TTS selection
    if use_kokoro:
        cmd.extend(["--tts_engine", "kokoro"])
    
    # Add remaining arguments
    cmd.extend(sys.argv[1:])
    
    return subprocess.run(cmd)

if __name__ == "__main__":
    server_process = None
    try:
        # Start llama server
        server_process = start_llama_server()
        
        # Wait a moment for server to start
        print("⏳ Waiting for server to start...")
        time.sleep(3)
        
        # Check if server started successfully
        if server_process.poll() is not None:
            stdout, stderr = server_process.communicate()
            print("❌ Server failed to start:")
            if stderr:
                print(stderr.decode())
            sys.exit(1)
        
        # Start voice agent
        start_voice_agent()
        
    except KeyboardInterrupt:
        print("\n🛑 Stopping...")
    finally:
        if server_process:
            print("🛑 Stopping llama server...")
            server_process.terminate()
            server_process.wait()