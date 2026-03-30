# Fully offline running voice agent.
#
# Uses OpenAI-compatible format to connect to LLM. For now, we assume the LLM is self-hosted via LLama.cpp (see script to
# start server). Currently, we do not support cloud-hosted LLMs (API key/model name ignored so far, but should be an easy change).
# Supports several on-device runnable tts-engines and asr models.
# Defaults are set for smallest models so that it can run on edge devices like Raspberry Pi 5.

import time
start_time = time.time()

import json
import queue
import signal
import sounddevice as sd
import sys
import threading
import time

from captioning_lib import captioning_utils
from tts_lib import tts_engines

from llm_client import LLMClient

import pysbd
nlp = pysbd.Segmenter(language="en", clean=False)
def get_sentences(text):
    return nlp.segment(text)

import re
import voice_agent_utils
from voice_agent_interaction_handlers import ColoredHandler


class LLmToAudio:
    """Generate LLM output based on prompt and stream into TTS output."""

    def show_llm_model_info(self):
        models = self.llm_client.models.list()
        
        # For now we are assuming that the LLM is self-hosted via LLama.cpp, so there really is only
        # one model. Double check and show info about the model.
        if not models.data:
            raise ValueError("No models found at LLM server.")
        elif len(models.data) != 1:
            raise ValueError("More than one model found at LLM server.")

        model = models.data[0]        
        print(f"LLM: {model.id}, via: {model.owned_by}")


    def __init__(self,
                 llm_server_url=voice_agent_utils.DEFAULT_LLM_SERVER_URL,
                 system_prompt=voice_agent_utils.DEFAULT_SYSTEM_PROMPT,
                 start_message=voice_agent_utils.DEFAULT_START_MESSAGE,
                 tts_engine='piper',
                 speaking_rate=1.0, # higher numbers means faster
                 tts_model_path=None,
                 tts_cache=None,  # pre-loaded TTS models dict {model_path: tts_instance}
                 max_words_to_speak_start=5,  # make sure that we get to speak quickly at the beginning
                 max_words_to_speak=15, # later speak at last after this many words, or when a sentence is finished
                 verbose=False,
                 printer=None,
                 single_turn=False
                 ):
        """Initialize the streamer with Piper and LLM models."""
        self.verbose = verbose
        self.single_turn = single_turn
        
        # Init TTS
        self.max_words_to_speak_start = max_words_to_speak_start
        self.max_words_to_speak = max_words_to_speak
        assert self.max_words_to_speak_start <= self.max_words_to_speak

        t1 = time.time()
        # Check if model is already in pre-loaded cache
        if tts_cache and tts_model_path and tts_model_path in tts_cache:
            print(f'Using pre-loaded TTS model: {tts_model_path}')
            self.tts = tts_cache[tts_model_path]
        elif tts_engine == 'piper':
            print('Initializing Piper TTS')
            if tts_model_path:
                self.tts = tts_engines.TTS_Piper(tts_model_path, warmup=False)
                print(f"Using tts model: {tts_model_path}")
            else:
                self.tts = tts_engines.TTS_Piper(warmup=False)
                print(f"Using default Piper model: {self.tts.model_path}")
        elif tts_engine == 'kokoro':
            print('Initializing Kokoro TTS')
            if tts_model_path:
                print(f"Initializing with tts model: {tts_model_path}")
                self.tts = tts_engines.TTS_Kokoro(tts_model_path)
            else:
                self.tts = tts_engines.TTS_Kokoro()
        else:
            raise ValueError('Unknown tts engine.')
        self.sample_rate = self.tts.get_sample_rate()
        self._info(f"Using sample rate: {self.sample_rate} Hz")
        self.speaking_rate = speaking_rate
        self._info(f"Using speaking rate: {self.speaking_rate}")
        print(f"> TTS initialized in {time.time()-t1:.2f} secs.")

        # Cache for TTS models to avoid reloading on language switch
        # Use pre-loaded cache if provided, otherwise start fresh
        self._tts_cache = tts_cache if tts_cache is not None else {}
        if tts_model_path:
            self._tts_cache[tts_model_path] = self.tts

        # increase buffer size if needed, esp on slower devices like raspberry pi
        self.audio_buffer_size = 2048

        ## Init LLM and prompts
        self.llm_server_url = llm_server_url
        self.llm_client = LLMClient(base_url=llm_server_url, api_key=voice_agent_utils.DEFAULT_LLM_SERVER_API_KEY)
        self.llm_client.wait_for_ready(max_retries=30, retry_delay=1.0)
        self.system_prompt = system_prompt
        self.start_message = start_message
        self.messages = [
            {'role': 'system', 'content': self.system_prompt},
        ]
        self.show_llm_model_info()

        # Warm up LLM
        t1 = time.time()
        _ = self.llm_client.chat.completions.create(
            model="mymodel",  # This can be any string
            messages=[{"role": "user", "content": "hi"}],
            stream=False
        )
        print(f"LLM warmed up in {time.time()-t1:.2f} secs.")


        # Printer
        if not printer:
            self.assistant_printer = ColoredHandler("Agent Output", "magenta")
        else:
            self.assistant_printer = printer

        self.audio_stream = None

        # Text processing
        self.text_buffer = ""
        self.sentence_queue = queue.Queue()
        self.is_processing = False
        self.is_speaking = False

        # Thread handlers
        self.stop_event = threading.Event()
        self.interrupt_event = threading.Event()
        self.lock = threading.Lock()

        # Signal handlers for graceful termination
        if threading.current_thread() is threading.main_thread():
            self._info('>>> setting up signal handlers')
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)

    
    def start(self):
        """Start and restart the agent."""
        # Reset LLM context
        self.messages = [
            {'role': 'system', 'content': self.system_prompt},
        ]

        # Text processing
        self.text_buffer = ""
        self.sentence_queue = queue.Queue()
        self.is_processing = False
        self.is_speaking = False

        # marker for first words spoken
        self.first_speech_fragment_finalized = False
        self.time_llm_gen_started = time.time()
        self.first_chunk_emitted = False


    def stop(self):
        """Stop agent."""
        self.stop_event.clear()

        # Reset text buffers and queues
        while not self.sentence_queue.empty():
            self.sentence_queue.get_nowait()
            self.sentence_queue.task_done()

        # Clear states
        self.messages = []
        self.text_buffer = ""

    def interrupt(self):
        """Interrupt current speech and return to listening."""
        self.interrupt_event.set()

        # Print and clear sentence queue - show user what was going to be said
        with self.lock:
            while not self.sentence_queue.empty():
                try:
                    sentence = self.sentence_queue.get_nowait()
                    # Print the unspoken text so user can see it
                    self.assistant_printer.print(sentence, partial=False)
                    self.sentence_queue.task_done()
                except:
                    pass
            # Print any remaining text in buffer
            if self.text_buffer.strip():
                self.assistant_printer.print(self.text_buffer, partial=False)
            self.text_buffer = ""

            # Abort audio stream to stop playback immediately
            if self.audio_stream:
                try:
                    if self.audio_stream.active:
                        self.audio_stream.abort()
                        self._info("Audio stream aborted after interrupt")
                except Exception as e:
                    self._info(f"Error aborting audio stream: {e}")
            # Note: Don't close/nullify the stream - it will be restarted on next speak

        self.is_speaking = False
        self.is_processing = False

        # Wait for system audio buffer to fully drain to prevent mic picking up residual audio
        # 0.5s should be enough for speakers to go silent
        time.sleep(0.5)


    def shutdown(self):
        """Close all resources."""
        if self.audio_stream:
            self._info("Closing audio stream...")
            self.audio_stream.stop()
            self.audio_stream.close()
            self.audio_stream = None


    def _clean_llm_output(self, text):
        """
        Remove formatting symbols we don't want to be spoken.
        """
        text = text.replace('*', ' ')
        # Remove weird newlines after punctuation (tiny LLMs often do this)
        # But keep newlines after complete items (for lists)
        text = re.sub(r',\s*\n', ', ', text)  # comma + newline -> comma + space
        text = re.sub(r':\s*\n', ': ', text)  # colon + newline -> colon + space
        text = re.sub(r';\s*\n', '; ', text)  # semicolon + newline -> semicolon + space
        # Collapse multiple spaces into one
        text = re.sub(r' +', ' ', text)
        # Remove emojis using regex (faster than emoji library)
        text = re.sub(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\U00002702-\U000027B0\U000024C2-\U0001F251]+', '', text)
        return text
            
    def _info(self, text):
        if self.verbose:
            print(text)

    def _signal_handler(self, sig, frame):
        """Handle termination signals gracefully."""
        self._info("\nReceived termination signal. Shutting down...")
        self.stop_event.set()
        self.shutdown()
        sys.exit(0)
    
    def _start_audio_stream(self):
        """Initialize and start the audio output stream."""
        with self.lock:
            try:
                if self.audio_stream is None:
                    self.audio_stream = sd.OutputStream(
                        samplerate=self.sample_rate,
                        blocksize=self.audio_buffer_size,
                        channels=1,
                        dtype='int16'
                    )
                    self.audio_stream.start()
                    self._info("Audio stream created and started")
                elif not self.audio_stream.active:
                    try:
                        # Restart stopped stream
                        self.audio_stream.start()
                        self._info("Audio stream restarted")
                    except sd.PortAudioError:
                        # Stream is in bad state, recreate it
                        self._info("Stream in bad state, recreating...")
                        try:
                            self.audio_stream.close()
                        except:
                            pass
                        self.audio_stream = sd.OutputStream(
                            samplerate=self.sample_rate,
                            blocksize=self.audio_buffer_size,
                            channels=1,
                            dtype='int16'
                        )
                        self.audio_stream.start()
                        self._info("Audio stream recreated")
            except Exception as e:
                self._info(f"Error with audio stream: {e}")
    
    def _start_sentence_processor(self):
        """Start a background thread to process sentences."""
        if self.is_processing:
            return
            
        self.is_processing = True
        threading.Thread(target=self._process_sentences, daemon=True).start()
        
    def _get_max_buffer_words_before_speaking(self):
        # If unspoken text buffer is getting long until first sentence break observed, we will need to
        # create a artificial break to ensure latency doesn't get too big.
        # This is more critical at the beginning of a response, before we have started speaking, where
        # the goal is to minimize time to speech onset.
        if not self.first_speech_fragment_finalized:
            return self.max_words_to_speak_start
        else:
            return self.max_words_to_speak

    def _has_natural_break_point(self, text):
        """Check if text has natural break points like punctuation marks followed by space or newlines."""
        break_patterns = ['\n', ', ', '; ', ': ', '! ', '? ', '. ', ' - ', ' – ', ' — ']
        return any(pattern in text for pattern in break_patterns)

    def _process_text_chunk(self, text_chunk):
        """Process a chunk of text from LLM.
        
        Decide when to put in the speak queue based on sentence end detection on max chunk size."""
        if self.stop_event.is_set():
            return
            
        if not text_chunk:
            return

        with self.lock:
            self.text_buffer += text_chunk
            self.text_buffer_words = self.text_buffer.split()
            
            # find complete sentences
            try:
                sentences = get_sentences(self.text_buffer)
                if len(sentences) > 1:
                    complete_sentences = sentences[:-1]
                    
                    # Keep the last (potentially incomplete) sentence in buffer
                    self.text_buffer = sentences[-1]

                    # Add complete sentences to the queue
                    for sentence in complete_sentences:
                        if sentence.strip():
                            self.sentence_queue.put(sentence)
                            self.assistant_printer.print(sentence, partial=False)
                            self._info(f"Queued full sentence: {sentence}")
                            if not self.first_speech_fragment_finalized:
                                self.time_to_first_speech_fragment = time.time() - self.time_llm_gen_started 
                                self._info(f"\n>> Time to first speech fragment (organic): {self.time_to_first_speech_fragment:.2f} seconds")
                            self.first_speech_fragment_finalized = True

                elif (len(self.text_buffer_words) > self._get_max_buffer_words_before_speaking() or 
                      (self._has_natural_break_point(self.text_buffer) and len(self.text_buffer_words) >= 1)):
                    # Look for natural break points
                    break_points = [
                        self.text_buffer.rfind('\n'),  # newlines are strong break points
                        self.text_buffer.rfind(', '),
                        self.text_buffer.rfind(' - '),
                        self.text_buffer.rfind(': '),
                        self.text_buffer.rfind('; '),
                        self.text_buffer.rfind('. '),
                        self.text_buffer.rfind('! '),
                        self.text_buffer.rfind('? '),
                        self.text_buffer.rfind(' ')
                    ]
                    
                    # Find the best break point
                    break_point = max(break_points)
                    
                    fragment = self.text_buffer[:break_point+1]
                    self.text_buffer = self.text_buffer[break_point+1:]
                    self.sentence_queue.put(fragment)
                    self.assistant_printer.print(fragment, partial=False)
                    self._info(f"Queued fragment: {fragment}")
                    if not self.first_speech_fragment_finalized:
                        self.time_to_first_speech_fragment = time.time() - self.time_llm_gen_started 
                        self._info(f"\n>> Time to first speech fragment (punctuation): {self.time_to_first_speech_fragment:.2f} seconds")

                    self.first_speech_fragment_finalized = True

            except Exception as e:
                print(f"Error in sentence detection: {e}")
        
        # Ensure the sentence processor is running
        if not self.is_processing:
            self._start_sentence_processor()
    
    def _process_sentences(self):
        """Process sentences from the queue and speak them."""
        self._start_audio_stream()

        try:
            while not self.stop_event.is_set() and not self.interrupt_event.is_set():
                try:
                    sentence = self.sentence_queue.get(timeout=0.5)

                    # Wait until not speaking to avoid overlap
                    while self.is_speaking and not self.stop_event.is_set() and not self.interrupt_event.is_set():
                        time.sleep(0.05)
                    
                    if self.stop_event.is_set() or self.interrupt_event.is_set():
                        break

                    # Speak new sentence
                    self._speak_sentence(sentence, speed=self.speaking_rate)
                    self.sentence_queue.task_done()

                except queue.Empty:
                    if self.sentence_queue.empty() and not self.text_buffer and not self.is_speaking:
                        break

        finally:
            self.is_processing = False

            # If there are still sentences and we're not stopped/interrupted, restart processor
            if not self.sentence_queue.empty() and not self.stop_event.is_set() and not self.interrupt_event.is_set():
                self._start_sentence_processor()
    
    def _speak_sentence(self, text, speed=1.0, noise_scale=0.667, noise_w=0.8, wait_for_completion=False):
        """Synthesize and play a sentence with TTS model."""
        if not text.strip():
            return

        # Check for interrupt before speaking
        if self.interrupt_event.is_set():
            return

        self.is_speaking = True

        try:
            self._info(f"Speaking: {text}")
            audio_data, sample_rate = self.tts.synthesize(
                text, target_sr = self.sample_rate,
                speaking_rate=speed, return_as_int16=True)

            # Check again before writing
            if self.interrupt_event.is_set():
                return

            # Ensure stream is ready before writing
            self._start_audio_stream()
            with self.lock:
                if self.audio_stream is None or not self.audio_stream.active:
                    self._info("Audio stream not ready, skipping write")
                    return

            # Write audio (outside lock to avoid blocking)
            try:
                self.audio_stream.write(audio_data)
                # Optionally wait for audio to finish playing
                if wait_for_completion:
                    audio_duration = len(audio_data) / self.sample_rate
                    time.sleep(audio_duration)
            except Exception as e:
                if not self.interrupt_event.is_set():
                    self._info(f"Error writing audio: {e}")
        except Exception as e:
            if not self.interrupt_event.is_set():
                self._info(f"Error during speech: {e}")
        finally:
            self.is_speaking = False

    def _finish_processing(self):
        """Process any remaining text in the buffer."""
        if self.interrupt_event.is_set():
            return

        with self.lock:
            if self.text_buffer.strip():
                self.sentence_queue.put(self.text_buffer)
                self.assistant_printer.print(self.text_buffer, partial=False)
                self.text_buffer = ""

        # Ensure processor is running if there's something in the queue
        if not self.sentence_queue.empty() and not self.is_processing:
            self._start_sentence_processor()

        # Wait for sentence queue to empty (with interrupt check)
        while self.sentence_queue.qsize() > 0 and not self.interrupt_event.is_set():
            self._info(f"Waiting for {self.sentence_queue.qsize()} pending sentences...")
            time.sleep(0.1)

        if self.interrupt_event.is_set():
            return

        # Wait for is_speaking to become False (audio write finished)
        while self.is_speaking and not self.interrupt_event.is_set():
            time.sleep(0.05)

        # Wait for sentence processor to finish
        while self.is_processing and not self.interrupt_event.is_set():
            time.sleep(0.05)

        # Stop (but don't close) the audio stream - it will be reused
        with self.lock:
            if self.audio_stream:
                try:
                    if self.audio_stream.active:
                        self.audio_stream.stop()
                        self._info("Audio output stream stopped")
                except Exception as e:
                    self._info(f"Error stopping audio stream: {e}")

        # Give a moment for system audio buffer to fully drain
        time.sleep(0.3)
    

    def process_prompt(self, user_prompt):
        """Process a prompt through LLM and stream to Piper."""

        if self.single_turn:
            self.messages = [{'role': 'system', 'content': self.system_prompt}]

        self.messages.append({'role': 'user', 'content': user_prompt})

        if self.verbose:
            self._info(f">> context length: turns: {len(self.messages) / 2}")
            self._info(f">> context length: characters: {len(json.dumps(self.messages))}")

            pretty_json = json.dumps(self.messages, indent=2)
            self._info(f">> Sending prompt to {self.llm_server_url}: {pretty_json}")


        # Wait for any previous processor to finish (max 1 second)
        wait_count = 0
        while self.is_processing and wait_count < 20:
            time.sleep(0.05)
            wait_count += 1
        if self.is_processing:
            self._info("Warning: previous processor still running, forcing reset")

        # reset all state for new turn
        self.interrupt_event.clear()
        self.is_speaking = False
        self.is_processing = False
        self.text_buffer = ""

        # Clear any leftover sentences from previous turn
        with self.lock:
            while not self.sentence_queue.empty():
                try:
                    self.sentence_queue.get_nowait()
                except:
                    pass

        self.assistant_printer.start()
        self.assistant_printer.show_idle('thinking...')

        self.first_speech_fragment_finalized = False
        self.time_llm_gen_started = time.time()
        self.first_chunk_emitted = False

        # For single_turn mode, disable prompt caching to avoid stale context
        extra_params = {}
        if self.single_turn:
            extra_params = {"cache_prompt": False, "n_keep": 0}

        llm_response_stream = self.llm_client.chat.completions.create(
            model=voice_agent_utils.DEFAULT_LLM_SERVER_MODEL,
            messages=self.messages,
            stream=True,
            **extra_params
        )
        text_chunks = []
        for chunk in llm_response_stream:
            if not self.first_chunk_emitted:
                self.first_chunk_emitted = True
                self.time_to_first_token = time.time() - self.time_llm_gen_started
                self._info(f"\n>> Time to first token: {self.time_to_first_token:.2f} seconds")

            if self.stop_event.is_set() or self.interrupt_event.is_set():
                break

            if chunk.choices and chunk.choices[0].delta.content:
                text_chunk = chunk.choices[0].delta.content
                self.assistant_printer.show_idle()

                # remove asterisks and other formatting info from the text
                text_chunk = self._clean_llm_output(text_chunk)

                self._process_text_chunk(text_chunk)            
                text_chunks.append(text_chunk)

        # Skip final processing if interrupted
        if self.interrupt_event.is_set():
            self._info(">> Interrupted, skipping finish processing")
            return

        assistant_response = ''.join(text_chunks)
        self.messages.append({'role': 'assistant', 'content': assistant_response})

        # Process any remaining text
        self._finish_processing()

    def update_language_context(self, tts_model_path, new_system_prompt):
        """Dynamically load a new TTS model and update the LLM prompt."""
        t_start = time.time()

        with self.lock:
            # Close old audio stream (sample rate may have changed)
            if self.audio_stream is not None:
                try:
                    self.audio_stream.close()
                except:
                    pass
                self.audio_stream = None

            # Clear any remaining buffers
            self.text_buffer = ""
            while not self.sentence_queue.empty():
                try:
                    self.sentence_queue.get_nowait()
                except:
                    pass

            # Check if model is already cached
            if tts_model_path in self._tts_cache:
                self._info(f"Using cached TTS model: {tts_model_path}")
                self.tts = self._tts_cache[tts_model_path]
            else:
                # Load new model and cache it
                self._info(f"Loading new TTS model: {tts_model_path}")
                new_tts = tts_engines.TTS_Piper(tts_model_path, warmup=False)
                self._tts_cache[tts_model_path] = new_tts
                self.tts = new_tts

            self.sample_rate = self.tts.get_sample_rate()
            print(f">> TTS model switched in {time.time() - t_start:.2f} secs")

            # Update the prompt and wipe the conversation history
            self.system_prompt = new_system_prompt
            self.messages = [{'role': 'system', 'content': self.system_prompt}]

            # Reset processing state
            self.is_speaking = False
            self.is_processing = False
            self._info("Reset all states and context...")


