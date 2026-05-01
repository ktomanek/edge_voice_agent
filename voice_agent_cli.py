# CLI for conversational voice agent.
#
# Usage examples:
#
#   python voice_agent_cli.py
#
#   With keyboard controls:
#     python voice_agent_cli.py --enable_keyboard_control
#
#   With GPIO (interrupt button + rotary dial) on Raspberry Pi 5:
#     python voice_agent_cli.py --platform rpi5
#
#   With GPIO (interrupt button + rotary dial) on Orange Pi 5 Pro:
#     python voice_agent_cli.py --platform opi5
#
#   Keyboard controls (when --enable_keyboard_control is set):
#     ENTER          - Interrupt agent output (only while agent is speaking)
#     SPACE          - Toggle microphone mute/unmute
#     g / s / f      - Switch to prompt 1 / 2 / 3 (mirrors rotary dial positions)
#
#   GPIO controls:
#     Interrupt button - Interrupt agent output (only while agent is speaking)
#     Rotary dial      - Switch among the first 3 prompts in prompts.json
#
#   Different interaction handlers:
#     python voice_agent_cli.py --interaction_handler colored           # Rich console (default)
#
#   Verbose mode (debug output):
#     python voice_agent_cli.py --verbose
#
# Exit: Say "goodbye" (voice command)

import threading
import time
start_time = time.time()
print("Loading Voice Agent...")

from voice_agent import VoiceAgent
import voice_agent_utils
from voice_agent_interaction_handlers import get_handler, LoggingHandlerWrapper, create_conversation_log_file
from opi.gpio_utils import POSITION_KEYS

# Rotary dial: 3 positions mapped to the first 3 prompts in prompts.json.
ROTARY_POSITION_TO_PROMPT_INDEX = {
    'pos1': 0,
    'pos2': 1,
    'pos3': 2,
}
ROTARY_SETTLE_DELAY = 0.3

print(f">> -- All imports done in {time.time() - start_time:.2f} seconds -- <<")


