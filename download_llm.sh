# NOTE: this is just one example
#
# LICENSE NOTE: Models are downloaded directly from their providers and are
# governed by THEIR licenses, not this project's (Apache 2.0). Review before use:
#   - LiquidAI LFM2 / LFM2.5: LFM Open License v1.0 (free commercial use only for
#     orgs with annual revenue under $10M) -> https://www.liquid.ai/lfm-license
#   - Google Gemma: Gemma Terms of Use (custom license, not OSS)
#     -> https://ai.google.dev/gemma/terms
# You are free to substitute any other GGUF model.
mkdir -p models/llms

wget https://huggingface.co/LiquidAI/LFM2.5-350M-GGUF/resolve/main/LFM2.5-350M-Q4_K_M.gguf -O models/llms/LFM2.5-350M-Q4_K_M.gguf
wget https://huggingface.co/LiquidAI/LFM2.5-1.2B-Instruct-GGUF/resolve/main/LFM2.5-1.2B-Instruct-Q4_K_M.gguf -O models/llms/LFM2.5-1.2B-Instruct-Q4_K_M.gguf
wget https://huggingface.co/unsloth/gemma-3-1b-it-GGUF/resolve/main/gemma-3-1b-it-Q4_K_M.gguf -O models/llms/gemma-3-1b-it-Q4_K_M.gguf
