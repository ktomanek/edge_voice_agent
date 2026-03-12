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


# Registry of available display types
DISPLAY_TYPES = {
    'colored': ColoredPrinter,
    'minimal': MinimalPrinter,
}


def get_printer(display_type, title, title_color='blue'):
    """Factory function to create a printer instance."""
    if display_type not in DISPLAY_TYPES:
        raise ValueError(f"Unknown display type: {display_type}. Available: {list(DISPLAY_TYPES.keys())}")
    return DISPLAY_TYPES[display_type](title, title_color)
