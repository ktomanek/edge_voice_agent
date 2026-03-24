"""GPIO input abstraction for different single-board computers.

Provides unified interface for:
- Interrupt button
- Rotary dial (4-position language selector)

Implementations:
- OrangePi5ProGPIOHandler (using gpiod)
- RaspberryPi5GPIOHandler (using gpiozero)
"""

import threading
import time
from abc import ABC, abstractmethod
from typing import Callable, Optional, Dict


class GPIOHandler(ABC):
    """Abstract base class for GPIO input handling."""

    LANGUAGES = ['german', 'spanish', 'arabic', 'french']

    def __init__(self):
        self._interrupt_callback: Optional[Callable] = None
        self._language_change_callback: Optional[Callable[[str], None]] = None
        self._running = False

    @abstractmethod
    def setup(self, add_interrupt_button=True, add_rotary_dial=True):
        """Initialize GPIO pins.

        Args:
            add_interrupt_button: If True, setup interrupt button.
            add_rotary_dial: If True, setup rotary dial for language selection.
        """
        pass

    @abstractmethod
    def cleanup(self):
        """Release GPIO resources."""
        pass

    @abstractmethod
    def is_interrupt_pressed(self) -> bool:
        """Return True if interrupt button is currently pressed."""
        pass

    @abstractmethod
    def get_current_language(self) -> Optional[str]:
        """Return current rotary dial position as language name, or None."""
        pass

    def set_interrupt_callback(self, callback: Callable):
        """Set callback for interrupt button press."""
        self._interrupt_callback = callback
        self._setup_interrupt_callback()

    def set_language_change_callback(self, callback: Callable[[str], None]):
        """Set callback for rotary dial change. Callback receives language name."""
        self._language_change_callback = callback
        self._setup_language_callback()

    @abstractmethod
    def _setup_interrupt_callback(self):
        """Internal: setup interrupt button callback."""
        pass

    @abstractmethod
    def _setup_language_callback(self):
        """Internal: setup rotary dial callback."""
        pass


class OrangePi5ProGPIOHandler(GPIOHandler):
    """GPIO handler for Orange Pi 5 Pro using gpiod."""

    GPIO_CHIP = "/dev/gpiochip1"
    INTERRUPT_PIN = 14
    ROTARY_PINS = {
        'german': 13,
        'spanish': 15,
        'arabic': 12,
        'french': 8,
    }
    BOUNCE_TIME = 0.05

    def __init__(self):
        super().__init__()
        import gpiod
        self._gpiod = gpiod
        self._chip = None
        self._interrupt_line = None
        self._rotary_lines = {}
        self._poll_thread = None
        self._last_interrupt_value = None
        self._last_rotary_values = {}
        self._last_press_times = {}

    def setup(self, add_interrupt_button=True, add_rotary_dial=True):
        self._chip = self._gpiod.Chip(self.GPIO_CHIP)

        # Interrupt button
        if add_interrupt_button:
            config = {self.INTERRUPT_PIN: self._gpiod.LineSettings(direction=self._gpiod.line.Direction.INPUT)}
            self._interrupt_line = self._chip.request_lines(consumer="interrupt", config=config)
            self._last_interrupt_value = self._interrupt_line.get_value(self.INTERRUPT_PIN)
            self._last_press_times['interrupt'] = 0

        # Rotary pins
        if add_rotary_dial:
            for lang, pin in self.ROTARY_PINS.items():
                config = {pin: self._gpiod.LineSettings(direction=self._gpiod.line.Direction.INPUT)}
                self._rotary_lines[lang] = self._chip.request_lines(consumer=f"rotary_{lang}", config=config)
                self._last_rotary_values[lang] = self._rotary_lines[lang].get_value(pin)
                self._last_press_times[lang] = 0

        parts = []
        if add_interrupt_button:
            parts.append(f"interrupt={self.INTERRUPT_PIN}")
        if add_rotary_dial:
            parts.append(f"rotary={self.ROTARY_PINS}")
        print(f"OrangePi5Pro GPIO: {', '.join(parts)}")

    def cleanup(self):
        self._running = False
        if self._poll_thread:
            self._poll_thread.join(timeout=0.5)

        if self._interrupt_line:
            try:
                self._interrupt_line.release()
            except:
                pass

        for line in self._rotary_lines.values():
            try:
                line.release()
            except:
                pass

    def is_interrupt_pressed(self) -> bool:
        val = self._interrupt_line.get_value(self.INTERRUPT_PIN)
        return val == self._gpiod.line.Value.INACTIVE

    def get_current_language(self) -> Optional[str]:
        for lang, pin in self.ROTARY_PINS.items():
            val = self._rotary_lines[lang].get_value(pin)
            if val == self._gpiod.line.Value.INACTIVE:
                return lang
        return None

    def _setup_interrupt_callback(self):
        self._start_polling()

    def _setup_language_callback(self):
        self._start_polling()

    def _start_polling(self):
        if self._running:
            return
        self._running = True
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._poll_thread.start()

    def _poll_loop(self):
        while self._running:
            try:
                now = time.time()

                # Interrupt button
                if self._interrupt_callback:
                    val = self._interrupt_line.get_value(self.INTERRUPT_PIN)
                    if val != self._last_interrupt_value:
                        if now - self._last_press_times['interrupt'] >= self.BOUNCE_TIME:
                            self._last_press_times['interrupt'] = now
                            if val == self._gpiod.line.Value.INACTIVE:
                                self._interrupt_callback()
                        self._last_interrupt_value = val

                # Rotary dial
                if self._language_change_callback:
                    for lang, pin in self.ROTARY_PINS.items():
                        val = self._rotary_lines[lang].get_value(pin)
                        if val != self._last_rotary_values[lang]:
                            if now - self._last_press_times[lang] >= self.BOUNCE_TIME:
                                self._last_press_times[lang] = now
                                if val == self._gpiod.line.Value.INACTIVE:
                                    self._language_change_callback(lang)
                            self._last_rotary_values[lang] = val

                time.sleep(0.01)
            except Exception as e:
                print(f"GPIO polling error: {e}")
                time.sleep(0.1)


