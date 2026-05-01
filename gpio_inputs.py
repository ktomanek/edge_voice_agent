"""GPIO input abstraction for different single-board computers.

Provides unified interface for:
- Interrupt button
- Rotary dial (3-position selector)

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

    POSITIONS = ['pos1', 'pos2', 'pos3']
    LONG_PRESS_DURATION = 2.0  # seconds

    def __init__(self):
        self._interrupt_callback: Optional[Callable] = None
        self._long_press_callback: Optional[Callable] = None
        self._position_change_callback: Optional[Callable[[str], None]] = None
        self._running = False

    @abstractmethod
    def setup(self, add_interrupt_button=True, add_rotary_dial=True):
        """Initialize GPIO pins.

        Args:
            add_interrupt_button: If True, setup interrupt button.
            add_rotary_dial: If True, setup rotary dial.
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
    def get_current_position(self) -> Optional[str]:
        """Return current rotary dial position ('pos1'/'pos2'/'pos3'), or None."""
        pass

    def set_interrupt_callback(self, callback: Callable):
        """Set callback for interrupt button short press."""
        self._interrupt_callback = callback
        self._setup_interrupt_callback()

    def set_long_press_callback(self, callback: Callable):
        """Set callback for interrupt button long press (3+ seconds)."""
        self._long_press_callback = callback
        self._setup_interrupt_callback()

    def set_position_change_callback(self, callback: Callable[[str], None]):
        """Set callback for rotary dial change. Callback receives position name."""
        self._position_change_callback = callback
        self._setup_position_callback()

    @abstractmethod
    def _setup_interrupt_callback(self):
        """Internal: setup interrupt button callback."""
        pass

    @abstractmethod
    def _setup_position_callback(self):
        """Internal: setup rotary dial callback."""
        pass


class OrangePi5ProGPIOHandler(GPIOHandler):
    """GPIO handler for Orange Pi 5 Pro using gpiod."""

    GPIO_CHIP = "/dev/gpiochip1"
    INTERRUPT_PIN = 14
    # Rotary dial positions. The translator CLI maps these to:
    #   pos1 -> german, pos2 -> spanish, pos3 -> french
    ROTARY_PINS = {
        'pos1': 13,
        'pos2': 15,
        'pos3': 8,
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
        self._interrupt_press_start = None  # For long press detection

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
            for pos, pin in self.ROTARY_PINS.items():
                config = {pin: self._gpiod.LineSettings(direction=self._gpiod.line.Direction.INPUT)}
                self._rotary_lines[pos] = self._chip.request_lines(consumer=f"rotary_{pos}", config=config)
                self._last_rotary_values[pos] = self._rotary_lines[pos].get_value(pin)
                self._last_press_times[pos] = 0

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

    def get_current_position(self) -> Optional[str]:
        for pos, pin in self.ROTARY_PINS.items():
            val = self._rotary_lines[pos].get_value(pin)
            if val == self._gpiod.line.Value.INACTIVE:
                return pos
        return None

    def _setup_interrupt_callback(self):
        self._start_polling()

    def _setup_position_callback(self):
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

                # Interrupt button with long press detection
                if self._interrupt_line and (self._interrupt_callback or self._long_press_callback):
                    val = self._interrupt_line.get_value(self.INTERRUPT_PIN)
                    is_pressed = (val == self._gpiod.line.Value.INACTIVE)

                    if is_pressed and self._interrupt_press_start is None:
                        # Button just pressed
                        self._interrupt_press_start = now
                    elif not is_pressed and self._interrupt_press_start is not None:
                        # Button just released - check duration
                        press_duration = now - self._interrupt_press_start
                        self._interrupt_press_start = None

                        if press_duration >= self.LONG_PRESS_DURATION:
                            if self._long_press_callback:
                                self._long_press_callback()
                        else:
                            if self._interrupt_callback:
                                self._interrupt_callback()

                # Rotary dial
                if self._position_change_callback:
                    for pos, pin in self.ROTARY_PINS.items():
                        val = self._rotary_lines[pos].get_value(pin)
                        if val != self._last_rotary_values[pos]:
                            if now - self._last_press_times[pos] >= self.BOUNCE_TIME:
                                self._last_press_times[pos] = now
                                if val == self._gpiod.line.Value.INACTIVE:
                                    self._position_change_callback(pos)
                            self._last_rotary_values[pos] = val

                time.sleep(0.01)
            except Exception as e:
                print(f"GPIO polling error: {e}")
                time.sleep(0.1)


class RaspberryPi5GPIOHandler(GPIOHandler):
    """GPIO handler for Raspberry Pi 5 using gpiozero."""

    INTERRUPT_PIN = 22
    # Rotary dial positions. The translator CLI maps these to:
    #   pos1 -> german, pos2 -> spanish, pos3 -> french
    ROTARY_PINS = {
        'pos1': 23,
        'pos2': 24,
        'pos3': 27,
    }
    BOUNCE_TIME = 0.05

    def __init__(self):
        super().__init__()
        from gpiozero import Button
        self._Button = Button
        self._interrupt_button = None
        self._rotary_buttons = {}
        self._interrupt_press_start = None  # For long press detection

    def setup(self, add_interrupt_button=True, add_rotary_dial=True):
        if add_interrupt_button:
            self._interrupt_button = self._Button(
                self.INTERRUPT_PIN,
                pull_up=True,
                bounce_time=self.BOUNCE_TIME
            )

        if add_rotary_dial:
            for pos, pin in self.ROTARY_PINS.items():
                self._rotary_buttons[pos] = self._Button(
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

    def get_current_position(self) -> Optional[str]:
        for pos, btn in self._rotary_buttons.items():
            if btn.is_pressed:
                return pos
        return None

    def _setup_interrupt_callback(self):
        if self._interrupt_button:
            self._interrupt_button.when_pressed = self._on_interrupt_pressed
            self._interrupt_button.when_released = self._on_interrupt_released

    def _on_interrupt_pressed(self):
        self._interrupt_press_start = time.time()

    def _on_interrupt_released(self):
        if self._interrupt_press_start is None:
            return
        press_duration = time.time() - self._interrupt_press_start
        self._interrupt_press_start = None

        if press_duration >= self.LONG_PRESS_DURATION:
            if self._long_press_callback:
                self._long_press_callback()
        else:
            if self._interrupt_callback:
                self._interrupt_callback()

    def _setup_position_callback(self):
        if self._position_change_callback:
            for pos, btn in self._rotary_buttons.items():
                btn.when_pressed = lambda p=pos: self._position_change_callback(p)


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

    def on_position_change(pos):
        print(f">> Position: {pos.upper()}")

    handler.set_interrupt_callback(on_interrupt)
    handler.set_position_change_callback(on_position_change)

    current_pos = handler.get_current_position()
    print(f"\nInitial position: {current_pos or 'none'}")
    print("Press buttons to test (Ctrl+C to exit)...\n")

    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nCleaning up...")
        handler.cleanup()
        print("Done.")
