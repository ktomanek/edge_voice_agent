# example for voice translation agent
#
# Supports language switching by eiher keyboard shortcuts or with 
# rotary dial on GPIO pins (Raspberry Pi etc)
#
# Usage examples:
#
#   Basic (with keyboard language switching):
#     python voice_translate_cli.py
#
#   Language switching keys:
#     g = German    (speaks "Bereit!")
#     s = Spanish   (speaks "Listo!")
#     a = Arabic    (speaks "Mustaeidd!")
#     f = French    (speaks "Pret!")
##
#   Verbose mode (debug output):
#     python voice_translate_cli.py --verbose
#
#   On Raspberry Pi with rotary switch:
#     - GPIO pins 0, 5, 6, 26 for language selection
#     - Both keyboard and rotary switch work simultaneously
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

# Try to import GPIO (only available on Raspberry Pi)
try:
    from gpiozero import Button
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False

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

# GPIO pin to language mapping (for rotary switch)
GPIO_LANGUAGE_MAP = {
    1: 'german',   # Pin 0
    2: 'spanish',  # Pin 5
    3: 'arabic',   # Pin 6
    4: 'french',   # Pin 26
}

DEFAULT_OUTPUT_LANGUAGE = 'spanish'

def main():
    """Main function to run the LLM to Audio output streamer."""
    
    parser = voice_agent_utils.get_cli_argument_parser()
    args = parser.parse_args()



    t1 = time.time()
    print(">> Initializing user interaction and controls <<")

    # Create interaction handlers
    user_interaction_handler = get_handler(args.interaction_handler, "User Input", "blue", is_agent=False)
    agent_interaction_handler = get_handler(args.interaction_handler, "Agent Output", "magenta", is_agent=True)


    # -- Setup GPIO rotary switch (if available) --
    switches = None
    if GPIO_AVAILABLE:
        db_time = 0.05
        switches = {
            1: Button(0, pull_up=True, bounce_time=db_time),
            2: Button(5, pull_up=True, bounce_time=db_time),
            3: Button(6, pull_up=True, bounce_time=db_time),
            4: Button(26, pull_up=True, bounce_time=db_time)
        }
        print(">> GPIO rotary switch detected.")

    # Read rotary dial position (or use default if not connected)
    def get_current_rotary_language():
        """Returns the language name based on current rotary switch position."""
        if switches:
            for pos, btn in switches.items():
                if btn.is_pressed:
                    return GPIO_LANGUAGE_MAP.get(pos)
        return None

    initial_language = get_current_rotary_language()
    if initial_language is None:
        initial_language = DEFAULT_OUTPUT_LANGUAGE
        print(f">> No rotary position detected, using default: {initial_language.upper()}")
    else:
        print(f">> Initial language from rotary dial: {initial_language.upper()}")
    print(f">> Took {time.time()-t1:.2f} secs to initialize interaction and controls <<")


    # get startup language
    start_config = LANGUAGE_CONFIGS[initial_language]
    start_start_message = start_config["ready_message"]
    start_tts_model_path = start_config["tts_model"]



    # initialize voice agent components
    t1 = time.time()
    print(">> Initializing Voice Agent and components <<")
    va = VoiceAgent()

    va.init_LLmToAudioOutput(
        llm_server_url=args.llm_server_url,
        system_prompt="",
        start_message=start_start_message,
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

    # Setup GPIO interrupt button if handler has one
    if hasattr(agent_interaction_handler, '_gpio_button') and agent_interaction_handler._gpio_button is not None:
        agent_interaction_handler._gpio_button.when_pressed = on_output_interrupt
        print("GPIO interrupt button enabled")

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
    
    # -- rotary switch integration (reuse switches from earlier init) --
    if GPIO_AVAILABLE and switches:
        # Delay to avoid queuing languages
        switch_state = {'timer': None}
        SETTLE_DELAY = 0.3  # Wait before loading

        def check_position():
            for pos, btn in switches.items():
                if btn.is_pressed:
                    lang_name = GPIO_LANGUAGE_MAP.get(pos)
                    if switch_state['timer'] is not None:
                        switch_state['timer'].cancel()
                    if lang_name and lang_name in LANGUAGE_CONFIGS:
                        switch_state['timer'] = threading.Timer(SETTLE_DELAY, va.change_language, args=[LANGUAGE_CONFIGS[lang_name]])
                        switch_state['timer'].start()
                    return

        # Assign callbacks (gpiozero runs these in a background thread automatically)
        for btn in switches.values():
            btn.when_pressed = check_position

        print(">> Rotary switch listener active.")
        # Check initial position on startup
        check_position()
    else:
        print(">> GPIO not available, rotary switch disabled (use keyboard: g/s/a/f)")
    # -- rotary switch integration --

    # Run the voice agent
    try:
        va.run()
    finally:
        # Clean up handler (handles keyboard listener cleanup too)
        if hasattr(user_interaction_handler, 'cleanup'):
            user_interaction_handler.cleanup()

if __name__ == "__main__":
    main()
