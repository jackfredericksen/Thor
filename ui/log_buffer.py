"""
Thread-safe log buffer for dashboard display
"""

import threading
import logging
from collections import deque
from datetime import datetime
from typing import Dict, List


class LogBuffer:
    """Thread-safe circular buffer for log messages"""

    def __init__(self, max_size: int = 1000):
        self.buffer = deque(maxlen=max_size)
        self.lock = threading.Lock()

    def add(self, record: logging.LogRecord) -> None:
        """Add a log record to the buffer"""
        with self.lock:
            self.buffer.append({
                'timestamp': datetime.fromtimestamp(record.created),
                'level': record.levelname,
                'message': record.getMessage(),
                'module': record.module,
            })

    def get_recent(self, count: int = 50) -> List[Dict]:
        """Get recent log entries"""
        with self.lock:
            return list(self.buffer)[-count:]

    def clear(self) -> None:
        """Clear the buffer"""
        with self.lock:
            self.buffer.clear()

    def get_level_color(self, level: str) -> str:
        """Get color for log level"""
        colors = {
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'bright_red',
        }
        return colors.get(level, 'white')