class RaspberryPi5GPIOHandler(GPIOHandler):
    """GPIO handler for Raspberry Pi 5 using gpiozero."""

    INTERRUPT_PIN = 22
    ROTARY_PINS = {
        'german': 0,
        'spanish': 5,
        'arabic': 6,
        'french': 26,
    }
    BOUNCE_TIME = 0.05

    def __init__(self):
        super().__init__()
        from gpiozero import Button
        self._Button = Button
        self._interrupt_button = None
        self._rotary_buttons = {}

    def setup(self, add_interrupt_button=True, add_rotary_dial=True):
        if add_interrupt_button:
            self._interrupt_button = self._Button(
                self.INTERRUPT_PIN,
                pull_up=True,
                bounce_time=self.BOUNCE_TIME
            )

        if add_rotary_dial:
            for lang, pin in self.ROTARY_PINS.items():
                self._rotary_buttons[lang] = self._Button(
                    pin,
                    pull_up=True,
                    bounce_time=self.BOUNCE_TIME
                )

        parts = []
        if add_interrupt_button:
            parts.append(f"interrupt={self.INTERRUPT_PIN}")
        if add_rotary_dial:
            parts.append(f"rotary={self.ROTARY_PINS}")
        print(f"RaspberryPi5 GPIO: {', '.join(parts)}")

    def cleanup(self):
        if self._interrupt_button:
            self._interrupt_button.close()
        for btn in self._rotary_buttons.values():
            btn.close()

    def is_interrupt_pressed(self) -> bool:
        return self._interrupt_button.is_pressed

    def get_current_language(self) -> Optional[str]:
        for lang, btn in self._rotary_buttons.items():
            if btn.is_pressed:
                return lang
        return None

    def _setup_interrupt_callback(self):
        if self._interrupt_button and self._interrupt_callback:
            self._interrupt_button.when_pressed = self._interrupt_callback

    def _setup_language_callback(self):
        if self._language_change_callback:
            for lang, btn in self._rotary_buttons.items():
                btn.when_pressed = lambda l=lang: self._language_change_callback(l)


def get_gpio_handler() -> GPIOHandler:
    """Auto-detect and return appropriate GPIO handler."""
    try:
        from gpiozero import Button
        return RaspberryPi5GPIOHandler()
    except ImportError:
        pass

    try:
        import gpiod
        return OrangePi5ProGPIOHandler()
    except ImportError:
        pass

    raise RuntimeError("No GPIO library available (need gpiozero or gpiod)")


if __name__ == "__main__":
    print("Detecting GPIO handler...")
    handler = get_gpio_handler()
    print(f"Using: {handler.__class__.__name__}")

    print("\nSetting up GPIO...")
    handler.setup()

    def on_interrupt():
        print(">> INTERRUPT pressed!")

    def on_language_change(lang):
        print(f">> Language: {lang.upper()}")

    handler.set_interrupt_callback(on_interrupt)
    handler.set_language_change_callback(on_language_change)

    current_lang = handler.get_current_language()
    print(f"\nInitial language: {current_lang or 'none'}")
    print("Press buttons to test (Ctrl+C to exit)...\n")

    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nCleaning up...")
        handler.cleanup()
        print("Done.")
