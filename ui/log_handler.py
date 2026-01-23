"""
Custom logging handler for dashboard integration
"""

import logging
from .log_buffer import LogBuffer


class DashboardLogHandler(logging.Handler):
    """Log handler that writes to dashboard buffer"""

    def __init__(self, log_buffer: LogBuffer):
        super().__init__()
        self.log_buffer = log_buffer

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a log record to the buffer"""
        try:
            self.log_buffer.add(record)
        except Exception:
            self.handleError(record)
