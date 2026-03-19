import sys
import time
import threading

from captioning_lib import printers

# Keyboard support for button simulation
try:
    import termios
    import tty
    import select
    KEYBOARD_AVAILABLE = True
except ImportError:
    KEYBOARD_AVAILABLE = False


def _start_keyboard_listener(key_callbacks, stop_event):
    """Background thread that listens for keyboard input and dispatches to callbacks.

    Args:
        key_callbacks: dict mapping keys to callbacks, e.g.:
            {
                'enter': callback,      # Enter/Return key
                'space': callback,      # Space bar
                'escape': callback,     # ESC key
                'g': callback,          # Letter keys
                ...
            }
        stop_event: threading.Event to signal when to stop listening
    """
    if not KEYBOARD_AVAILABLE:
        return

    fd = sys.stdin.fileno()
    try:
        old_settings = termios.tcgetattr(fd)
    except:
        return  # Not a terminal

    def listener():
        try:
            tty.setcbreak(fd)  # Use cbreak instead of raw to allow Ctrl+C
            while not stop_event.is_set():
                if select.select([sys.stdin], [], [], 0.1)[0]:
                    key = sys.stdin.read(1)

                    # Map special keys to names
                    if key == '\n' or key == '\r':
                        key_name = 'enter'
                    elif key == ' ':
                        key_name = 'space'
                    elif key == '\x1b':
                        key_name = 'escape'
                    else:
                        key_name = key.lower()

                    # Call the callback if registered
                    if key_name in key_callbacks:
                        key_callbacks[key_name]()
        except Exception as e:
            print(f"Keyboard listener error: {e}")
            raise e
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    thread = threading.Thread(target=listener, daemon=True)
    thread.start()
    return thread


class ColoredHandler(printers.CaptionPrinter):

    def __init__(self, title, title_color='blue', **kwargs):
        # https://rich.readthedocs.io/en/stable/style.html
        from rich.console import Console
        from rich.theme import Theme
        self.title = title
        self.title_color = title_color
        caption_theme = Theme({
            "partial": "italic",
            "segment": f"bold {self.title_color}",
        })
        self.console = Console(theme=caption_theme, highlight=False)

    def start(self):
        self.console.rule(f"[bold {self.title_color}]{self.title}")

    def stop(self):
        self.console.rule()

    def print(self, transcript, duration=None, partial=False, is_recent_chunk_mode=False, recent_chunk_duration=None):
        """Update the caption display with the latest transcription"""
        # Move to the beginning of the line and clear it
        sys.stdout.write("\r\033[K")

        text = transcript

        # Show partial and full segments differently
        if partial:
            terminal_width = self.console.width
            if len(text) > terminal_width/2:
                last_chars = terminal_width - 5
                text = '...' + text[-last_chars:]
            syle = "partial"
            self.console.print(text, end="", style=syle)   # Print the styled text without adding a new line
        else:
            syle = "segment"
            self.console.print(text, style=syle) # Print the styled text without adding a new line

    def show_idle(self, text=None):
        if not hasattr(self, '_spinner_frame'):
            self._spinner_frame = 0
            self._spinner_last_update = 0

        # Different spinner styles
        spinners = {
            'dots': ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'],
            'bar': ['▏', '▎', '▍', '▌', '▋', '▊', '▉', '█', '▉', '▊', '▋', '▌', '▍', '▎'],
            'circle': ['◐', '◓', '◑', '◒'],
            'pulse': ['●', '○', '○', '○'],
            'classic': ['|', '/', '-', '\\']
        }

        spinner_chars = spinners.get('circle', spinners['classic'])

        # Update animation frame based on time (smoother than random)
        current_time = time.time()
        if current_time - self._spinner_last_update > 0.1:  # Update every 100ms
            self._spinner_frame = (self._spinner_frame + 1) % len(spinner_chars)
            self._spinner_last_update = current_time

        spinner_symbol = spinner_chars[self._spinner_frame]

        if text:
            idle_msg = f"{spinner_symbol} {text}"
        else:
            idle_msg = spinner_symbol

        self.print(idle_msg, partial=True)

    def on_button_press(self, callback):
        """Register a callback for ENTER key press (simulates button).

        This is a convenience wrapper around setup_keyboard_controls for
        simple interrupt-only use cases.
        """
        self.setup_keyboard_controls({'enter': callback})

    def setup_keyboard_controls(self, key_callbacks):
        """Set up keyboard controls with custom key bindings.

        Args:
            key_callbacks: dict mapping key names to callbacks, e.g.:
                {
                    'enter': on_interrupt,
                    'space': on_mute_toggle,
                    'escape': on_exit,
                    'g': lambda: change_lang('german'),
                }
        """
        if not hasattr(self, '_stop_event'):
            self._stop_event = threading.Event()
        self._key_callbacks = key_callbacks
        _start_keyboard_listener(key_callbacks, self._stop_event)

    def cleanup(self):
        """Clean up resources."""
        if hasattr(self, '_stop_event'):
            self._stop_event.set()


