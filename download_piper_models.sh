mkdir -p models/piper

# ONNX models are here
# https://github.com/rhasspy/piper/blob/master/VOICES.md

# for each voice we need the ONNX file and the JSON file
# models are all available in medium quality, some also in low and high
# inference time is signifiantly faster in low quality

mkdir -p models/piper

wget https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/low/en_US-lessac-low.onnx.json -O models/piper/en_US-lessac-low.onnx.json
wget https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/low/en_US-lessac-low.onnx -O models/piper/en_US-lessac-low.onnx

# TODO use instead python3 -m piper.download_voices en_US-lessac-medium

# wget https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json
# wget https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx
# wget https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/high/en_US-lessac-high.onnx.json
# wget https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/high/en_US-lessac-high.onnx
