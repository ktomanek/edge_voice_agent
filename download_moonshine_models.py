# download moonshone ONNX models from HF hub to allow offline usage
from huggingface_hub import hf_hub_download
import os
import shutil

precision="float"
model_name = 'tiny'
output_folder = 'models/moonshine_' + model_name
os.makedirs(output_folder, exist_ok=True)

repo = "UsefulSensors/moonshine"
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
    destination = os.path.join(output_folder, f"{model_file}.onnx")
    shutil.copy(cached_path, destination)
    downloaded_files.append(destination)

print(f"\nAll files downloaded to: {output_folder}")
print(f"Downloaded files: {downloaded_files}")