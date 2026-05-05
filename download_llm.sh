# NOTE: this is just one example
mkdir -p models/llms

wget https://huggingface.co/LiquidAI/LFM2.5-350M-GGUF/resolve/main/LFM2.5-350M-Q4_K_M.gguf -O models/llms/LFM2.5-350M-Q4_K_M.gguf
wget https://huggingface.co/LiquidAI/LFM2.5-1.2B-Instruct-GGUF/resolve/main/LFM2.5-1.2B-Instruct-Q4_K_M.gguf -O models/llms/LFM2.5-1.2B-Instruct-Q4_K_M.gguf
wget https://huggingface.co/unsloth/gemma-3-1b-it-GGUF/resolve/main/gemma-3-1b-it-Q4_K_M.gguf -O models/llms/gemma-3-1b-it-Q4_K_M.gguf
