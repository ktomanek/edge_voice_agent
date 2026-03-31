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
#   Preload all TTS models for faster language switching:
#     python voice_translate_cli.py --preload-tts
#
#   Language switching keys:
#     g = German    (speaks "Bereit!")
#     s = Spanish   (speaks "Listo!")
#     f = French    (speaks "Pret!")
#
#   Verbose mode (debug output):
#     python voice_translate_cli.py --verbose
#
# Exit: Say "goodbye" (voice command)

import logging
import threading
import time
start_time = time.time()
print("Loading Voice Agent...")

import sys
from voice_agent import VoiceAgent
import voice_agent_utils
from tts_lib import tts_engines
from voice_agent_interaction_handlers import get_handler

# Suppress Piper phoneme warnings (some models missing combining characters)
logging.getLogger('piper.phoneme_ids').setLevel(logging.ERROR)

print(f">> -- All imports done in {time.time() - start_time:.2f} seconds -- <<")

# Translation mode uses fixed word limits to avoid premature sentence splitting
# Complete sentences (with . ! ?) still speak immediately via sentence detection
TRANSLATION_MAX_WORDS = 15

# Language configurations for translation
LANGUAGE_CONFIGS = {
    'german': {
        "lang": "German",
        "tts_model": "models/piper/de_DE-thorsten-low.onnx",
        "prompt": "Translate the following into German. Give only the translation on a single line, no explanations:",
        "ready_message": "Ich bin bereit!"
    },
    'spanish': {
        "lang": "Spanish",
        "tts_model": "models/piper/es_ES-carlfm-x_low.onnx",
        "prompt": "Translate the following into Spanish. Give only the translation on a single line, no explanations:",
        "ready_message": "Estoy listo!"
    },
    'french': {
        "lang": "French",
        "tts_model": "models/piper/fr_FR-siwis-low.onnx",
        "prompt": "Translate the following into French. Give only the translation on a single line, no explanations:",
        "ready_message": "Je suis pret!"
    },
}

# Keyboard shortcuts for language selection
LANGUAGE_KEYS = {
    'g': 'german',
    's': 'spanish',
    'f': 'french',
}

DEFAULT_OUTPUT_LANGUAGE = 'spanish'

def preload_tts_models(language_configs, verbose=False):
    """Preload all TTS models into a cache dictionary.

    Args:
        language_configs: dict of language configurations with 'tts_model' keys
        verbose: whether to print progress info

    Returns:
        dict mapping model paths to loaded TTS instances
    """
    tts_cache = {}
    print(">> Preloading all TTS models...")
    t_start = time.time()

    for lang_name, config in language_configs.items():
        model_path = config['tts_model']
        if model_path not in tts_cache:
            t1 = time.time()
            if verbose:
                print(f"   Loading {lang_name}: {model_path}")
            tts_cache[model_path] = tts_engines.TTS_Piper(model_path, warmup=False)
            if verbose:
                print(f"   Loaded in {time.time() - t1:.2f} secs")

    print(f">> All {len(tts_cache)} TTS models preloaded in {time.time() - t_start:.2f} secs")
    return tts_cache


