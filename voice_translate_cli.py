# example for voice translation agent
# Translations are done stateless, single-turn.
#
# Supports language switching by either keyboard shortcuts or with
# rotary dial on GPIO pins (Raspberry Pi 5 or Orange Pi 5 Pro)
#
# Usage examples:
#
#   Basic (with keyboard language switching):
#     python voice_translate_cli.py
#
#   With GPIO on Raspberry Pi 5:
#     python voice_translate_cli.py --platform rpi5
#
#   With GPIO on Orange Pi 5 Pro:
#     python voice_translate_cli.py --platform opi5
#
#   Language switching keys:
#     g = German    (speaks "Bereit!")
#     s = Spanish   (speaks "Listo!")
#     a = Arabic    (speaks "Mustaeidd!")
#     f = French    (speaks "Pret!")
#
#   Verbose mode (debug output):
#     python voice_translate_cli.py --verbose
#
# Exit: Say "goodbye" (voice command)

import threading
import time
start_time = time.time()
print("Loading Voice Agent...")

import sys
from voice_agent import VoiceAgent
import voice_agent_utils
from voice_agent_interaction_handlers import get_handler

print(f">> -- All imports done in {time.time() - start_time:.2f} seconds -- <<")

# Language configurations for translation
LANGUAGE_CONFIGS = {
    'german': {
        "lang": "German",
        # "tts_model": "models/piper/de_DE-eva_k-x_low.onnx",
        "tts_model": "models/piper/de_DE-thorsten-low.onnx",
        "prompt": "Translate the following into German. Your response should only contain a single translation (no context, commentary, or explanation):",
        "ready_message": "Ich bin bereit!"
    },
    'spanish': {
        "lang": "Spanish",
        "tts_model": "models/piper/es_ES-carlfm-x_low.onnx",
        "prompt": "Translate the following into Spanish. Your response should only contain a single translation (no context, commentary, or explanation):",
        "ready_message": "Estoy listo!"
    },
    'arabic': {
        "lang": "Arabic",
        "tts_model": "models/piper/ar_JO-kareem-low.onnx",
        "prompt": "Translate the following into Levantine Arabic. Your response should only contain a single translation (no context, commentary, or explanation):",
        "ready_message": "Mustaeidd!"
    },
    'french': {
        "lang": "French",
        "tts_model": "models/piper/fr_FR-siwis-low.onnx",
        "prompt": "Translate the following into French. Your response should only contain a single translation (no context, commentary, or explanation):",
        "ready_message": "Je suis pret!"
    },
}

# Keyboard shortcuts for language selection
LANGUAGE_KEYS = {
    'g': 'german',
    's': 'spanish',
    'a': 'arabic',
    'f': 'french',
}

DEFAULT_OUTPUT_LANGUAGE = 'spanish'

