# NOTE: this is just one example
mkdir -p models/llms

wget https://huggingface.co/LiquidAI/LFM2-350M-GGUF/resolve/main/LFM2-350M-Q4_K_M.gguf -O models/llms/LFM2-350M-Q4_K_M.gguf
wget https://huggingface.co/LiquidAI/LFM2-1.2B-GGUF/resolve/main/LFM2-1.2B-Q4_0.gguf -O models/llms/LFM2-1.2B-Q4_0.gguf
wget https://huggingface.co/unsloth/gemma-3-1b-it-GGUF/resolve/main/gemma-3-1b-it-Q4_0.gguf -O models/llms/gemma-3-1b-it-Q4_0.gguf
wget https://huggingface.co/unsloth/gemma-3-1b-it-GGUF/resolve/main/gemma-3-1b-it-Q4_K_M.gguf -O models/llms/gemma-3-1b-it-Q4_K_M.gguf

