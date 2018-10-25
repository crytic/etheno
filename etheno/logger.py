import enum
import logging
import os
import threading
import time

import ptyprocess

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
        ret = ret.replace('$LEVELCOLOR', ANSI_COLOR % (30 + levelcolor.value))
        ret = ret.replace('\n', self.reformat('$RESET $BOLD$BLUE\\$RESET\n'), 1)
        ret = ret.replace('\n', self.reformat('\n$RESET$BOLD$BLUE> $RESET'))
        return ret

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
        self._descendant_handlers = []
        if parent is not None:
            parent._add_child(self)
        if self.parent is None:
            formatter = NonInfoFormatter(formatter)
        self._handler.setFormatter(formatter)
        self._logger.addHandler(self._handler)
        self._directory = None

    def _add_child(self, child):
        self.children.append(child)
        parent = self
        while parent is not None:
            for handler in self._descendant_handlers:
                child.addHandler(handler, include_descendants=True)
            if parent._directory is not None:
                child.save_to_directory(os.path.join(parent._directory, child.name))
            parent = parent.parent

    def addHandler(self, handler, include_descendants=True):
        self._logger.addHandler(handler)
        if include_descendants:
            self._descendant_handlers.append(handler)
            for child in self.children:
                if isinstance(child, EthenoLogger):
                    child.addHandler(handler, include_descendants=include_descendants)
                else:
                    child.addHandler(handler)

    def save_to_file(self, path, include_descendants=True):
        handler = logging.FileHandler(path)
        handler.setFormatter(logging.Formatter('%(levelname)-8s [%(asctime)14s][%(name)s] %(message)s', datefmt='%m-%d|%H:%M:%S'))
        self.addHandler(handler, include_descendants=include_descendants)

    def save_to_directory(self, path):
        self._directory = path
        os.makedirs(path, exist_ok=True)
        self.save_to_file(os.path.join(path, "%s.log" % self.name), include_descendants=False)
        for child in self.children:
            child.save_to_directory(os.path.join(path, child.name))

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
    def __init__(self, logger, *streams, newline_char=b'\n'):
        super().__init__(daemon=True)
        self.logger = logger
        self.streams = streams
        if isinstance(newline_char, str):
            newline_char = newline_char.encode('utf-8')
        self._newline_char = newline_char
        self._buffers = [b'' for i in range(len(streams))]
        self.start()
        self._done = False
    def is_done(self):
        return self._done
    def run(self):
        while not self.is_done():
            while True:
                got_byte = False
                try:
                    for i, stream in enumerate(self.streams):
                        byte = stream.read(1)
                        while byte is not None and len(byte):
                            if isinstance(byte, str):
                                byte = byte.encode('utf-8')
                            if byte == self._newline_char:
                                self.logger.info(self._buffers[i].decode())
                                self._buffers[i] = b''
                            else:
                                self._buffers[i] += byte
                            got_byte = True
                            byte = stream.read(1)
                except Exception:
                    self._done = True
                if not got_byte or self._done:
                    break
            time.sleep(0.5)

class ProcessLogger(StreamLogger):
    def __init__(self, logger, process):
        self.process = process
        super().__init__(logger, open(process.stdout.fileno(), buffering=1), open(process.stderr.fileno(), buffering=1))
    def is_done(self):
        return self.process.poll() is not None

class PtyLogger(StreamLogger):
    def __init__(self, logger, args, **kwargs):
        self.process = ptyprocess.PtyProcessUnicode.spawn(args)
        super().__init__(logger, self.process, **kwargs)
    def is_done(self):
        return not self.process.isalive()
    def __getattr__(self, name):
        return getattr(self.process, name)
    
if __name__ == '__main__':
    logger = EthenoLogger('Testing', DEBUG)
    logger.info('Info')
    logger.critical('Critical')