def main():
    """Main function to run the LLM to Audio output streamer."""
    
    parser = voice_agent_utils.get_cli_argument_parser()
    args = parser.parse_args()

    voice_agent_utils.apply_audio_device_settings(args)

    # Setup prompt selector (either from file or CLI args)
    prompt_selector = voice_agent_utils.PromptSelector(
        prompt_file=args.prompt_file,
        default_system_prompt=args.system_prompt,
        default_start_message=args.start_message
    )

    # Setup GPIO handler early so we can read the rotary dial for the initial prompt
    gpio_handler = None
    if args.platform:
        from gpio_inputs import RaspberryPi5GPIOHandler, OrangePi5ProGPIOHandler
        if args.platform == 'rpi5':
            gpio_handler = RaspberryPi5GPIOHandler()
        elif args.platform == 'opi5':
            gpio_handler = OrangePi5ProGPIOHandler()
        gpio_handler.setup(add_interrupt_button=True, add_rotary_dial=True)
        print(f">> GPIO handler: {gpio_handler.__class__.__name__}")

    # Pick initial prompt: from rotary dial if available, else random
    initial_prompt = None
    if gpio_handler:
        rotary_pos = gpio_handler.get_current_position()
        idx = ROTARY_POSITION_TO_PROMPT_INDEX.get(rotary_pos)
        if idx is not None and idx < len(prompt_selector.prompts):
            initial_prompt = prompt_selector.prompts[idx]
            print(f">> Initial prompt from rotary dial position '{rotary_pos}': {initial_prompt.get('name', 'unnamed')}")
        else:
            print(f">> No valid rotary position detected (got {rotary_pos!r}), using random prompt")
    if initial_prompt is None:
        initial_prompt = prompt_selector.get_random_prompt()

    t1 = time.time()
    print(">> Initializing Voice Agent <<")
    va = VoiceAgent(verbose=args.verbose)
    va.prompt_selector = prompt_selector  # Store for use on reset

    # Create interaction handlers
    user_interaction_handler = get_handler(args.interaction_handler, "User Input", "blue", is_agent=False)
    agent_interaction_handler = get_handler(args.interaction_handler, "Agent Output", "magenta", is_agent=True)

    # Wrap with logging if requested
    log_file = None
    if args.log_conversation:  # argparse converts --log-conversation to log_conversation
        log_file = create_conversation_log_file()
        user_interaction_handler = LoggingHandlerWrapper(user_interaction_handler, log_file, "USER")
        agent_interaction_handler = LoggingHandlerWrapper(agent_interaction_handler, log_file, "AGENT")
        # Log initial prompt name
        prompt_name = initial_prompt.get('name', 'unnamed')
        log_file.write(f"[PROMPT] {prompt_name}\n")
        log_file.flush()

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
        system_prompt=initial_prompt['system_prompt'],
        start_message=initial_prompt['start_message'],
        tts_engine=args.tts_engine,
        speaking_rate=args.speaking_rate,
        tts_model_path=args.tts_model_path,
        max_words_to_speak_start=args.max_words_to_speak_start,
        max_words_to_speak=args.max_words_to_speak,
        split_on_punctuation=False,
        verbose=args.verbose,
        single_turn=False,  # Conversational agent keeps history
        printer=agent_interaction_handler
    )
    print(f">> Initialized LLmToAudioOutput in {time.time() - start_time:.2f} seconds -- <<")

    va.start()
    print(f">> Took {time.time()-t1:.2f} secs to initialize Voice Agent <<")

    # full start time to ready
    print(f">> --  Voice Agent ready in {time.time()-start_time:.2f} seconds -- <<")

    # Define button callbacks (used by both GPIO button and keyboard)
    button_press_count = {'n': 0}

    def on_interrupt_agent():
        """Interrupt agent's speech output and discard pending input."""
        button_press_count['n'] += 1
        if args.verbose:
            print(f"\n[Interrupt agent #{button_press_count['n']}] at {time.time():.2f}")
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
            # Don't unmute here either - the main run() loop handles it
        finally:
            va.input_handler.release_stream_lock()
            va.debug_state("interrupt_released_lock")

        user_interaction_handler.start()
        if args.verbose:
            print(f"[Interrupt agent #{button_press_count['n']} done]")

    def on_button_press():
        """Button press: only interrupt agent speech (no-op if agent isn't speaking)."""
        if va.output_handler.is_speaking or va.output_handler.is_processing:
            on_interrupt_agent()

    def switch_to_prompt(new_prompt):
        if log_file:
            prompt_name = new_prompt.get('name', 'unnamed')
            log_file.write(f"\n[RESET] [PROMPT] {prompt_name}\n")
            log_file.flush()
        va.full_reset_with_prompt(
            system_prompt=new_prompt['system_prompt'],
            start_message=new_prompt['start_message']
        )

    # Setup GPIO interrupt button via gpio_handler
    if gpio_handler:
        gpio_handler.set_interrupt_callback(on_button_press)
        print(">> GPIO interrupt button enabled (interrupts agent speech only)")

    # -- rotary switch -> prompt selection --
    # Debounce so dial sweeps don't queue multiple prompt switches.
    rotary_state = {'timer': None}
    def switch_to_position(rotary_pos):
        idx = ROTARY_POSITION_TO_PROMPT_INDEX.get(rotary_pos)
        if idx is None or idx >= len(prompt_selector.prompts):
            return
        new_prompt = prompt_selector.prompts[idx]
        if rotary_state['timer'] is not None:
            rotary_state['timer'].cancel()
        rotary_state['timer'] = threading.Timer(
            ROTARY_SETTLE_DELAY, switch_to_prompt, args=[new_prompt]
        )
        rotary_state['timer'].start()

    if gpio_handler:
        gpio_handler.set_position_change_callback(switch_to_position)
        print(f">> Rotary switch listener active (3 positions -> first 3 prompts)")

    # Setup keyboard controls via the interaction handler
    if args.enable_keyboard_control and hasattr(user_interaction_handler, 'setup_keyboard_controls'):
        # Track mute state for toggle
        mute_state = {'is_muted': False}

        def on_mute_toggle():
            if mute_state['is_muted']:
                va.unmute_microphone()
                mute_state['is_muted'] = False
                print("\r\033[K🎤 Microphone ACTIVE")
            else:
                va.mute_microphone()
                mute_state['is_muted'] = True
                print("\r\033[K🔇 Microphone MUTED")

        key_callbacks = {
            'enter': on_button_press,
            'space': on_mute_toggle,
        }
        # Bind g/s/f (or whatever POSITION_KEYS defines) to switch prompts,
        # mirroring the rotary dial.
        for key, pos in POSITION_KEYS.items():
            key_callbacks[key] = lambda p=pos: switch_to_position(p)

        user_interaction_handler.setup_keyboard_controls(key_callbacks)

        keys_str = "/".join(k.upper() for k in POSITION_KEYS)
        print(f"Keyboard controls: ENTER=interrupt | SPACE=mute/unmute | {keys_str}=switch prompt")

    # Run the voice agent
    try:
        va.run()
    finally:
        # Cancel any pending rotary debounce timer
        if rotary_state.get('timer'):
            rotary_state['timer'].cancel()
        # Clean up GPIO handler
        if gpio_handler:
            gpio_handler.cleanup()
        # Clean up interaction handler (handles keyboard listener cleanup too)
        if hasattr(user_interaction_handler, 'cleanup'):
            user_interaction_handler.cleanup()
        # Close log file
        if log_file:
            log_file.close()

if __name__ == "__main__":
    main()
