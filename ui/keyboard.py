"""
Keyboard event handler for dashboard controls
"""

import threading
import sys
import tty
import termios
from typing import Callable, Optional
import logging

logger = logging.getLogger(__name__)


class KeyboardHandler:
    """Non-blocking keyboard input handler"""

    def __init__(self, on_key_press: Optional[Callable[[str], None]] = None):
        self.on_key_press = on_key_press
        self.running = False
        self.thread = None
        self.paused = False

    def start(self):
        """Start listening for keyboard input"""
        self.running = True
        self.thread = threading.Thread(target=self._listen, daemon=True)
        self.thread.start()
        logger.info("Keyboard handler started")

    def stop(self):
        """Stop listening for keyboard input"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1)
        logger.info("Keyboard handler stopped")

    def _listen(self):
        """Listen for keyboard input in a thread"""
        # Save terminal settings
        old_settings = termios.tcgetattr(sys.stdin)

        try:
            # Set terminal to raw mode
            tty.setraw(sys.stdin.fileno())

            while self.running:
                # Check if input is available
                if sys.stdin in select.select([sys.stdin], [], [], 0.1)[0]:
                    key = sys.stdin.read(1)
                    if self.on_key_press:
                        self.on_key_press(key)
        except Exception as e:
            logger.error(f"Keyboard handler error: {e}")
        finally:
            # Restore terminal settings
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

    def handle_key(self, key: str, bot, dashboard) -> bool:
        """Handle key press (returns False to quit)"""
        if key == 'q':
            logger.info("Quit requested by user")
            return False
        elif key == 'p':
            self.paused = not self.paused
            status = "paused" if self.paused else "resumed"
            logger.info(f"Bot {status}")
        elif key == 'r':
            logger.info("Manual refresh requested")
            # Refresh is automatic in Live display
        elif key == 's':
            logger.warning("Emergency stop requested!")
            if hasattr(bot, 'trader'):
                bot.trader.emergency_stop()
        elif key == 'c':
            logger.info("Command mode not yet implemented")
            # TODO: Implement command mode

        return True


# Fallback for systems without select
try:
    import select
except ImportError:
    # Windows fallback
    import msvcrt

    class KeyboardHandler:
        """Windows-compatible keyboard handler"""

        def __init__(self, on_key_press: Optional[Callable[[str], None]] = None):
            self.on_key_press = on_key_press
            self.running = False
            self.thread = None
            self.paused = False

        def start(self):
            self.running = True
            self.thread = threading.Thread(target=self._listen, daemon=True)
            self.thread.start()

        def stop(self):
            self.running = False
            if self.thread:
                self.thread.join(timeout=1)

        def _listen(self):
            while self.running:
                if msvcrt.kbhit():
                    key = msvcrt.getch().decode('utf-8')
                    if self.on_key_press:
                        self.on_key_press(key)
                threading.Event().wait(0.1)

        def handle_key(self, key: str, bot, dashboard) -> bool:
            if key == 'q':
                return False
            elif key == 'p':
                self.paused = not self.paused
                logger.info(f"Bot {'paused' if self.paused else 'resumed'}")
            elif key == 's':
                logger.warning("Emergency stop!")
                if hasattr(bot, 'trader'):
                    bot.trader.emergency_stop()
            return True