class ColoredHandlerWithInterruptButton(ColoredHandler):
    """ColoredHandler extended with GPIO-based interrupt button (and ENTER key fallback).

    Uses GPIO 16 for the interrupt button (no conflict with ReSpeaker HAT or display pins).
    On non-Pi systems, falls back to ENTER key only.
    """

    INTERRUPT_BUTTON_PIN = 16  # GPIO 16 - free pin, no conflict with display/LEDs/ReSpeaker

    def __init__(self, title, title_color='blue', is_agent=False, **kwargs):
        super().__init__(title, title_color, **kwargs)
        self._gpio_button = None
        self._button_callback = None

        # Only initialize GPIO button for agent handler to avoid pin conflicts
        if is_agent and GPIO_AVAILABLE:
            try:
                from gpiozero import Button
                self._gpio_button = Button(self.INTERRUPT_BUTTON_PIN)
            except Exception as e:
                print(f"Warning: Could not initialize GPIO button on pin {self.INTERRUPT_BUTTON_PIN}: {e}")
                self._gpio_button = None

    def on_button_press(self, callback):
        """Register a callback for both ENTER key and GPIO button press."""
        self._button_callback = callback

        # Set up ENTER key listener (from parent)
        super().on_button_press(callback)

        # Set up GPIO button if available
        if self._gpio_button is not None:
            self._gpio_button.when_pressed = callback

    def cleanup(self):
        """Clean up resources including GPIO button."""
        super().cleanup()
        if self._gpio_button is not None:
            try:
                self._gpio_button.close()
            except:
                pass
            self._gpio_button = None


class MinimalHandler(printers.CaptionPrinter):
    """Minimal handler with no colors, just shows emoji for listening/speaking status."""

    def __init__(self, title=None, title_color=None, **kwargs):
        # title and title_color are accepted but ignored for API compatibility
        self._is_listening = False

    def start(self):
        self._is_listening = True
        sys.stdout.write("\r\033[K")
        print("👂")

    def stop(self):
        self._is_listening = False
        sys.stdout.write("\r\033[K")

    def print(self, transcript, duration=None, partial=False, is_recent_chunk_mode=False, recent_chunk_duration=None):
        """Update the display with the latest transcription"""
        sys.stdout.write("\r\033[K")
        if partial:
            # For partials, just show the text on the same line
            sys.stdout.write(transcript)
            sys.stdout.flush()
        else:
            # For final segments, print with newline
            print(transcript)

    def show_idle(self, text=None):
        sys.stdout.write("\r\033[K")
        sys.stdout.write("🗣️")
        sys.stdout.flush()

    def on_button_press(self, callback):
        """Register a callback for ENTER key press (simulates button)."""
        self.setup_keyboard_controls({'enter': callback})

    def setup_keyboard_controls(self, key_callbacks):
        """Set up keyboard controls with custom key bindings."""
        if not hasattr(self, '_stop_event'):
            self._stop_event = threading.Event()
        self._key_callbacks = key_callbacks
        _start_keyboard_listener(key_callbacks, self._stop_event)

    def cleanup(self):
        """Clean up resources."""
        if hasattr(self, '_stop_event'):
            self._stop_event.set()


# Try to import Whisplay library (pip install -e . from Whisplay_RPI5 repo)
try:
    from WhisPlay import WhisPlayBoard
    from PIL import Image, ImageDraw
    WHISPLAY_AVAILABLE = True
