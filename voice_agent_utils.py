import argparse

DEFAULT_LLM_SERVER_URL = "http://localhost:8080/v1"
DEFAULT_LLM_SERVER_MODEL = "dummy"
DEFAULT_LLM_SERVER_API_KEY = "dummy"

DEFAULT_LANGUAGE = "en"

DEFAULT_SYSTEM_PROMPT = """You are a pirate. You talk like a pirate from the 18th century. Short replies only. One sentence max. No lists. No bullet 
points.

User: How are you?
Pirate: Aye, I be finer than a freshly swabbed deck, mate!"""

DEFAULT_START_MESSAGE = "Ahoy landlubber!"
DEFAULT_GOODBYE_MESSAGE = "Fair winds, mate!"
DEFAULT_EXIT_COMMAND = "please quit"


def get_cli_argument_parser():
    parser = argparse.ArgumentParser(description="On Device Voice Agen")
    parser.add_argument("--llm_server_url", default=DEFAULT_LLM_SERVER_URL, help="Url where LLM is served using OpenAI-compatible API format.")
    parser.add_argument("--tts_engine", choices=['piper', 'kokoro'], default="piper", help="which tts engine to use; piper is much faster than kokoro.")
    parser.add_argument("--asr_model_name", default="moonshine_v1_tiny", help="which asr model to run.")
    parser.add_argument("--asr_model_path", default="models/moonshine_v1_tiny", help="Path to the ASR model directory (use empty string to unset for models that don't need it)")
    parser.add_argument("--disable_partials", action="store_true", default=True, help="Disable partial transcription results (default: True)")
    parser.add_argument("--enable_partials", dest="disable_partials", action="store_false", help="Enable partial transcription results")
    parser.add_argument("--language", default=DEFAULT_LANGUAGE, help="language to use")
    parser.add_argument("--tts_model_path", required=False, help="Path to the tts model (.onnx file)")
    parser.add_argument("--speaking_rate", type=float, default=1.0, help="how fast should generated speech be, 1.0 is default, higher numbers mean faster speech")
    parser.add_argument("--max_words_to_speak_start", type=int, default=5, help="maximum number of words to speech onset after a prompt; reduce if latency too high.")
    parser.add_argument("--max_words_to_speak", type=float, default=20, help="always produce speech after this many words were produced ignoring sentence boundaries.")        
    parser.add_argument("--system_prompt", default=DEFAULT_SYSTEM_PROMPT, help="Instructions for the model.")
    parser.add_argument("--start_message", default=DEFAULT_START_MESSAGE, help="Opening sentence.")
    parser.add_argument("--min_partial_duration", type=float, default=0.25, help="Minimum duration in seconds for partial transcriptions to be displayed.",)
    parser.add_argument("--end_of_utterance_duration", type=float, default=0.7, help="Silence seconds until end of turn of user identified")
    parser.add_argument("--enable_keyboard_control", action="store_true", default=False, help="Enable keyboard control (space to mute/unmute, ESC to exit)")
    parser.add_argument("--verbose", action="store_true", help="Verbose status info")
    parser.add_argument("--interaction_handler", choices=['colored', 'minimal', 'whisplay', 'display_leds_interrupt'], default="colored", help="Interaction handler: 'colored' (default) for rich console output, 'minimal' for emoji status, 'whisplay' for Whisplay HAT, 'display_leds_interrupt' for Waveshare display + external LEDs + ReSpeaker button. Use --platform for GPIO interrupt button.")
    parser.add_argument("--audio-device-input", type=str, default=None,
                        help="Input audio device (mic): index (e.g. '3') or ALSA name (e.g. 'plughw:3,0')")
    parser.add_argument("--audio-device-output", type=str, default=None,
                        help="Output audio device (speaker): index (e.g. '3') or ALSA name (e.g. 'plughw:3,0')")
    parser.add_argument("--platform", choices=['rpi5', 'opi5'], default=None,
                        help="Hardware platform for GPIO: rpi5 (Raspberry Pi 5) or opi5 (Orange Pi 5 Pro)")

    return parser


def apply_audio_device_settings(args):
    """Apply audio device settings from CLI args to sounddevice defaults."""
    if args.audio_device_input is not None or args.audio_device_output is not None:
        import sounddevice as sd

        def parse_device(device_str):
            try:
                return int(device_str)
            except ValueError:
                return device_str

        if args.audio_device_input is not None:
            input_dev = parse_device(args.audio_device_input)
            sd.default.device[0] = input_dev
            name = sd.query_devices(input_dev)['name'] if isinstance(input_dev, int) else input_dev
            print(f">> Using input device: {name}")

        if args.audio_device_output is not None:
            output_dev = parse_device(args.audio_device_output)
            sd.default.device[1] = output_dev
            name = sd.query_devices(output_dev)['name'] if isinstance(output_dev, int) else output_dev
            print(f">> Using output device: {name}")

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
