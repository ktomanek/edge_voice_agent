# CLI for voice agent
# Default settings meant to be run on tiny screen (Raspberry Pi)

import time
start_time = time.time()
print("Loading voice_agent_cli.py")

import threading
import sys
import os

import select
from voice_agent import VoiceAgent
import voice_agent_utils

print(f"Imports: in {time.time() - start_time} seconds")

# Only import termios on platforms that support it (Unix/Linux/macOS)
try:
    import termios
    import tty
    import fcntl
    TERMIOS_AVAILABLE = True
except ImportError:
    TERMIOS_AVAILABLE = False

def print_mute_status(is_muted):
    """Print the current mute status."""
    sys.stdout.write("\r\033[K")  # Clear the current line
    if is_muted:
        sys.stdout.write("🔇 Microphone MUTED (press SPACE to unmute)\n")
    else:
        sys.stdout.write("🎤 Microphone ACTIVE (press SPACE to mute)\n")
    sys.stdout.flush()

def keyboard_listener(voice_agent, stop_event):
    """Listen for keyboard events to toggle mute using termios (Unix systems only)."""
    if not TERMIOS_AVAILABLE:
        print("Keyboard control not available on this platform")
        return

    is_muted = False
    print("\n🎤 Microphone ACTIVE (press SPACE to mute, ESC to exit)")
    
    # Save original terminal settings
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    old_flags = fcntl.fcntl(fd, fcntl.F_GETFL)
    
    try:
        # Set terminal to raw mode to get individual key presses
        tty.setraw(fd, termios.TCSANOW)
        # Set non-blocking mode
        fcntl.fcntl(fd, fcntl.F_SETFL, old_flags | os.O_NONBLOCK)
        
        while not stop_event.is_set():
            # Check if there's input available (non-blocking)
            r, _, _ = select.select([fd], [], [], 0.1)
            
            if r:
                # Read a single character
                key = sys.stdin.read(1)
                
                # Check for space key (ASCII 32)
                if key == ' ':
                    if is_muted:
                        voice_agent.unmute_microphone()
                        is_muted = False
                    else:
                        voice_agent.mute_microphone()
                        is_muted = True
                    print_mute_status(is_muted)
                # Check for ESC key (ASCII 27)
                elif key == '\x1b':
                    voice_agent.trigger_stop_events()
                    stop_event.set()
            
            time.sleep(0.01)  # Small sleep to reduce CPU usage
    
    except Exception as e:
        print(f"Error in keyboard handling: {e}")
    
    finally:
        # Restore terminal settings
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        fcntl.fcntl(fd, fcntl.F_SETFL, old_flags)

def main():
    """Main function to run the LLM to Audio output streamer."""
    
    parser = voice_agent_utils.get_cli_argument_parser()
    args = parser.parse_args()

    t1 = time.time()
    print(">> Initializing Voice Agent <<")
    va = VoiceAgent()

    va.init_LLmToAudioOutput(
        llm_server_url=args.llm_server_url,
        system_prompt=args.system_prompt,
        start_message=args.start_message,
        tts_engine=args.tts_engine,
        speaking_rate=args.speaking_rate,
        tts_model_path=args.tts_model_path,
        max_words_to_speak_start=args.max_words_to_speak_start,
        max_words_to_speak=args.max_words_to_speak,
        verbose=args.verbose
    )


    va.init_AudioToText(
        asr_model_name=args.asr_model_name,
        language=args.language,
        min_partial_duration=args.min_partial_duration,
        end_of_utterance_duration=args.end_of_utterance_duration,
        verbose=args.verbose
    )
    va.start()
    print(f">> Took {time.time()-t1} secs to initialize Voice Agent <<")

    # full start time to ready
    print(f"------> Voice Agent ready in {time.time()-start_time} seconds")
    

    # Setup keyboard control if enabled
    keyboard_thread = None
    stop_event = threading.Event()
    
    if args.enable_keyboard_control and TERMIOS_AVAILABLE:
        # Start keyboard listener in a separate thread
        keyboard_thread = threading.Thread(
            target=keyboard_listener, 
            args=(va, stop_event), 
            daemon=True
        )
        keyboard_thread.start()
    
    # Run the voice agent
    try:
        va.run()
    finally:
        # Clean up
        if keyboard_thread and keyboard_thread.is_alive():
            stop_event.set()
            keyboard_thread.join(timeout=1.0)

if __name__ == "__main__":
    main()
