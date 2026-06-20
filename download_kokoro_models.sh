# LICENSE NOTE: Models are downloaded directly from the kokoro-onnx project and
# are governed by THEIR licenses, not this project's (Apache 2.0). The Kokoro
# model is released under Apache 2.0. Review before use.

# ONNX models
# https://github.com/thewh1teagle/kokoro-onnx/releases


mkdir -p models/kokoro

# download and store with different name
wget https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin -O models/kokoro/kokoro-voices-v1.0.bin

# flp16 model takes same run time as full precision model, int8 is twice as slow!

# # 310 MB
# wget https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx -O models/kokoro/kokoro-v1.0.onnx

# 170 MB
wget https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.fp16.onnx -O models/kokoro/kokoro-v1.0.fp16.onnx

# # 88 MB
# wget https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.int8.onnx -O models/kokoro/kokoro-v1.0.int8.onnx