def main():
    """Main function to run the LLM to Audio output streamer."""

    parser = voice_agent_utils.get_cli_argument_parser()
    parser.add_argument("--platform", choices=['rpi5', 'opi5'], default=None,
                        help="Hardware platform for GPIO: rpi5 (Raspberry Pi 5) or opi5 (Orange Pi 5 Pro)")
    args = parser.parse_args()

    voice_agent_utils.apply_audio_device_settings(args)

    t1 = time.time()
    print(">> Initializing user interaction and controls <<")

    # Create interaction handlers (GPIO is handled separately via gpio_inputs.py)
    user_interaction_handler = get_handler("colored", "User Input", "blue", is_agent=False)
    agent_interaction_handler = get_handler("colored", "Agent Output", "magenta", is_agent=True)

    # -- Setup GPIO handler based on platform --
    gpio_handler = None
    if args.platform:
        from gpio_inputs import RaspberryPi5GPIOHandler, OrangePi5ProGPIOHandler
        if args.platform == 'rpi5':
            gpio_handler = RaspberryPi5GPIOHandler()
        elif args.platform == 'opi5':
            gpio_handler = OrangePi5ProGPIOHandler()
        gpio_handler.setup()
        print(f">> GPIO handler: {gpio_handler.__class__.__name__}")

    # Read rotary dial position (or use default if not connected)
    initial_language = None
    if gpio_handler:
        initial_language = gpio_handler.get_current_language()

    if initial_language is None:
        initial_language = DEFAULT_OUTPUT_LANGUAGE
        print(f">> No rotary position detected, using default: {initial_language.upper()}")
    else:
        print(f">> Initial language from rotary dial: {initial_language.upper()}")
    print(f">> Took {time.time()-t1:.2f} secs to initialize interaction and controls <<")


    # get startup language
    start_config = LANGUAGE_CONFIGS[initial_language]
    start_system_prompt = start_config["prompt"]
    start_ready_message = start_config["ready_message"]
    start_tts_model_path = start_config["tts_model"]



    # initialize voice agent components
    t1 = time.time()
    print(">> Initializing Voice Agent and components <<")
    va = VoiceAgent()

    va.init_LLmToAudioOutput(
        llm_server_url=args.llm_server_url,
        system_prompt=start_system_prompt,
        start_message=start_ready_message,
        tts_engine=args.tts_engine,
        speaking_rate=args.speaking_rate,
        tts_model_path=start_tts_model_path,
        max_words_to_speak_start=args.max_words_to_speak_start,
        max_words_to_speak=args.max_words_to_speak,
        verbose=args.verbose,
        single_turn=True,  # Each translation is independent, no context needed
        printer=agent_interaction_handler
    )


    va.init_AudioToText(
        asr_model_name=args.asr_model_name,
        asr_model_path=args.asr_model_path if args.asr_model_path else None,
        disable_partials=args.disable_partials,
        language=args.language,
        min_partial_duration=args.min_partial_duration,
        end_of_utterance_duration=args.end_of_utterance_duration,
        verbose=args.verbose,
        printer=user_interaction_handler
    )
    va.start()
    print(f">> Took {time.time()-t1:.2f} secs to initialize Voice Agent <<")

    # full start time to ready
    print(f">> --  Voice Agent ready in {time.time()-start_time:.2f} seconds -- <<")

    # Define interrupt callback
    interrupt_count = {'n': 0}
    def on_output_interrupt():
        """Interrupt agent's speech output."""
        interrupt_count['n'] += 1
        if args.verbose:
            print(f"\n[Interrupted #{interrupt_count['n']}] at {time.time():.2f}")
        va.output_handler.interrupt()
        if hasattr(user_interaction_handler, 'show_interrupted'):
            user_interaction_handler.show_interrupted()
            time.sleep(0.3)
        user_interaction_handler.start()
        if args.verbose:
            print(f"[Interrupt #{interrupt_count['n']} done]")

    # Setup GPIO interrupt button via gpio_handler
    if gpio_handler:
        gpio_handler.set_interrupt_callback(on_output_interrupt)
        print(">> GPIO interrupt button enabled")

    # Setup keyboard controls via the interaction handler
    if hasattr(user_interaction_handler, 'setup_keyboard_controls'):
        # Add language switching keys to callbacks
        key_callbacks = {
        }
        for key, lang_name in LANGUAGE_KEYS.items():
            key_callbacks[key] = lambda ln=lang_name: va.change_language(LANGUAGE_CONFIGS[ln])

        user_interaction_handler.setup_keyboard_controls(key_callbacks)

        print("Keyboard controls active:")
        # print("  ENTER: interrupt | SPACE: mute/unmute | ESC: exit")
        print("  Language: g=German, s=Spanish, a=Arabic, f=French")
    
    # -- rotary switch integration via gpio_handler --
    if gpio_handler:
        # Delay to avoid queuing languages during dial turn
        switch_state = {'timer': None}
        SETTLE_DELAY = 0.3

        def on_language_change(lang_name):
            if switch_state['timer'] is not None:
                switch_state['timer'].cancel()
            if lang_name in LANGUAGE_CONFIGS:
                switch_state['timer'] = threading.Timer(
                    SETTLE_DELAY,
                    va.change_language,
                    args=[LANGUAGE_CONFIGS[lang_name]]
                )
                switch_state['timer'].start()

        gpio_handler.set_language_change_callback(on_language_change)
        print(">> Rotary switch listener active")
    else:
        print(">> GPIO not available (use --platform rpi5 or opi5), using keyboard: g/s/a/f")

    # Run the voice agent
    try:
        va.run()
    finally:
        # Clean up GPIO handler
        if gpio_handler:
            gpio_handler.cleanup()
        # Clean up interaction handler (handles keyboard listener cleanup too)
        if hasattr(user_interaction_handler, 'cleanup'):
            user_interaction_handler.cleanup()

if __name__ == "__main__":
    main()
