#!/usr/bin/env python3
"""
Unified setup script for Edge Voice Agent
Installs dependencies and downloads models
"""

import os
import sys
import subprocess
import urllib.request
import platform
from pathlib import Path

def run_command(cmd, description="", check=True):
    """Run a shell command with error handling"""
    print(f"🔄 {description}")
    try:
        if isinstance(cmd, list):
            result = subprocess.run(cmd, check=check, capture_output=True, text=True)
        else:
            result = subprocess.run(cmd, shell=True, check=check, capture_output=True, text=True)
        
        if result.stdout:
            print(f"   {result.stdout.strip()}")
        return result
    except subprocess.CalledProcessError as e:
        print(f"❌ Error: {e}")
        if e.stderr:
            print(f"   {e.stderr.strip()}")
        if check:
            sys.exit(1)
        return e

def download_file(url, output_path, description=""):
    """Download a file with progress"""
    print(f"⬇️  {description}")
    try:
        urllib.request.urlretrieve(url, output_path)
        print(f"   ✅ Downloaded to {output_path}")
    except Exception as e:
        print(f"❌ Failed to download {url}: {e}")
        sys.exit(1)

def check_llama_cpp():
    """Check if llama-server is available"""
    print("🦙 Checking for llama-server...")
    try:
        result = subprocess.run(["llama-server", "--version"], 
                              capture_output=True, text=True, timeout=10)
        print("   ✅ llama-server found")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        print("❌ llama-server not found in PATH")
        print("   Please install llama.cpp first:")
        print()
        
        system = platform.system().lower()
        if system == "darwin":  # macOS
            print("   macOS installation options:")
            print("   • Homebrew: brew install llama.cpp")
            print("   • From source: https://github.com/ggml-org/llama.cpp")
        elif system == "linux":
            # Check for common package managers
            distro_info = ""
            try:
                with open("/etc/os-release", "r") as f:
                    distro_info = f.read().lower()
            except:
                pass
            
            print("   Linux installation options:")
            if "ubuntu" in distro_info or "debian" in distro_info:
                print("   • APT: sudo apt update && sudo apt install llama.cpp")
            elif "fedora" in distro_info or "rhel" in distro_info or "centos" in distro_info:
                print("   • DNF: sudo dnf install llama.cpp")
            elif "arch" in distro_info:
                print("   • Pacman: sudo pacman -S llama.cpp")
            else:
                print("   • Check your package manager for llama.cpp")
            print("   • From source: https://github.com/ggml-org/llama.cpp")
        elif system == "windows":
            print("   Windows installation options:")
            print("   • Chocolatey: choco install llama.cpp")
            print("   • Scoop: scoop install llama.cpp")
            print("   • Download binary: https://github.com/ggml-org/llama.cpp/releases")
        else:
            print("   Install from source: https://github.com/ggml-org/llama.cpp")
        
        print()
        print("   After installation, ensure 'llama-server' is in your PATH and try again.")
        sys.exit(1)

def setup_models():
    """Download and setup all models"""
    print("📦 Setting up models...")
    
    # Create model directories
    for dir_name in ["models/piper", "models/kokoro", "models/llms"]:
        Path(dir_name).mkdir(parents=True, exist_ok=True)
    
    # Download Piper models
    print("🎙️  Downloading Piper TTS models...")
    download_file(
        "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/low/en_US-lessac-low.onnx.json",
        "models/piper/en_US-lessac-low.onnx.json",
        "Piper voice config"
    )
    download_file(
        "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/low/en_US-lessac-low.onnx",
        "models/piper/en_US-lessac-low.onnx",
        "Piper voice model"
    )
    
    # Download Kokoro models
    print("🎵 Downloading Kokoro TTS models...")
    download_file(
        "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin",
        "models/kokoro/kokoro-voices-v1.0.bin",
        "Kokoro voices"
    )
    download_file(
        "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.fp16.onnx",
        "models/kokoro/kokoro-v1.0.fp16.onnx",
        "Kokoro model"
    )
    
    # Download LLM models
    print("🧠 Downloading LLM models...")
    download_file(
        "https://huggingface.co/LiquidAI/LFM2-350M-GGUF/resolve/main/LFM2-350M-Q4_K_M.gguf",
        "models/llms/LFM2-350M-Q4_K_M.gguf",
        "LFM2-350M model (for demo)"
    )
    download_file(
        "https://huggingface.co/LiquidAI/LFM2-1.2B-GGUF/resolve/main/LFM2-1.2B-Q4_K_M.gguf",
        "models/llms/LFM2-1.2B-Q4_K_M.gguf",
        "LFM2-1.2B model (better quality)"
    )

def main():
    """Main setup function"""
    print("🚀 Setting up Edge Voice Agent...")
    print("=" * 50)
    
    # Check Python version
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 or higher is required")
        sys.exit(1)
    
    # Check for llama.cpp
    check_llama_cpp()
    
    # Install Python dependencies
    run_command([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], 
                "Installing Python dependencies")
    
    # Download spacy model
    run_command([sys.executable, "-m", "spacy", "download", "en_core_web_sm"], 
                "Downloading spacy model")
    
    # Setup models
    setup_models()
    
    print("=" * 50)
    print("✅ Setup complete!")
    print("\n📋 Next steps:")
    print("1. Start llama server: llama-server -m models/llms/LFM2-350M-Q4_K_M.gguf --port 8080")
    print("2. Run: python voice_agent_cli.py")

if __name__ == "__main__":
    main()