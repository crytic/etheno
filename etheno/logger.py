import enum
import logging
import threading
import time

CRITICAL = logging.CRITICAL
ERROR    = logging.ERROR
WARNING  = logging.WARNING
INFO     = logging.INFO
DEBUG    = logging.DEBUG
NOTSET   = logging.NOTSET

class CGAColors(enum.Enum):
    BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE = range(8)

ANSI_RESET = "\033[0m"
ANSI_COLOR = "\033[1;%dm"
ANSI_BOLD  = "\033[1m"

LEVEL_COLORS = {
    CRITICAL: CGAColors.MAGENTA,
    ERROR: CGAColors.RED,
    WARNING: CGAColors.YELLOW,
    INFO: CGAColors.GREEN,
    DEBUG: CGAColors.CYAN,
    NOTSET: CGAColors.BLUE
}

def formatter_message(message, use_color = True):
    if use_color:
        message = message.replace("$RESET", RESET_SEQ).replace("$BOLD", BOLD_SEQ)
    else:
        message = message.replace("$RESET", "").replace("$BOLD", "")
    return message

class ComposableFormatter(object):
    def __init__(self, *args, **kwargs):
        if len(args) == 1 and not isinstance(args[0], str):
            self._parent_formatter = args[0]
        else:
            self._parent_formatter = self.new_formatter(*args, **kwargs)
    def new_formatter(self, *args, **kwargs):
        return logging.Formatter(*args, **kwargs)
    def __getattr__(self, name):
        return getattr(self._parent_formatter, name)

class ColorFormatter(ComposableFormatter):
    def reformat(self, fmt):
        for color in CGAColors:
            fmt = fmt.replace("$%s" % color.name, ANSI_COLOR % (30 + color.value))
        fmt = fmt.replace("$RESET", ANSI_RESET)
        fmt = fmt.replace("$BOLD", ANSI_BOLD)
        return fmt
    def new_formatter(self, fmt, *args, **kwargs):
        if 'datefmt' in kwargs:
            kwargs['datefmt'] = self.reformat(kwargs['datefmt'])
        return super().new_formatter(self.reformat(fmt), *args, **kwargs)
    def format(self, *args, **kwargs):
        levelcolor = LEVEL_COLORS.get(args[0].levelno, LEVEL_COLORS[NOTSET])
        ret = self._parent_formatter.format(*args, **kwargs)
        return ret.replace('$LEVELCOLOR', ANSI_COLOR % (30 + levelcolor.value))

class NonInfoFormatter(ComposableFormatter):
    _vanilla_formatter = logging.Formatter()
    def format(self, *args, **kwargs):
        if args and args[0].levelno == INFO:
            return self._vanilla_formatter.format(*args, **kwargs)
        else:
            return self._parent_formatter.format(*args, **kwargs)

class EthenoLogger(object):
    def __init__(self, name, log_level=None, parent=None):
        self.parent = parent
        self.children = []
        if parent is not None:
            parent.children.append(self)
        if log_level is None:
            if parent is None:
                raise ValueError('A logger must be provided a parent if `log_level` is None')
            log_level = parent.log_level
        self._log_level = log_level
        self._logger = logging.getLogger(name)
        self._handler = logging.StreamHandler()
        if log_level is not None:
            self.log_level = log_level
        formatter = ColorFormatter('$RESET$LEVELCOLOR$BOLD%(levelname)-8s $BLUE[$RESET$WHITE%(asctime)14s$BLUE$BOLD][$RESET$WHITE%(name)s$BLUE$BOLD]$RESET %(message)s', datefmt='%m$BLUE-$WHITE%d$BLUE|$WHITE%H$BLUE:$WHITE%M$BLUE:$WHITE%S')
        if self.parent is None:
            formatter = NonInfoFormatter(formatter)
        self._handler.setFormatter(formatter)
        self._logger.addHandler(self._handler)

    @property
    def log_level(self):
        if self._log_level is None:
            if self.parent is None:
                raise ValueError('A logger must be provided a parent if `log_level` is None')
            return self.parent.log_level
        else:
            return self._log_level

    @log_level.setter
    def log_level(self, level):
        if not isinstance(level, int):
            try:
                level = getattr(logging, str(level).upper())
            except AttributeError:
                raise ValueError("Invalid log level: %s" % level)
        elif level not in (CRITICAL, ERROR, WARNING, INFO, DEBUG):
            raise ValueError("Invalid log level: %d" % level)
        self._log_level = level
        self._logger.setLevel(level)
        self._handler.setLevel(level)        

    def __getattr__(self, name):
        return getattr(self._logger, name)

class StreamLogger(threading.Thread):
    def __init__(self, logger, *streams):
        super().__init__(daemon=True)
        self.logger = logger
        self.streams = streams
        self.start()
    def is_done(self):
        return False
    def run(self):
        while not self.is_done():
            got_line = False
            for stream in self.streams:
                line = stream.readline()
                if line:
                    got_line = True
                    self.logger.info(line.decode().strip())
            if not got_line:
                time.sleep(0.5)

class ProcessLogger(StreamLogger):
    def __init__(self, logger, process):
        self.process = process
        super().__init__(logger, process.stdout, process.stderr)
    def is_done(self):        
        return self.process.poll() is not None

if __name__ == '__main__':
    logger = EthenoLogger('Testing', DEBUG)
    logger.info('Info')
    logger.critical('Critical')