class AudioToText:
    """Stream from audio and transcribe."""

    def __init__(self, asr_model_name,
                 asr_model_path=None,
                 disable_partials=True,
                 language='en',
                 end_of_utterance_duration=0.5,
                 min_partial_duration=0.2,
                 max_segment_duration=15,
                 verbose=False,
                printer=None):

        self.verbose = verbose
        self.language = language
        self.end_of_utterance_duration = end_of_utterance_duration

        self.min_partial_duration = min_partial_duration
        self.max_segment_duration = max_segment_duration
        self.disable_partials = disable_partials
        
        if not printer:
            self.caption_printer = ColoredHandler("User Input", "blue")
        else:
            self.caption_printer = printer

        # For audio input
        self.input_device = captioning_utils.find_default_input_device()
        self._info(f"Using default audio input device: {self.input_device}")
        self.device_index = self.input_device['index']

        # Audio buffer
        self.audio_queue = queue.Queue(maxsize=1000)
        self.input_audio_stream = None

        # Load models
        t1 = time.time()
        self.vad = captioning_utils.get_vad(eos_min_silence=200)
        print(f"VAD model loaded in {time.time()-t1:.2f} secs.")    
        
        t1 = time.time()
        self.asr_model = captioning_utils.load_asr_model(
            model_name=asr_model_name,
            model_path=asr_model_path,
            language=self.language,
            sampling_rate=16000,
            show_word_confidence_scores=False)
        print(f"ASR model '{asr_model_name}' loaded in {time.time()-t1:.2f} secs.")

        # Transcription thread
        self.stop_event = threading.Event()
        self.interrupt_event = threading.Event()  # For aborting current input
        self.transcription_handler = captioning_utils.TranscriptionWorker(
            sampling_rate=captioning_utils.SAMPLING_RATE)

        
    def start(self):

        # Initialize audio stream with callback mode for better performance
        # Use low latency for responsive conversation on voice agent
        self.input_audio_stream = captioning_utils.get_audio_stream_callback(
            audio_queue=self.audio_queue,
            input_device_index=self.device_index,
            target_latency=0.5  # Balance between responsiveness and stability on RPi
        )

        # Set stop flag and transcriber thread
        self.stop_event.clear()
        self.transcriber = threading.Thread(target=self.transcription_handler.transcription_worker,
                                    kwargs={'vad': self.vad,
                                            'asr': self.asr_model,
                                            'audio_queue': self.audio_queue,
                                            'caption_printer': self.caption_printer,
                                            'stop_threads': self.stop_event,
                                            'min_partial_duration': self.min_partial_duration,
                                            'max_segment_duration': self.max_segment_duration,
                                            'disable_partials': self.disable_partials})
        self.transcriber.daemon = True
        self.transcriber.start()


    def stop(self):

        # Stop audio stream
        if self.input_audio_stream:
            if self.input_audio_stream.active:
                self.input_audio_stream.stop()
            self.input_audio_stream.close()
        
        # Set stop flag
        self.stop_event.set()

        # Clear audio buffer
        try:
            while True:
                self.audio_queue.get_nowait()
        except queue.Empty:
            pass

        # Stop transcriber thread
        if self.transcriber and self.transcriber.is_alive():
            self.transcriber.join(timeout=3.0)   
            if self.transcriber.is_alive():
                raise Exception("Transcriber thread not stopped within timeout.")
        self.transcription_handler.reset()

        # Reset VAD states
        self.vad.reset_states()


    def mute(self):
        """Temporarily stop the audio input stream without destroying it"""
        if self.input_audio_stream and self.input_audio_stream.active:
            self.input_audio_stream.stop()
            self._info("Audio input stream muted")
            return True
        return False

    def unmute(self):
        """Resume the audio input stream if it exists"""
        if self.input_audio_stream and not self.input_audio_stream.active:
            self.input_audio_stream.start()
            self._info("Audio input stream unmuted")
            return True
        return False

    def is_muted(self):
        """Check if the audio input stream is currently muted"""
        if self.input_audio_stream:
            return not self.input_audio_stream.active
        return True  # If no stream exists, consider it muted

    def interrupt(self):
        """Interrupt current input and discard partial transcription.

        Use this when you need to abort user input mid-speech,
        e.g., when changing language settings.
        """
        self._info("Input interrupted, discarding partial transcription")

        # Set interrupt flag (checked by get_speech_input before returning)
        self.interrupt_event.set()

        # Discard any partial transcription
        self.transcription_handler.reset()

        # Reset VAD state
        self.vad.reset_states()

        # Clear buffered audio
        try:
            while True:
                self.audio_queue.get_nowait()
        except queue.Empty:
            pass

    def shutdown(self):
        # Clean up audio resources
        if self.input_audio_stream:
            self.input_audio_stream.stop()
            self.input_audio_stream.close()
            self.input_audio_stream = None


    def _info(self, text):
        if self.verbose:
            print(text)

    def get_speech_input(self):
        """Get speech input from user until end of utterance is detected.

        With callback mode, audio is captured in background thread automatically.
        This method just monitors for end-of-utterance.
        """
        # Small delay to ensure any system audio has finished
        time.sleep(0.1)

        # Clear any residual audio in the queue (e.g., from agent speech picked up by mic)
        cleared_count = 0
        try:
            while True:
                self.audio_queue.get_nowait()
                cleared_count += 1
        except queue.Empty:
            pass
        if cleared_count > 0:
            self._info(f"Cleared {cleared_count} audio chunks from queue")

        # Reset transcription state to avoid processing old audio
        self.transcription_handler.reset()
        self.vad.reset_states()

        self.caption_printer.start()

        try:
            # Start stream for listening (callback will feed queue)
            if not self.input_audio_stream.active:
                self.input_audio_stream.start()
            self._info(f">>> START input audio stream active: {self.input_audio_stream.active}")

            while True:
                # Check for stop signal
                if self.stop_event.is_set():
                    return ""

                # Small sleep to avoid busy-waiting (callback feeds queue in background)
                time.sleep(0.01)

                all_transcribed = ''
                if not self.transcription_handler.is_speech_recording:
                    if not self.transcription_handler.had_speech:
                        # wait until user spoke - make this message more visible
                        self.caption_printer.print("Please speak now...", partial=True)
                    else:
                        # define EOU when we haven't seen speech for a while
                        if self.transcription_handler.time_since_last_speech() > self.end_of_utterance_duration:
                            self._info(">>> seems user stopped speaking...")

                            # Check if interrupted (e.g., language change) - discard input
                            if self.interrupt_event.is_set():
                                self._info(">>> input was interrupted, discarding")
                                self.interrupt_event.clear()
                                all_transcribed = ''
                                break

                            # retranscribe and capture all
                            all_transcribed = ' '.join(self.transcription_handler.transcribed_segments)
                            self._info(f">> all said: {all_transcribed}")
                            # reset the transcriber
                            self.transcription_handler.reset()
                            break
        finally:
            # Stop stream while LLM is responding (prevent echo)
            if self.input_audio_stream.active:
                self.input_audio_stream.stop()

        return all_transcribed


