"""
Download Silero VAD ONNX model from GitHub and store it locally.
"""
import urllib.request
import ssl
import hashlib
import subprocess
import os
from pathlib import Path


MODEL_NAME = 'silero_vad.onnx'
MODEL_URL = 'https://github.com/snakers4/silero-vad/raw/master/src/silero_vad/data/' + MODEL_NAME

DEFAULT_MODEL_DIR = os.path.join('models', 'silero_vad')

os.makedirs(DEFAULT_MODEL_DIR, exist_ok=True)
output_path = os.path.join(DEFAULT_MODEL_DIR, MODEL_NAME)

ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# Download with progress
def reporthook(block_num, block_size, total_size):
    downloaded = block_num * block_size
    if total_size > 0:
        percent = min(downloaded * 100 / total_size, 100)
        mb_downloaded = downloaded / 1024 / 1024
        mb_total = total_size / 1024 / 1024
        print(f"\r  Progress: {percent:.1f}% ({mb_downloaded:.2f}/{mb_total:.2f} MB)", end='')

opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ssl_context))
urllib.request.install_opener(opener)
urllib.request.urlretrieve(MODEL_URL, output_path, reporthook=reporthook)
print(f"\nDownloaded Silero VAD model to: {output_path}")