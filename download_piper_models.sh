mkdir -p models/piper

# LICENSE NOTE: Voices are downloaded directly from rhasspy/piper-voices and are
# governed by THEIR licenses, not this project's (Apache 2.0). The Piper code is
# MIT, but each voice has its own license tied to the dataset it was trained on
# (e.g. the en_US lessac voice uses the CSTR Blizzard 2013 dataset). Check the
# per-voice license before use -> https://github.com/rhasspy/piper/blob/master/VOICES.md
# (the license is also listed in each voice's accompanying .onnx.json / MODEL_CARD)

# ONNX models are here
# https://github.com/rhasspy/piper/blob/master/VOICES.md

# for each voice we need the ONNX file and the JSON file
# models are all available in medium quality, some also in low and high
# inference time is signifiantly faster in low quality

mkdir -p models/piper

# English
wget https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/low/en_US-lessac-low.onnx.json -O models/piper/en_US-lessac-low.onnx.json
wget https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/low/en_US-lessac-low.onnx -O models/piper/en_US-lessac-low.onnx

# German
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/de/de_DE/thorsten/low/de_DE-thorsten-low.onnx -O models/piper/de_DE-thorsten-low.onnx
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/de/de_DE/thorsten/low/de_DE-thorsten-low.onnx.json -O models/piper/de_DE-thorsten-low.onnx.json

#wget https://huggingface.co/rhasspy/piper-voices/resolve/main/de/de_DE/eva_k/x_low/de_DE-eva_k-x_low.onnx -O models/piper/de_DE-eva_k-x_low.onnx
#wget https://huggingface.co/rhasspy/piper-voices/resolve/main/de/de_DE/eva_k/x_low/de_DE-eva_k-x_low.onnx.json -O models/piper/de_DE-eva_k-x_low.onnx.json

# Spanish
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_ES/carlfm/x_low/es_ES-carlfm-x_low.onnx -O models/piper/es_ES-carlfm-x_low.onnx
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_ES/carlfm/x_low/es_ES-carlfm-x_low.onnx.json -O models/piper/es_ES-carlfm-x_low.onnx.json

# French
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/fr/fr_FR/siwis/low/fr_FR-siwis-low.onnx -O models/piper/fr_FR-siwis-low.onnx
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/fr/fr_FR/siwis/low/fr_FR-siwis-low.onnx.json -O models/piper/fr_FR-siwis-low.onnx.json

