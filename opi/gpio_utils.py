"""GPIO utilities for Orange Pi using gpiod."""

import threading
import time

# gpiod is only available on the Orange Pi target. Import lazily so that this
# module's constants (e.g. POSITION_KEYS) can be imported from a dev machine.
try:
    import gpiod
except ImportError:
    gpiod = None

# Orange Pi 5 Pro pin assignments (gpiochip1)
GPIO_CHIP = "/dev/gpiochip1"

# Pin mappings
INTERRUPT_BUTTON_PIN = 14
ROTARY_PINS = {
    'german': 13,
    'french': 8,
    'spanish': 15,
}

# Keyboard fallback for the 3-position rotary dial. Keys chosen to match the
# translator CLI's historical bindings (g=German, s=Spanish, f=French).
POSITION_KEYS = {
    'g': 'pos1',
    's': 'pos2',
    'f': 'pos3',
}


class Button:
    """Button interface for Orange Pi using gpiod."""

    def __init__(self, pin, chip=GPIO_CHIP, bounce_time=0.05):
        self.pin = pin
        self.chip_path = chip
        self.bounce_time = bounce_time
        self._when_pressed = None
        self._when_released = None
        self._running = False
        self._thread = None

        self._chip = gpiod.Chip(chip)
        config = {pin: gpiod.LineSettings(direction=gpiod.line.Direction.INPUT)}
        self._line = self._chip.request_lines(consumer="button", config=config)
        self._last_value = self._line.get_value(pin)
        self._last_press_time = 0

    @property
    def is_pressed(self):
        """Return True if button is currently pressed."""
        val = self._line.get_value(self.pin)
        return val == gpiod.line.Value.INACTIVE

    @property
    def when_pressed(self):
        return self._when_pressed

    @when_pressed.setter
    def when_pressed(self, callback):
        self._when_pressed = callback
        if callback is not None and not self._running:
            self._start_polling()

    @property
    def when_released(self):
        return self._when_released

    @when_released.setter
    def when_released(self, callback):
        self._when_released = callback
        if callback is not None and not self._running:
            self._start_polling()

    def _start_polling(self):
        """Start background thread to poll for button changes."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def _poll_loop(self):
        """Poll for button state changes."""
        while self._running:
            try:
                val = self._line.get_value(self.pin)
                now = time.time()

                if val != self._last_value:
                    if now - self._last_press_time >= self.bounce_time:
                        self._last_press_time = now

                        if val == gpiod.line.Value.INACTIVE:  # Pressed
                            if self._when_pressed:
                                self._when_pressed()
                        else:  # Released
                            if self._when_released:
                                self._when_released()

                    self._last_value = val

                time.sleep(0.01)
            except Exception as e:
                print(f"GPIO polling error: {e}")
                time.sleep(0.1)

    def close(self):
        """Clean up resources."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=0.5)
        try:
            self._line.release()
        except:
            pass


if __name__ == "__main__":
    """Test all buttons: interrupt + rotary dial (4 positions)."""

    print("Setting up buttons...")
    buttons = {}

    # Interrupt button
    try:
        buttons['interrupt'] = Button(INTERRUPT_BUTTON_PIN)
        buttons['interrupt'].when_pressed = lambda: print(">> INTERRUPT pressed!")
        print(f"  Interrupt button (pin {INTERRUPT_BUTTON_PIN}): OK")
    except Exception as e:
        print(f"  Interrupt button: FAILED - {e}")

    # Rotary dial positions
    for lang, pin in ROTARY_PINS.items():
        try:
            buttons[lang] = Button(pin)
            buttons[lang].when_pressed = lambda l=lang: print(f">> Rotary: {l.upper()} selected!")
            print(f"  Rotary {lang} (pin {pin}): OK")
        except Exception as e:
            print(f"  Rotary {lang}: FAILED - {e}")

    print(f"\n{len(buttons)} buttons ready. Press buttons to test (Ctrl+C to exit)...\n")

    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nCleaning up...")
        for btn in buttons.values():
            btn.close()
        print("Done.")