except ImportError:
    WHISPLAY_AVAILABLE = False

# Try to import GPIO libraries for custom GPIO handler
try:
    import spidev
    from gpiozero import LED, Button, DigitalOutputDevice, PWMLED
    from PIL import Image, ImageDraw, ImageFont
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False

# Shared WhisPlayBoard instance (singleton) - only one board can be used at a time
_whisplay_board_instance = None


def _get_whisplay_board():
    """Get or create the shared WhisPlayBoard instance."""
    global _whisplay_board_instance
    if _whisplay_board_instance is None:
        _whisplay_board_instance = WhisPlayBoard()
        _whisplay_board_instance.set_backlight(80)
    return _whisplay_board_instance


class WhisplayHandler(printers.CaptionPrinter):
    """Whisplay HAT interaction handler showing ear/mic icons with colored LEDs."""

    def __init__(self, title=None, title_color=None, is_agent=False, **kwargs):
        if not WHISPLAY_AVAILABLE:
            raise ImportError("Whisplay library not available. Install with: pip install git+https://github.com/ktomanek/Whisplay_RPI5.git")

        self._board = _get_whisplay_board()
        self._title = title or ""
        self._is_agent = is_agent
        # Determine if this is a "listening" (user input) or "speaking" (agent output) handler
        self._is_user_printer = not is_agent

        # Show green LED on startup (booting)
        self._board.set_rgb(0, 255, 0)

    def _convert_to_rgb565(self, img):
        """Convert PIL image to RGB565 pixel data."""
        width, height = img.size
        pixel_data = []
        for py in range(height):
            for px in range(width):
                r, g, b = img.getpixel((px, py))
                rgb565 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
                pixel_data.append((rgb565 >> 8) & 0xFF)
                pixel_data.append(rgb565 & 0xFF)
        return pixel_data

    def _load_font(self, size=18):
        """Load a font for text rendering."""
        from PIL import ImageFont
        for fpath in [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        ]:
            try:
                return ImageFont.truetype(fpath, size)
            except:
                pass
        return ImageFont.load_default()

    def _draw_mic_listening(self):
        """Draw microphone icon with 'listening to user' text."""
        width = self._board.LCD_WIDTH
        height = self._board.LCD_HEIGHT
        img = Image.new('RGB', (width, height), (0, 0, 0))
        draw = ImageDraw.Draw(img)

        cx = width // 2
        cy = height // 2 - 30  # Shift icon up to make room for text

        # Mic head (rounded rectangle)
        color = (255, 100, 100)  # Red
        draw.rounded_rectangle([cx-25, cy-50, cx+25, cy+20], radius=20, fill=color)
        # Mic stand
        draw.arc([cx-40, cy, cx+40, cy+50], 0, 180, fill=color, width=6)
        # Mic base
        draw.line([cx, cy+50, cx, cy+75], fill=color, width=6)
        draw.line([cx-30, cy+75, cx+30, cy+75], fill=color, width=6)

        # Draw text
        font = self._load_font(18)
        text = "listening to user"
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        draw.text(((width - text_width) // 2, height - 40), text, fill=color, font=font)

        return self._convert_to_rgb565(img)

    def _draw_robot_speaking(self):
        """Draw robot icon with 'agent responding' text."""
        width = self._board.LCD_WIDTH
        height = self._board.LCD_HEIGHT
        img = Image.new('RGB', (width, height), (0, 0, 0))
        draw = ImageDraw.Draw(img)

        cx = width // 2
        cy = height // 2 - 30  # Shift icon up to make room for text

        color = (255, 255, 255)  # White

        # Robot head
        draw.rounded_rectangle([cx-40, cy-40, cx+40, cy+30], radius=10, fill=color)
        # Eyes
        draw.ellipse([cx-25, cy-25, cx-10, cy-5], fill=(0, 0, 0))
        draw.ellipse([cx+10, cy-25, cx+25, cy-5], fill=(0, 0, 0))
        # Mouth
        draw.rectangle([cx-20, cy+5, cx+20, cy+15], fill=(0, 0, 0))
        # Antenna
        draw.line([cx, cy-40, cx, cy-60], fill=color, width=4)
        draw.ellipse([cx-8, cy-70, cx+8, cy-55], fill=color)
        # Body hint
        draw.rectangle([cx-30, cy+35, cx+30, cy+70], fill=color)

        # Draw text
        font = self._load_font(18)
        text = "agent responding"
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        draw.text(((width - text_width) // 2, height - 40), text, fill=color, font=font)

        return self._convert_to_rgb565(img)

    def start(self):
        """Show appropriate state based on handler role."""
        if self._is_user_printer:
            # User input: recording state with mic icon and red LED
            self._board.set_rgb(255, 0, 0)  # Red LED
            image_data = self._draw_mic_listening()
            self._board.draw_image(0, 0, self._board.LCD_WIDTH, self._board.LCD_HEIGHT, image_data)
        else:
            # Agent output: speaking state with robot icon and white LED
            self._board.set_rgb(255, 255, 255)  # White LED
            image_data = self._draw_robot_speaking()
            self._board.draw_image(0, 0, self._board.LCD_WIDTH, self._board.LCD_HEIGHT, image_data)

    def stop(self):
        self._board.set_rgb(0, 0, 0)  # LED off
        self._board.fill_screen(0)  # Clear screen

    def print(self, transcript, duration=None, partial=False, is_recent_chunk_mode=False, recent_chunk_duration=None):
        """Update the display - for Whisplay we just show status icons."""
        # Console output for debugging
        sys.stdout.write("\r\033[K")
        if partial:
            sys.stdout.write(transcript)
            sys.stdout.flush()
        else:
            print(transcript)

    def show_idle(self, text=None):
        """Show speaking state: robot icon with white LED."""
        self._board.set_rgb(255, 255, 255)  # White LED
        image_data = self._draw_robot_speaking()
        self._board.draw_image(0, 0, self._board.LCD_WIDTH, self._board.LCD_HEIGHT, image_data)

    def _draw_interrupted(self):
        """Draw stop/interrupted symbol."""
        width = self._board.LCD_WIDTH
        height = self._board.LCD_HEIGHT
        img = Image.new('RGB', (width, height), (0, 0, 0))
        draw = ImageDraw.Draw(img)

        cx = width // 2
        cy = height // 2 - 30

        color = (255, 200, 0)  # Yellow/orange

        # Draw stop hand / pause symbol
        # Two vertical bars (pause icon)
        draw.rectangle([cx-35, cy-40, cx-15, cy+40], fill=color)
        draw.rectangle([cx+15, cy-40, cx+35, cy+40], fill=color)

        # Draw text
        font = self._load_font(18)
        text = "interrupted"
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        draw.text(((width - text_width) // 2, height - 40), text, fill=color, font=font)

        return self._convert_to_rgb565(img)

    def show_interrupted(self):
        """Show interrupted state briefly (yellow LED + pause symbol)."""
        self._board.set_rgb(255, 200, 0)  # Yellow LED
        image_data = self._draw_interrupted()
        self._board.draw_image(0, 0, self._board.LCD_WIDTH, self._board.LCD_HEIGHT, image_data)
        time.sleep(1.0)  # Brief pause

    def on_button_press(self, callback):
        """Register a callback for when the Whisplay button is pressed."""
        self._board.on_button_press(callback)

    def cleanup(self):
        """Clean up Whisplay resources."""
        global _whisplay_board_instance
        if _whisplay_board_instance is not None:
            _whisplay_board_instance.set_rgb(0, 0, 0)
            _whisplay_board_instance.set_backlight(0)
            _whisplay_board_instance.cleanup()
            _whisplay_board_instance = None


# Shared GPIOBoard instance (singleton)
_gpio_board_instance = None


class GPIOBoard:
    """Combined GPIO board with display and LEDs.
    Pin layout so that it is compatible with ReSpeaker 2-Mics Pi HAT (button on pin 17, LEDs on 5,6,13) and has an ST7789V2 display connected via SPI (DC=25, RST=27, BL=12).
    """

    LCD_WIDTH = 240
    LCD_HEIGHT = 280
    # ST7789 RAM is 240x320, display is 240x280 - needs offset
    Y_OFFSET = 20

    # Pin assignments
    DC_PIN = 25
    RST_PIN = 27
    BL_PIN = 12
    RED_PIN = 5
    YELLOW_PIN = 6
    GREEN_PIN = 13
    BUTTON_PIN = 17  # ReSpeaker onboard button

    def __init__(self):
        # Display setup
        self.dc = DigitalOutputDevice(self.DC_PIN)
        self.rst = DigitalOutputDevice(self.RST_PIN)
        self.bl = PWMLED(self.BL_PIN)

        self.spi = spidev.SpiDev()
        self.spi.open(0, 0)
        self.spi.max_speed_hz = 40000000
        self.spi.mode = 0

        # External LEDs
        self.red_led = LED(self.RED_PIN)
        self.yellow_led = LED(self.YELLOW_PIN)
        self.green_led = LED(self.GREEN_PIN)

        # Button (ReSpeaker onboard)
        self.button = Button(self.BUTTON_PIN)

        self._init_display()

    def _init_display(self):
        """Initialize the ST7789V2 display."""
        self.rst.on()
        time.sleep(0.01)
        self.rst.off()
        time.sleep(0.01)
        self.rst.on()
        time.sleep(0.12)

        self._write_cmd(0x01)  # SWRESET
        time.sleep(0.12)
        self._write_cmd(0x11)  # SLPOUT
        time.sleep(0.12)
        self._write_cmd(0x3A)  # COLMOD
        self._write_data([0x05])  # 16-bit RGB565
        self._write_cmd(0x36)  # MADCTL
        self._write_data([0x00])
        self._write_cmd(0x21)  # INVON
        self._write_cmd(0x13)  # NORON
        time.sleep(0.01)
        self._write_cmd(0x29)  # DISPON
        time.sleep(0.12)

    def _write_cmd(self, cmd):
        self.dc.off()
        self.spi.writebytes([cmd])

    def _write_data(self, data):
        self.dc.on()
        self.spi.writebytes(data)

    def set_backlight(self, brightness):
        """Set backlight brightness (0-100)."""
        self.bl.value = brightness / 100.0

    def fill_screen(self, color):
        """Fill screen with RGB565 color."""
        self._set_window(0, 0, self.LCD_WIDTH - 1, self.LCD_HEIGHT - 1)
        high = (color >> 8) & 0xFF
        low = color & 0xFF
        chunk_size = 4096
        pixel_data = [high, low] * (self.LCD_WIDTH * self.LCD_HEIGHT)
        self.dc.on()
        for i in range(0, len(pixel_data), chunk_size):
            self.spi.writebytes(pixel_data[i:i + chunk_size])

    def _set_window(self, x0, y0, x1, y1):
        """Set the drawing window (applies Y_OFFSET for ST7789)."""
        # Apply Y offset for 240x280 display on 240x320 RAM
        y0 += self.Y_OFFSET
        y1 += self.Y_OFFSET
        self._write_cmd(0x2A)  # CASET
        self._write_data([x0 >> 8, x0 & 0xFF, x1 >> 8, x1 & 0xFF])
        self._write_cmd(0x2B)  # RASET
        self._write_data([y0 >> 8, y0 & 0xFF, y1 >> 8, y1 & 0xFF])
        self._write_cmd(0x2C)  # RAMWR

    def draw_image(self, x, y, width, height, pixel_data):
        """Draw RGB565 pixel data to display."""
        self._set_window(x, y, x + width - 1, y + height - 1)
        chunk_size = 4096
        self.dc.on()
        for i in range(0, len(pixel_data), chunk_size):
            self.spi.writebytes(pixel_data[i:i + chunk_size])

    def set_rgb(self, r, g, b):
        """Set LED states based on RGB values (maps to 3 separate LEDs)."""
        # Red LED for red channel
        if r > 127:
            self.red_led.on()
        else:
            self.red_led.off()
        # Green LED for green channel
        if g > 127:
            self.green_led.on()
        else:
            self.green_led.off()
        # Yellow when both red and green are high, or explicit yellow
        if (r > 127 and g > 127) or (r > 200 and g > 150 and g < 220):
            self.yellow_led.on()
        else:
            self.yellow_led.off()

    def set_led(self, led_name, state):
        """Set individual LED state."""
        led_map = {
            'red': self.red_led,
            'yellow': self.yellow_led,
            'green': self.green_led,
        }
        if led_name in led_map:
            if state:
                led_map[led_name].on()
            else:
                led_map[led_name].off()

    def on_button_press(self, callback):
        """Register callback for button press."""
        self.button.when_pressed = callback

    def cleanup(self):
        """Clean up all GPIO resources."""
        self.set_backlight(0)
        self.fill_screen(0)
        self.set_rgb(0, 0, 0)  # Turn off LEDs
        self.spi.close()
        self.dc.close()
        self.rst.close()
        self.bl.close()
        self.red_led.close()
        self.yellow_led.close()
        self.green_led.close()
        self.button.close()


def _get_gpio_board():
    """Get or create the shared GPIOBoard instance."""
    global _gpio_board_instance
    if _gpio_board_instance is None:
        _gpio_board_instance = GPIOBoard()
        _gpio_board_instance.set_backlight(80)
    return _gpio_board_instance


class DisplayWithLEDandInterruptButton(printers.CaptionPrinter):
    """Interaction handler with Waveshare display, external LEDs, and ReSpeaker button."""

    def __init__(self, title=None, title_color=None, is_agent=False, **kwargs):
        if not GPIO_AVAILABLE:
            raise ImportError("GPIO libraries not available. Install: pip install spidev gpiozero pillow")

        self._board = _get_gpio_board()
        self._title = title or ""
        self._is_agent = is_agent
        self._is_user_printer = not is_agent

        # Show green LED on startup
        self._board.set_rgb(0, 255, 0)

    def _convert_to_rgb565(self, img):
        """Convert PIL image to RGB565 pixel data."""
        width, height = img.size
        pixel_data = []
        for py in range(height):
            for px in range(width):
                r, g, b = img.getpixel((px, py))
                rgb565 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
                pixel_data.append((rgb565 >> 8) & 0xFF)
                pixel_data.append(rgb565 & 0xFF)
        return pixel_data

    def _load_font(self, size=18):
        """Load a font for text rendering."""
        for fpath in [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        ]:
            try:
                return ImageFont.truetype(fpath, size)
            except:
                pass
        return ImageFont.load_default()

    def _draw_mic_listening(self):
        """Draw microphone icon with 'listening to user' text."""
        width = self._board.LCD_WIDTH
        height = self._board.LCD_HEIGHT
        img = Image.new('RGB', (width, height), (0, 0, 0))
        draw = ImageDraw.Draw(img)

        cx = width // 2
        cy = height // 2 - 30

        color = (255, 100, 100)  # Red
        draw.rounded_rectangle([cx-25, cy-50, cx+25, cy+20], radius=20, fill=color)
        draw.arc([cx-40, cy, cx+40, cy+50], 0, 180, fill=color, width=6)
        draw.line([cx, cy+50, cx, cy+75], fill=color, width=6)
        draw.line([cx-30, cy+75, cx+30, cy+75], fill=color, width=6)

        font = self._load_font(18)
        text = "listening to user"
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        draw.text(((width - text_width) // 2, height - 40), text, fill=color, font=font)

        return self._convert_to_rgb565(img)

    def _draw_robot_speaking(self):
        """Draw robot icon with 'agent responding' text."""
        width = self._board.LCD_WIDTH
        height = self._board.LCD_HEIGHT
        img = Image.new('RGB', (width, height), (0, 0, 0))
        draw = ImageDraw.Draw(img)

        cx = width // 2
        cy = height // 2 - 30

        color = (255, 255, 255)  # White
        draw.rounded_rectangle([cx-40, cy-40, cx+40, cy+30], radius=10, fill=color)
        draw.ellipse([cx-25, cy-25, cx-10, cy-5], fill=(0, 0, 0))
        draw.ellipse([cx+10, cy-25, cx+25, cy-5], fill=(0, 0, 0))
        draw.rectangle([cx-20, cy+5, cx+20, cy+15], fill=(0, 0, 0))
        draw.line([cx, cy-40, cx, cy-60], fill=color, width=4)
        draw.ellipse([cx-8, cy-70, cx+8, cy-55], fill=color)
        draw.rectangle([cx-30, cy+35, cx+30, cy+70], fill=color)

        font = self._load_font(18)
        text = "agent responding"
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        draw.text(((width - text_width) // 2, height - 40), text, fill=color, font=font)

        return self._convert_to_rgb565(img)

    def _draw_interrupted(self):
        """Draw interrupted/pause symbol."""
        width = self._board.LCD_WIDTH
        height = self._board.LCD_HEIGHT
        img = Image.new('RGB', (width, height), (0, 0, 0))
        draw = ImageDraw.Draw(img)

        cx = width // 2
        cy = height // 2 - 30

        color = (255, 200, 0)  # Yellow
        draw.rectangle([cx-35, cy-40, cx-15, cy+40], fill=color)
        draw.rectangle([cx+15, cy-40, cx+35, cy+40], fill=color)

        font = self._load_font(18)
        text = "interrupted"
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        draw.text(((width - text_width) // 2, height - 40), text, fill=color, font=font)

        return self._convert_to_rgb565(img)

    def start(self):
        """Show appropriate state based on handler role."""
        if self._is_user_printer:
            # Listening: red LED + mic icon
            self._board.set_rgb(255, 0, 0)
            image_data = self._draw_mic_listening()
            self._board.draw_image(0, 0, self._board.LCD_WIDTH, self._board.LCD_HEIGHT, image_data)
        else:
            # Speaking: green LED + robot icon
            self._board.set_rgb(0, 255, 0)
            image_data = self._draw_robot_speaking()
            self._board.draw_image(0, 0, self._board.LCD_WIDTH, self._board.LCD_HEIGHT, image_data)

    def stop(self):
        """Turn off LEDs and clear display."""
        self._board.set_rgb(0, 0, 0)
        self._board.fill_screen(0)

    def print(self, transcript, duration=None, partial=False, is_recent_chunk_mode=False, recent_chunk_duration=None):
        """Update the display - console output for debugging."""
        sys.stdout.write("\r\033[K")
        if partial:
            sys.stdout.write(transcript)
            sys.stdout.flush()
        else:
            print(transcript)

    def show_idle(self, text=None):
        """Show speaking state: robot icon with green LED."""
        self._board.set_rgb(0, 255, 0)
        image_data = self._draw_robot_speaking()
        self._board.draw_image(0, 0, self._board.LCD_WIDTH, self._board.LCD_HEIGHT, image_data)

    def show_interrupted(self):
        """Show interrupted state (yellow LED + pause symbol)."""
        self._board.set_rgb(255, 200, 0)
        image_data = self._draw_interrupted()
        self._board.draw_image(0, 0, self._board.LCD_WIDTH, self._board.LCD_HEIGHT, image_data)
        time.sleep(1.0)

    def on_button_press(self, callback):
        """Register a callback for button press."""
        self._board.on_button_press(callback)

    def cleanup(self):
        """Clean up GPIO resources."""
        global _gpio_board_instance
        if _gpio_board_instance is not None:
            _gpio_board_instance.cleanup()
            _gpio_board_instance = None


# Registry of available interaction handlers
HANDLER_TYPES = {
    'colored': ColoredHandler,
    'colored_interrupt': ColoredHandlerWithInterruptButton,
    'minimal': MinimalHandler,
    'whisplay': WhisplayHandler,
    'display_leds_interrupt': DisplayWithLEDandInterruptButton,
}


def get_handler(handler_type, title, title_color='blue', is_agent=False):
    """Factory function to create an interaction handler instance.

    Args:
        handler_type: One of the registered handler types
        title: Display title for the handler
        title_color: Color for the title
        is_agent: If True, this handler is for agent output. Some handlers
                  (e.g., colored_interrupt) only enable GPIO button for user handler.
    """
    if handler_type not in HANDLER_TYPES:
        raise ValueError(f"Unknown handler type: {handler_type}. Available: {list(HANDLER_TYPES.keys())}")
    if handler_type == 'whisplay' and not WHISPLAY_AVAILABLE:
        raise ImportError("Whisplay library not available")
    if handler_type == 'display_leds_interrupt' and not GPIO_AVAILABLE:
        raise ImportError("GPIO libraries not available. Install: pip install spidev gpiozero pillow")
    return HANDLER_TYPES[handler_type](title, title_color, is_agent=is_agent)
