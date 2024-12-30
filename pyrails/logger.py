import logging
import sys


class ColorFormatter(logging.Formatter):
    """Custom formatter matching the exact spacing shown"""

    COLORS = {
        'DEBUG': '\033[36m',
        'INFO': '\033[32m',
        'WARNING': '\033[33m',
        'ERROR': '\033[31m',
        'CRITICAL': '\033[35m',
        'RESET': '\033[0m'
    }

    def format(self, record):
        levelname = record.levelname
        if levelname in self.COLORS:
            return f"{self.COLORS[levelname]}{levelname}{self.COLORS['RESET']}:{' ' * (9 - len(levelname))}{record.getMessage()}"



logger = logging.getLogger("pyrails")
logger.setLevel(logging.DEBUG)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(ColorFormatter())
logger.addHandler(console_handler)