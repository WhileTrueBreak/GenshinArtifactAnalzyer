import threading
from collections import deque
from enum import Enum
from typing import ClassVar

from rich.color import Color
from rich.panel import Panel
from rich.style import Style
from rich.text import Text


class LogLevel(Enum):
    INFO = 1
    WARNING = 2
    ERROR = 3
    CRITICAL = 4
    EXCEPTION = 5

class RichConsole:
    MESSAGE_COLORS: ClassVar[dict] = {
        LogLevel.INFO: '#ffffff',
        LogLevel.WARNING: '#f2fa02',
        LogLevel.ERROR: '#fa2302',
        LogLevel.CRITICAL: '#9b02fa',
        LogLevel.EXCEPTION: '#fa2302',
    }

    MAX_MESSAGES = 100
    MESSAGE_LOCK = threading.Lock()
    MESSAGES: ClassVar[deque] = deque(maxlen=MAX_MESSAGES)

    @staticmethod
    def fade_color(age, max_age, base_color='#ffffff'):
        if max_age == 0:
            return Style(color=base_color)
        color = Color.parse(base_color)
        r, g, b = color.get_truecolor().red, color.get_truecolor().green, color.get_truecolor().blue
        factor = max(0, 1 - (age / max_age) * (175 / 255))
        faded = f"#{int(r * factor):02x}{int(g * factor):02x}{int(b * factor):02x}"
        return Style(color=faded)

    @staticmethod
    def render_console_panel():
        with RichConsole.MESSAGE_LOCK:
            message_list = list(RichConsole.MESSAGES)
        message_list.reverse()
        content = Text()
        for i, (message, message_type) in enumerate(message_list):
            content.append(f"{message}\n", style=RichConsole.fade_color(i, RichConsole.MAX_MESSAGES, base_color=RichConsole.MESSAGE_COLORS[message_type]))
        return Panel(content,title='Status',border_style='#ff4d76',expand=True)

    @staticmethod
    def log(text, level=LogLevel.INFO, logger=None):
        with RichConsole.MESSAGE_LOCK:
            RichConsole.MESSAGES.append((text, level)) 
        if not logger: return
        if level == LogLevel.INFO:
            logger.info(text)
        elif level == LogLevel.WARNING:
            logger.warning(text)
        elif level == LogLevel.ERROR:
            logger.error(text)
        elif level == LogLevel.CRITICAL:
            logger.critical(text)
        elif level == LogLevel.EXCEPTION:
            logger.exception(text)

    @staticmethod
    def set_max_messages(max_messages):
        RichConsole.MAX_MESSAGES = max_messages
        RichConsole.MESSAGES: ClassVar[deque] = deque(maxlen=RichConsole.MAX_MESSAGES)
