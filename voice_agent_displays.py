import sys
import time

from captioning_lib import printers


class ColoredPrinter(printers.CaptionPrinter):

    def __init__(self, title, title_color='blue'):
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


class MinimalPrinter(printers.CaptionPrinter):
    """Minimal printer with no colors, just shows emoji for listening/speaking status."""

    def __init__(self, title=None, title_color=None):
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


# Try to import Whisplay library (pip install -e . from Whisplay_RPI5 repo)
try:
    from WhisPlay import WhisPlayBoard
    from PIL import Image, ImageDraw
    WHISPLAY_AVAILABLE = True
except ImportError:
    WHISPLAY_AVAILABLE = False

# Shared WhisPlayBoard instance (singleton) - only one board can be used at a time
_whisplay_board_instance = None


def _get_whisplay_board():
    """Get or create the shared WhisPlayBoard instance."""
    global _whisplay_board_instance
    if _whisplay_board_instance is None:
        _whisplay_board_instance = WhisPlayBoard()
        _whisplay_board_instance.set_backlight(80)
    return _whisplay_board_instance


class WhisplayPrinter(printers.CaptionPrinter):
    """Whisplay HAT display showing ear/mic icons with colored LEDs."""

    def __init__(self, title=None, title_color=None):
        if not WHISPLAY_AVAILABLE:
            raise ImportError("Whisplay library not available. Install with: pip install git+https://github.com/ktomanek/Whisplay_RPI5.git")

        self._board = _get_whisplay_board()
        self._title = title or ""
        # Determine if this is a "listening" (user input) or "speaking" (agent output) printer
        self._is_user_printer = "user" in self._title.lower() or "input" in self._title.lower()

    def _draw_ear_icon(self):
        """Draw a simple ear shape."""
        width = self._board.LCD_WIDTH
        height = self._board.LCD_HEIGHT
        img = Image.new('RGB', (width, height), (0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Draw a simple ear shape using arcs and lines
        cx, cy = width // 2, height // 2
        # Outer ear arc
        draw.arc([cx-50, cy-70, cx+50, cy+70], 270, 90, fill=(255, 100, 100), width=8)
        # Inner ear curve
        draw.arc([cx-30, cy-40, cx+20, cy+40], 270, 90, fill=(255, 100, 100), width=6)

        # Convert to RGB565
        pixel_data = []
        for py in range(height):
            for px in range(width):
                r, g, b = img.getpixel((px, py))
                rgb565 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
                pixel_data.append((rgb565 >> 8) & 0xFF)
                pixel_data.append(rgb565 & 0xFF)
        return pixel_data

    def _draw_mic_icon(self):
        """Draw a simple microphone shape."""
        width = self._board.LCD_WIDTH
        height = self._board.LCD_HEIGHT
        img = Image.new('RGB', (width, height), (0, 0, 0))
        draw = ImageDraw.Draw(img)

        cx, cy = width // 2, height // 2
        # Mic head (rounded rectangle)
        draw.rounded_rectangle([cx-25, cy-60, cx+25, cy+20], radius=20, fill=(100, 255, 100))
        # Mic stand
        draw.arc([cx-40, cy-10, cx+40, cy+50], 0, 180, fill=(100, 255, 100), width=6)
        # Mic base
        draw.line([cx, cy+50, cx, cy+80], fill=(100, 255, 100), width=6)
        draw.line([cx-30, cy+80, cx+30, cy+80], fill=(100, 255, 100), width=6)

        # Convert to RGB565
        pixel_data = []
        for py in range(height):
            for px in range(width):
                r, g, b = img.getpixel((px, py))
                rgb565 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
                pixel_data.append((rgb565 >> 8) & 0xFF)
                pixel_data.append(rgb565 & 0xFF)
        return pixel_data

    def start(self):
        """Show appropriate state based on printer role."""
        if self._is_user_printer:
            # User input: listening state with ear icon and red LED
            self._board.set_rgb(255, 0, 0)  # Red LED
            image_data = self._draw_ear_icon()
            self._board.draw_image(0, 0, self._board.LCD_WIDTH, self._board.LCD_HEIGHT, image_data)
        else:
            # Agent output: speaking state with mic icon and green LED
            self._board.set_rgb(0, 255, 0)  # Green LED
            image_data = self._draw_mic_icon()
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
        """Show speaking state: microphone icon with green LED."""
        self._board.set_rgb(0, 255, 0)  # Green LED
        image_data = self._draw_mic_icon()
        self._board.draw_image(0, 0, self._board.LCD_WIDTH, self._board.LCD_HEIGHT, image_data)

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


# Registry of available display types
DISPLAY_TYPES = {
    'colored': ColoredPrinter,
    'minimal': MinimalPrinter,
    'whisplay': WhisplayPrinter,
}


def get_printer(display_type, title, title_color='blue'):
    """Factory function to create a printer instance."""
    if display_type not in DISPLAY_TYPES:
        raise ValueError(f"Unknown display type: {display_type}. Available: {list(DISPLAY_TYPES.keys())}")
    if display_type == 'whisplay' and not WHISPLAY_AVAILABLE:
        raise ImportError("Whisplay library not available")
    return DISPLAY_TYPES[display_type](title, title_color)