def main():
    """Main function to run the LLM to Audio output streamer."""

    parser = voice_agent_utils.get_cli_argument_parser()
    parser.add_argument("--preload-tts", action="store_true", default=False,
                        help="Preload all TTS models at startup for faster language switching")
    args = parser.parse_args()

    # Warn if user set max_words arguments (they are ignored in translation mode)
    if args.max_words_to_speak_start != 5 or args.max_words_to_speak != 20:
        print(f">> WARNING: --max_words_to_speak_start and --max_words_to_speak are ignored in translation mode.")
        print(f">>          Using TRANSLATION_MAX_WORDS={TRANSLATION_MAX_WORDS} instead.")

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
        gpio_handler.setup(add_interrupt_button=True, add_rotary_dial=True)
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

    # Preload all TTS models if requested
    tts_cache = None
    if args.preload_tts:
        tts_cache = preload_tts_models(LANGUAGE_CONFIGS, verbose=args.verbose)

    # initialize voice agent components
    t1 = time.time()
    print(">> Initializing Voice Agent and components <<")
    va = VoiceAgent(verbose=args.verbose)

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
    print(f">> Initialized AudioToTextInput in {time.time() - start_time:.2f} seconds -- <<")

    va.init_LLmToAudioOutput(
        llm_server_url=args.llm_server_url,
        system_prompt=start_system_prompt,
        start_message=start_ready_message,
        tts_engine=args.tts_engine,
        speaking_rate=args.speaking_rate,
        tts_model_path=start_tts_model_path,
        tts_cache=tts_cache,
        # For translation mode, disable splitting at commas/punctuation
        # Complete sentences (with . ! ?) still speak immediately via get_sentences()
        max_words_to_speak_start=TRANSLATION_MAX_WORDS,
        max_words_to_speak=TRANSLATION_MAX_WORDS,
        split_on_punctuation=False,
        verbose=args.verbose,
        single_turn=True,  # Each translation is independent, no context needed
        printer=agent_interaction_handler
    )
    print(f">> Initialized LLmToAudioOutput in {time.time() - start_time:.2f} seconds -- <<")

    va.start()
    print(f">> Took {time.time()-t1:.2f} secs to initialize Voice Agent <<")

    # full start time to ready
    print(f">> --  Voice Agent ready in {time.time()-start_time:.2f} seconds -- <<")

    # Define interrupt callback
    interrupt_count = {'n': 0}
    def on_output_interrupt():
        """Interrupt agent's speech output and discard pending input."""
        interrupt_count['n'] += 1
        if args.verbose:
            print(f"\n[Interrupted #{interrupt_count['n']}] at {time.time():.2f}")
        va.debug_state("interrupt_start")

        # Acquire stream lock to prevent get_speech_input from starting mic
        # while we're draining audio
        va.input_handler.acquire_stream_lock()
        va.debug_state("interrupt_got_stream_lock")
        try:
            # Interrupt input to discard any partial transcription
            va.input_handler.interrupt()
            va.debug_state("interrupt_after_input_interrupt")

            # Interrupt output to stop speech (includes 0.5s audio drain wait)
            va.output_handler.interrupt()
            va.debug_state("interrupt_after_output_interrupt")

            if hasattr(user_interaction_handler, 'show_interrupted'):
                user_interaction_handler.show_interrupted()

            # Don't clear interrupt_event here - let process_prompt() see it and exit
            # The event will be cleared at the start of next process_prompt() call
            # Don't unmute here either - let the main run() loop handle it
        finally:
            va.input_handler.release_stream_lock()
            va.debug_state("interrupt_released_lock")

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
        key_callbacks = {}
        for key, lang_name in LANGUAGE_KEYS.items():
            key_callbacks[key] = lambda ln=lang_name: va.change_language(LANGUAGE_CONFIGS[ln])

        # Add ENTER for interrupt if --enable_keyboard_control is set
        if args.enable_keyboard_control:
            key_callbacks['enter'] = on_output_interrupt
            print("Keyboard controls: ENTER=interrupt | g=German, s=Spanish, f=French")
        else:
            print("Keyboard controls: g=German, s=Spanish, f=French")

        user_interaction_handler.setup_keyboard_controls(key_callbacks)
    
    # -- rotary switch integration via gpio_handler --
    # Delay to avoid queuing languages during dial turn
    switch_state = {'timer': None}
    SETTLE_DELAY = 0.3
    if gpio_handler:

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
        # Cancel any pending language change timer
        if switch_state.get('timer'):
            switch_state['timer'].cancel()
        # Clean up GPIO handler
        if gpio_handler:
            gpio_handler.cleanup()
        # Clean up interaction handler (handles keyboard listener cleanup too)
        if hasattr(user_interaction_handler, 'cleanup'):
            user_interaction_handler.cleanup()

if __name__ == "__main__":
    main()
