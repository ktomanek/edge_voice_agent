import argparse

DEFAULT_LLM_SERVER_URL = "http://localhost:8080/v1"
DEFAULT_LLM_SERVER_MODEL = "dummy"
DEFAULT_LLM_SERVER_API_KEY = "dummy"

DEFAULT_SYSTEM_PROMPT = """
You are an AI assistant that runs on an edge device. You're helpful and friendly, but you are a bit of a weirdo and certainly funny at times. Keep your responses short and concise (no more than 2 sentences), as they will be read aloud.
It is generally helpful to use discourse markers where appropriate to keep a good conversation flow. Remember be witty but also understanding.
"""
DEFAULT_START_MESSAGE = "Hello, how can I help?"
DEFAULT_LANGUAGE = "en"
DEFAULT_GOODBYE_MESSAGE = 'Good bye!'
DEFAULT_EXIT_COMMAND = 'please exit'


def get_cli_argument_parser():
    parser = argparse.ArgumentParser(description="On Device Voice Agen")
    parser.add_argument("--llm_server_url", default=DEFAULT_LLM_SERVER_URL, help="Url where LLM is served using OpenAI-compatible API format.")
    parser.add_argument("--tts_engine", choices=['piper', 'kokoro'], default="piper", help="which tts engine to use; piper is much faster than kokoro.")
    parser.add_argument("--asr_model_name", default="moonshine_onnx_tiny", help="which asr model to run.")
    parser.add_argument("--language", default=DEFAULT_LANGUAGE, help="language to use")
    parser.add_argument("--tts_model_path", required=False, help="Path to the tts model (.onnx file)")
    parser.add_argument("--speaking_rate", type=float, default=1.0, help="how fast should generated speech be, 1.0 is default, higher numbers mean faster speech")
    parser.add_argument("--max_words_to_speak_start", type=int, default=5, help="maximum number of words to speech onset after a prompt; reduce if latency too high.")
    parser.add_argument("--max_words_to_speak", type=float, default=20, help="always produce speech after this many words were produced ignoring sentence boundaries.")        
    parser.add_argument("--system_prompt", default=DEFAULT_SYSTEM_PROMPT, help="Instructions for the model.")
    parser.add_argument("--start_message", default=DEFAULT_START_MESSAGE, help="Opening sentence.")
    parser.add_argument("--min_partial_duration", type=float, default=0.25, help="Minimum duration in seconds for partial transcriptions to be displayed.",)
    parser.add_argument("--end_of_utterance_duration", type=float, default=0.5, help="Silence seconds until end of turn of user identified")
    parser.add_argument("--enable_keyboard_control", action="store_true", default=False, help="Enable keyboard control (space to mute/unmute, ESC to exit)")
    parser.add_argument("--verbose", action="store_true", help="Verbose status info")
    
    return parser

def get_ui_argument_parser():
    
    # get basic arguments
    parser = get_cli_argument_parser()

    # UI configuration arguments
    parser.add_argument("--window_size", default="470x250", help="Window size in format WIDTHxHEIGHT")
    parser.add_argument("--fullscreen", action="store_true", default=False, help="Run in fullscreen mode")
    parser.add_argument("--label_font_size", type=int, default=14, help="Font size for labels")
    parser.add_argument("--textbox_font_size", type=int, default=14, help="Font size for textboxes")
    parser.add_argument("--button_font_size", type=int, default=20, help="Font size for buttons")
    parser.add_argument("--appearance_mode", default="dark", choices=["dark", "light", "system"], help="UI appearance mode")
    parser.add_argument("--color_theme", default="blue", help="UI color theme")
    
    return parser