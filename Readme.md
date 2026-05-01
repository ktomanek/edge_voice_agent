# Small Voice Agent running fully offline on edge devices

* flexible wrt to ASR, LLM and TTS component, currently supported:
   * ASR: Moonshine, FasterWhisper, Nemo FastConformer, Vosk
   * TTS: Piper, Kokoro
   * LLM: any model, hosted through LLama.cpp
* components chosen to work fully offline on-device, CPU only
   * default setup can run on Raspberry Pi 5
      * ASR: Moonshine tiny
      * TTSL: Piper
      * LLM: Gemma3:1b


## Installation

### Quick Start (Recommended)

1. **Install llama.cpp**: Follow [installation instructions](https://github.com/ggml-org/llama.cpp) and ensure `llama-server` is in your PATH and that `-DLLAMA_BUILD_SERVER=ON` is in your cmake flags.
    * make sure `llama-server` is in the path or set symlink, eg like this: `sudo ln -s ~/dev/llama.cpp/build/bin/llama-server /usr/local/bin/llama-server`
3. **Create python environment**: eg `python -m venv venv` and `source venv/bin/activate` (see [GPIO Hardware Controls](#gpio-hardware-controls) for platform-specific setup)
2. **One-step setup**: `python setup.py`
3. **Try the fitness coach demo**: `./start_demo.py` (using tiny ASR/LLM and TTS models to run edge devices like a Raspberry Pi for example)
4. **Or start manually**: 
   ```bash
   # Terminal 1: Start LLM server
   llama-server -m models/llms/LFM2-350M-Q4_K_M.gguf --port 8080
   
   # Terminal 2: Start voice agent
   python voice_agent_cli.py
   ```

### Manual Installation (Alternative)

#### Preparation
* `python -m venv venv`
* you might need to install: ```sudo apt install python3-dev portaudio19-dev```


#### Dependencies
* ```pip install -r requirements.txt```

#### Download assets
* download models (check scripts if you want other models):
   * piper tts models: ```sh download_piper_models.sh```
   * llm models: ```sh download_llm.sh```
   * moonshine models: ```python download_moonshine_v1_models.py```
   * silero vad models: ```python download_silero_vad_model.py```

#### Llama.cpp
* install [LLama.cpp](https://github.com/ggml-org/llama.cpp) locally and make sure that at least `llama-server` is added to the path
* then retrieve GGUF files of the model you want to use
   * recommended quantization level: Q4_K_M - typically good balance of quality and size
   * models can be downloaded eg from HuggingFace
      * eg for LiquidAI's LFM2 variants: [here](https://huggingface.co/collections/LiquidAI/lfm2-686d721927015b2ad73eaa38)
* start a local LLama.cpp server for the chosen and downloaded model:
   * ```sh start_llama_server.sh mymodel.gguf```
   * depending on your environment, modify settings in the llama.cpp server (eg context length, threads, etc)


### Optional

#### Kokoro TTS
* Download models if using Kokoro instead of Piper: ```sh download_kokoro_models.sh```

#### Nvidia ASR
* if you want to use Nvidia's ASR models (nemo): ```pip install "nemo_toolkit[asr]"```


## CLI command line arguments

### Interaction Handlers

The voice agent supports different interaction handlers via the `--interaction_handler` argument:

| Handler | Description |
| ------- | ----------- |
| `colored` | (default) Rich console output with colors, spinners, and styled text |
| `minimal` | Simple emoji-based status display (👂 listening, 🗣️ speaking) |
| `whisplay` | [Whisplay HAT](https://github.com/ktomanek/Whisplay_RPI5) display with ear/mic icons and colored LEDs |
| `display_leds_interrupt` | Waveshare 1.69" LCD + external LEDs + ReSpeaker button for interrupt |


#### Whisplay Handler

For the Whisplay HAT display on Raspberry Pi 5, you need to install system packages first (lgpio cannot be pip installed):

```bash
# Install system packages
sudo apt install python3-lgpio python3-gpiozero python3-spidev python3-pil

# Create venv with access to system packages
python3 -m venv --system-site-packages venv
source venv/bin/activate

# Install the Whisplay driver
pip install git+https://github.com/ktomanek/Whisplay_RPI5.git
```

The `--system-site-packages` flag is required because `lgpio` (needed for Pi 5 GPIO) must be installed via apt, not pip.

The Whisplay display shows:
- Red LED + ear icon when listening
- Green LED + microphone icon when speaking
- Press the button to exit

#### Display + LEDs + Interrupt Button Handler

For a custom setup with Waveshare 1.69" LCD display, external LEDs, and ReSpeaker 2-Mic HAT (for audio and button):

```bash
# Install system packages
sudo apt install python3-lgpio python3-gpiozero python3-spidev python3-pil

# Create venv with access to system packages
python3 -m venv --system-site-packages venv
source venv/bin/activate
```

Hardware connections:
- **Display**: Waveshare 1.69" LCD via SPI (GPIO 8, 10, 11, 12, 25, 27)
- **LEDs**: External red (GPIO 5), yellow (GPIO 6), green (GPIO 13)
- **Button**: ReSpeaker onboard button (GPIO 17)
- **Audio**: ReSpeaker 2-Mic HAT via I2S (GPIO 18-21)

The display shows:
- Red LED + mic icon when listening to user
- Green LED + robot icon when agent is speaking
- Yellow LED + pause icon when interrupted
- Press the ReSpeaker button to interrupt the agent

### GPIO Hardware Controls

The voice agent supports hardware controls via GPIO on single-board computers using the `--platform` argument:

| Platform | Board | GPIO Library |
| -------- | ----- | ------------ |
| `rpi5` | Raspberry Pi 5 | gpiozero |
| `opi5` | Orange Pi 5 Pro | gpiod |

#### Features

- **Interrupt Button**: Press while the agent is speaking to stop the speech and return to listening mode. (Presses while the agent is silent are ignored.)
- **Rotary Dial**: 3-position switch.
  - In `voice_translate_cli.py`: selects the output language (positions 1/2/3 → German/Spanish/French).
  - In `voice_agent_cli.py`: selects which prompt to use (positions 1/2/3 → first 3 prompts in `prompts.json`, with a full conversation reset on change).

#### Usage

```bash
# Voice agent with interrupt button + rotary dial (rotary cycles among first 3 prompts)
python voice_agent_cli.py --platform rpi5 --prompt_file prompts.json

# Translation agent with interrupt button + rotary dial (rotary picks language)
python voice_translate_cli.py --platform opi5

# With verbose output to see button actions
python voice_agent_cli.py --platform rpi5 --verbose
```

#### Keyboard Controls

When running on a laptop/desktop without GPIO, you can use keyboard controls:

```bash
python voice_agent_cli.py --enable_keyboard_control
```

| Key | Action |
| --- | ------ |
| ENTER | Interrupt agent speech (only while agent is speaking) |
| SPACE | Toggle microphone mute/unmute |
| g / s / f | Switch to prompt 1 / 2 / 3 (mirrors rotary dial; agent CLI only) |

Note: keyboard `g/s/f` map to the same positions as the rotary dial (`pos1/pos2/pos3`). In the translator CLI those keys also pick German/Spanish/French.

#### Pinout

Pin numbers are **GPIO numbers** (BCM numbering), not physical pin numbers.

**Raspberry Pi 5 (`rpi5`)**

See [Raspberry Pi 5 Pinout](https://vilros.com/pages/raspberry-pi-5-pinout) for reference.

| Function | GPIO | Physical Pin |
| -------- | ---- | ------------ |
| Interrupt Button | 22 | 15 |
| Rotary: pos1 (German / prompt 1) | 23 | 16 |
| Rotary: pos2 (Spanish / prompt 2) | 24 | 18 |
| Rotary: pos3 (French / prompt 3) | 17 | 11 |

Note: These pins are chosen to avoid conflicts with the [ReSpeaker 2-Mic HAT](https://pinout.xyz/pinout/respeaker_2_mics_phat).

**Orange Pi 5 Pro (`opi5`)**

See [Orange Pi 5 Pro](http://www.orangepi.org/html/hardWare/computerAndMicrocontrollers/details/Orange-Pi-5-Pro.html) for reference. Uses `/dev/gpiochip1`:

| Function | GPIO |
| -------- | ---- |
| Interrupt Button | 14 |
| Rotary: pos1 (German / prompt 1) | 13 |
| Rotary: pos2 (Spanish / prompt 2) | 15 |
| Rotary: pos3 (French / prompt 3) | 8 |

#### Installation

**Raspberry Pi 5:**

Requires system packages because `lgpio` (needed for Pi 5 GPIO) cannot be pip installed:

```bash
# Install system packages
sudo apt install python3-lgpio python3-gpiozero

# Create venv with access to system packages
python3 -m venv --system-site-packages venv
source venv/bin/activate

# Then run setup
python setup.py
```

**Orange Pi 5 Pro:**

```bash
pip install gpiod
```

Then run `python setup.py` as usual.

### End of utterance detection

```--end_of_utterance_duration 0.7``` determines when we consider the user input to be finished. Adapt according to user's speaking patterns, slower speakers might need a higher value. ```0.7``` seems to be a good default

### Conversation Logging

Log all user and agent utterances to a timestamped file:

```bash
python voice_agent_cli.py --log-conversation
```

Logs are saved to `logs/conversation_YYYYMMDD_HHMMSS.txt` with format:
```
Conversation started at 2026-04-16 14:30:22
--------------------------------------------------
[14:30:25] USER: Hello how are you
[14:30:28] AGENT: I'm doing well, thank you for asking!
[14:30:35] USER: What's the weather like
[14:31:00] AGENT: [RESET]
[14:31:00] AGENT: Hello, how can I help you today?
...
```

Resets are logged as `[RESET]` followed by the start message.

## System prompt from text

* you can increase the speaking rate to make long responses not feel quite as length

```python voice_agent_cli.py --speaking_rate 3.0 --system_prompt "`cat examples/cat_specialist.txt`" ```

## Other models

* moonshine base seems to run fast enough on Raspberry Pi.
* different and especially larger LLM models will lead to much improved conversational abilities

## Performance measurements

### User Speech input

See [here](https://github.com/ktomanek/captioning?tab=readme-ov-file#streaming-performance-comparison) for comparison on different ASR models in the streaming lib on various devices.

### LLM Generation

Before audio output can be generated, the LLM needs to generate enough tokens to start synthesizing audio output.
When running ```python voice_agent_cli.py --verbose```, several performance metrics will be shown quantifying this latency.

  * Time to first token (seconds)
      * measures the time it took the LLM until the first token was generated
      * this in only dependent on the LLM's inference speed in streaming mode
  * Time to first speech fragment (seconds)
      * measures how long it took the LLM to generate enough tokens needed to start synthesizing audio output (this doesn't include the time needed to actually generate the audio ouput, but is an important measure for minimal latency until audio can be generated)
      * this also depends on how the parameter ```--max_words_to_speak_start``` is set. A lower number means that the first speech segment is shorter and hence can be generated by the LLM quicker; the downside is a likely more synthetic sounding output. Processing speech on the respecitve device should be taken into consideration here.

LLama.cpp allows to benchmark models, eg with ```llama-bench -m LFM2-350M-Q4_K_M.gguf -t 2```. The relevant metrics to look at are ```ppxxx``` -- prompt processing (prefill) and ```tgXXX``` -- text generation.


#### Measurements

Hardware tested

* Rasp - Raspberry Pi 5, 16GB
* Mac M2 - Macbook Air M2, 16GB

In both cases, measurements where taking with the CPU governor  set to ```performance``` (see above). On Mac M2, the impact was minimal, but on Raspberry Pi 5, setting the CPU governor to ```performance``` led to more consistent and lower ```time to first token/speech segment``` measurements.

We set ```--max_words_to_speak_start``` to 5 for these experiments.


| model | metric | Mac M2 | Rasp |
| -- | -- | -- | -- |
| LFM2-350M-Q4_K_M.gguf | Time to first token (seconds) | ~0.09 sec |  ~0.30sec |
| LFM2-350M-Q4_K_M.gguf | Time to first speech fragment (seconds) | ~0.17 sec  | ~0.45 sec |
| -- | -- | -- | -- |
| LFM2-350M-Q4_K_M.gguf | Time to first token (seconds) | ~0.12 sec |  ~0.7sec |
| LFM2-350M-Q4_K_M.gguf | Time to first speech fragment (seconds) | ~0.20 sec  | ~1.0-1.3 sec |
| -- | -- | -- | -- |
| LFM2-700M-Q4_K_M.gguf | Time to first token (seconds) | ~0.14 sec | ~0.9-1.5 sec | 
| LFM2-700M-Q4_K_M.gguf | Time to first speech fragment (seconds) | ~0.26 sec  | ~1.3-1.7 sec |

The variance in inference speed on the Raspberry Pi is quite remarkable by the 700M and 1.2B models. Conversation quality is getting quite good with the 1.2B model. The 350M param model is very fast to respond on  a Raspberry Pi, however, conversation quality is significantly lacking compared to the 1.2B model.


## Example on Raspberry Pi 5

Running offline with above configuration (Moonshine ASR tiny, Gemma3:1b, Piper voice).

[video](https://github.com/user-attachments/assets/486d4d48-36ff-455a-bca0-d230fe26dd0b)
