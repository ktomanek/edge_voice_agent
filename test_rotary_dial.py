"""Rotary dial diagnostic.

Prints (a) the live position polled twice per second and (b) every press
event reported by the GPIO handler. Useful for verifying wiring before
running the full voice agent.

Usage:
    python test_rotary_dial.py rpi5
    python test_rotary_dial.py opi5
"""

import sys
import time

from gpio_inputs import RaspberryPi5GPIOHandler, OrangePi5ProGPIOHandler


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ('rpi5', 'opi5'):
        print("Usage: python test_rotary_dial.py [rpi5|opi5]")
        sys.exit(1)

    handler = RaspberryPi5GPIOHandler() if sys.argv[1] == 'rpi5' else OrangePi5ProGPIOHandler()
    handler.setup(add_interrupt_button=True, add_rotary_dial=True)

    print(f"Pin map: {handler.ROTARY_PINS}")
    print("Turn the dial through all 3 positions. Press the interrupt button to test it.")
    print("Ctrl+C to exit.\n")

    handler.set_position_change_callback(
        lambda pos: print(f"  [event] position changed -> {pos}")
    )
    handler.set_interrupt_callback(
        lambda: print("  [event] interrupt button pressed")
    )

    last = object()  # sentinel so first read always prints
    try:
        while True:
            current = handler.get_current_position()
            if current != last:
                print(f"  [poll]  current position = {current}")
                last = current
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nCleaning up...")
        handler.cleanup()


if __name__ == "__main__":
    main()
