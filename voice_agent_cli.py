# CLI for conversational voice agent.
#
# Usage examples:
#
#   python voice_agent_cli.py
#
#   With keyboard controls:
#     python voice_agent_cli.py --enable_keyboard_control
#
#   Keyboard controls (when enabled):
#     ENTER - Interrupt agent output (stops current speech and returns to listening)
#     SPACE - Toggle microphone mute/unmute
#
#   Different interaction handlers:
#     python voice_agent_cli.py --interaction_handler colored           # Rich console (default)
#
#   Verbose mode (debug output):
#     python voice_agent_cli.py --verbose
#
# Exit: Say "goodbye" (voice command)

import time
start_time = time.time()
print("Loading Voice Agent...")

import sys
from voice_agent import VoiceAgent
import voice_agent_utils
from voice_agent_interaction_handlers import get_handler

print(f">> -- All imports done in {time.time() - start_time:.2f} seconds -- <<")


def main():
    """Main function to run the LLM to Audio output streamer."""
    
    parser = voice_agent_utils.get_cli_argument_parser()
    args = parser.parse_args()

    t1 = time.time()
    print(">> Initializing Voice Agent <<")
    va = VoiceAgent()

    # Create interaction handlers
    user_interaction_handler = get_handler(args.interaction_handler, "User Input", "blue", is_agent=False)
    agent_interaction_handler = get_handler(args.interaction_handler, "Agent Output", "magenta", is_agent=True)

    va.init_LLmToAudioOutput(
        llm_server_url=args.llm_server_url,
        system_prompt=args.system_prompt,
        start_message=args.start_message,
        tts_engine=args.tts_engine,
        speaking_rate=args.speaking_rate,
        tts_model_path=args.tts_model_path,
        max_words_to_speak_start=args.max_words_to_speak_start,
        max_words_to_speak=args.max_words_to_speak,
        verbose=args.verbose,
        single_turn=args.single_turn,
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

    # Define interrupt callback (used by both GPIO button and keyboard)
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

    # Setup GPIO button if handler has one (works without --enable_keyboard_control)
    if hasattr(agent_interaction_handler, '_gpio_button') and agent_interaction_handler._gpio_button is not None:
        agent_interaction_handler._gpio_button.when_pressed = on_output_interrupt
        print("GPIO interrupt button enabled")

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
            'enter': on_output_interrupt,
            'space': on_mute_toggle,
        }

        user_interaction_handler.setup_keyboard_controls(key_callbacks)

        print("Keyboard controls: ENTER=interrupt | SPACE=mute/unmute")

    # Run the voice agent
    try:
        va.run()
    finally:
        # Clean up handler (handles keyboard listener cleanup too)
        if hasattr(user_interaction_handler, 'cleanup'):
            user_interaction_handler.cleanup()

if __name__ == "__main__":
    main()
