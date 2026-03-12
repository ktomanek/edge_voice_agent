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
3. **Create python environment**: eg `python -m venv venv` and `source venv/bin/activate`
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
   * moonshine models: ```python download_moonshine_models.py```
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

#### For UI
* CLI should work on all environments
* the UI is based on tkinter (customtkinter), which should run seamlessly on Linux; on MacOs it might be necessary to download python from https://www.python.org/downloads/macos and use this python version instead of one installed by homebrew (ie, create your python environment with the newly installed version of python, which sould be found under eg ```/usr/local/bin/python3.12```)
* for running the TKInter UI you might need to install a tk-enabled python version: ```sudo apt install python3-tk```


## CLI command line arguments

### Display Options

The voice agent supports different display modes via the `--display` argument:

| Display | Description |
| ------- | ----------- |
| `colored` | (default) Rich console output with colors, spinners, and styled text |
| `minimal` | Simple emoji-based status display (👂 listening, 🗣️ speaking) |
| `whisplay` | [Whisplay HAT](https://github.com/ktomanek/Whisplay_RPI5) display with ear/mic icons and colored LEDs |

Usage:
```bash
python voice_agent_cli.py --display colored   # default
python voice_agent_cli.py --display minimal   # minimal emoji output
python voice_agent_cli.py --display whisplay  # Whisplay HAT display
```

#### Whisplay Display

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

### End of utterance detection

```--end_of_utterance_duration 0.7``` determines when we consider the user input to be finished. Adapt according to user's speaking patterns, slower speakers might need a higher value. ```0.7``` seems to be a good default

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
