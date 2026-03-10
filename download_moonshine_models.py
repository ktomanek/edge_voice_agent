"""Download Moonshine ONNX models using moonshine_voice library."""

import os
import shutil
import tempfile
from pathlib import Path

# Set cache directory to /tmp folder before importing
tmp_dir = Path(tempfile.gettempdir()) / "moonshine_download"
tmp_dir.mkdir(parents=True, exist_ok=True)
models_dir = Path(__file__).parent / "models"
os.environ["MOONSHINE_VOICE_CACHE"] = str(tmp_dir)

from moonshine_voice.download import get_model_for_language, ModelArch

# Download English models for tiny and base architectures
if __name__ == "__main__":
    print("Downloading Moonshine models for English...")
    print(f"Temporary cache directory: {tmp_dir}")

    models_to_download = [
        (ModelArch.TINY, "moonshine_tiny"),
        (ModelArch.BASE, "moonshine_base"),
    ]

    for arch, target_dir_name in models_to_download:
        print(f"\n=== Downloading {arch.value} model ===")

        # Download using library (to tmp cache)
        result = get_model_for_language("en", arch)
        # get_model_for_language returns a tuple (model_path, ...)
        downloaded_path = Path(result[0]) if isinstance(result, tuple) else Path(result)
        print(f"Downloaded to: {downloaded_path}")

        # Move to final location
        target_dir = models_dir / target_dir_name
        if target_dir.exists():
            print(f"Removing existing directory: {target_dir}")
            shutil.rmtree(target_dir)

        print(f"Moving {downloaded_path} -> {target_dir}")
        shutil.move(str(downloaded_path), str(target_dir))
        print(f"✓ Moved to: {target_dir}")

    # Clean up entire tmp directory
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
        print(f"\n✓ Cleaned up temporary directory: {tmp_dir}")

    print("\n✓ All models downloaded successfully!")
