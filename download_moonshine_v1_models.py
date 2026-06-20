"""Download Moonshine V1 ONNX models from HF hub to allow offline usage.

LICENSE NOTE: Models are downloaded directly from their provider (UsefulSensors/
moonshine on the HF hub) and are governed by THEIR license, not this project's
(Apache 2.0). The Moonshine models are released under the MIT license. Review
before use.
"""
from huggingface_hub import hf_hub_download
import os
import shutil
from pathlib import Path

# Download to project root models/ directory
models_dir = Path("models")
precision = "float"
repo = "UsefulSensors/moonshine"

models_to_download = [
    ("tiny", "moonshine_v1_tiny"),
    ("base", "moonshine_v1_base"),
]

for model_name, target_dir_name in models_to_download:
    print(f"\n=== Downloading {model_name} model ===")

    output_folder = models_dir / target_dir_name
    os.makedirs(output_folder, exist_ok=True)

    subfolder = f"onnx/merged/{model_name}/{precision}"

    downloaded_files = []
    for model_file in ("encoder_model", "decoder_model_merged"):
        # Download to HF cache first
        cached_path = hf_hub_download(
            repo,
            f"{model_file}.onnx",
            subfolder=subfolder
        )

        # Copy directly to output_folder root
        destination = output_folder / f"{model_file}.onnx"
        shutil.copy(cached_path, str(destination))
        downloaded_files.append(str(destination))

    print(f"✓ Downloaded to: {output_folder}")
    print(f"  Files: {downloaded_files}")

print("\n✓ All Moonshine V1 models downloaded successfully!")