class VoiceAgent():


    def __init__(self):
        # Lock to prevent concurrent language changes (causes segfault in TTS)
        self._language_change_lock = threading.Lock()

    def _info(self, text):
        """Print info message."""
        print(f"[VoiceAgent] {text}")

    def init_AudioToText(self, **audioToTextKwargs):
        t1 = time.time()
        self.input_handler = AudioToText(**audioToTextKwargs)
        print(f"> AudioToText initialized in {time.time()-t1:.2f} secs.")

    def init_LLmToAudioOutput(self, **llmToAudiOutputArgsKwargs):
        t1 = time.time()
        self.output_handler = LLmToAudio(**llmToAudiOutputArgsKwargs)
        print(f"> LLmToAudioOutput initialized in {time.time()-t1:.2f} secs.")
    
    def start(self):
        print("Starting voice agent...")

    def stop(self):
        self.input_handler.stop()
        self.output_handler.stop()        

    def shutdown(self):
        self.output_handler.shutdown()
        self.input_handler.shutdown()

    def run(self):

        # start the output handler and open with start message
        self.output_handler.start()

        start_message = self.output_handler.start_message
        self.output_handler._start_audio_stream()
        self.output_handler.assistant_printer.start()
        self.output_handler.assistant_printer.show_idle(start_message)
        self.output_handler._speak_sentence(start_message)
        self.output_handler._finish_processing()


        # start the input handler only once we're done with the start message to
        # avoid conflicts with audio streams
        self.input_handler.start()         

        while True:
            if self.stop_event_set():
                break
            
            user_input_transcribed = self.input_handler.get_speech_input()

            if not user_input_transcribed:
                continue

            if voice_agent_utils.DEFAULT_EXIT_COMMAND.lower() in user_input_transcribed.lower():
                self.output_handler.assistant_printer.print(voice_agent_utils.DEFAULT_GOODBYE_MESSAGE, partial=False)
                self.output_handler._speak_sentence(voice_agent_utils.DEFAULT_GOODBYE_MESSAGE, wait_for_completion=True)
                break
            else:
                if self.stop_event_set():
                    break
                self.output_handler.process_prompt(user_input_transcribed)
                time.sleep(0.3)    

    def trigger_stop_events(self):
        self.input_handler.stop_event.set()
        self.output_handler.stop_event.set()            
        time.sleep(0.2)

    def stop_event_set(self):
        return self.input_handler.stop_event.is_set() or self.output_handler.stop_event.is_set()
        
    def mute_microphone(self):
        """Temporarily mute the input audio stream"""
        return self.input_handler.mute()
        
    def unmute_microphone(self):
        """Resume the input audio stream"""
        return self.input_handler.unmute()
        
    def is_microphone_muted(self):
        """Check if the microphone is currently muted"""
        return self.input_handler.is_muted()

    def change_language(self, lang_config):
        """Dynamically change the target language for translation.

        Interrupts any ongoing input/output, switches TTS model and prompt,
        speaks the ready message, and returns to listening state.

        Args:
            lang_config: dict with keys 'lang', 'tts_model', 'prompt', 'ready_message'
        """
        # Prevent concurrent language changes (causes segfault in TTS loading)
        if not self._language_change_lock.acquire(blocking=False):
            self._info(f"Language change to {lang_config['lang']} skipped (another change in progress)")
            return

        try:
            self._info(f"Changing language to {lang_config['lang']}")

            # 1. Interrupt input FIRST to discard partial speech immediately
            #    (before output_handler.interrupt()'s 0.5s sleep)
            self.input_handler.interrupt()

            # 2. Interrupt any ongoing output to avoid audio overlap
            self.output_handler.interrupt()

            # 3. Mute mic to prevent picking up our own speech
            was_muted = self.is_microphone_muted()
            if not was_muted:
                self.mute_microphone()

            # 4. Update TTS model and prompt
            self.output_handler.update_language_context(
                tts_model_path=lang_config['tts_model'],
                new_system_prompt=lang_config['prompt']
            )

            # 5. Clear interrupt event so we can speak the ready message
            self.output_handler.interrupt_event.clear()

            # 6. Speak ready message and wait for completion
            self.output_handler._start_audio_stream()
            self.output_handler._speak_sentence(lang_config['ready_message'])
            self.output_handler._finish_processing()

            # 7. Clear input interrupt event (language change complete)
            self.input_handler.interrupt_event.clear()

            # 8. Unmute and return to listening
            if not was_muted:
                self.unmute_microphone()

            # 9. Cooldown to let native ONNX resources settle before allowing next change
            time.sleep(0.3)
        finally:
            self._language_change_lock.release()                        
