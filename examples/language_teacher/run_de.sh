python ../../voice_agent_cli.py \
   --ollama_model_name gemma3:1b \
   --tts_model_path de_DE-karlsson-low.onnx  \
   --asr_model_name whisper_tiny \
   --language de \
   --system_prompt "`cat instructions_de.txt `" \
   --start_message "Hallo! Ich bin Lehrer Bolte.  Ich bin dein geduldiger Deutschlehrer. Erzähl mir, wie du heißt und was dich so interessiert." \
   --min_partial_duration 0.5 \
   --end_of_utterance_duration 0.75 \
   --speaking_rate 1.0
