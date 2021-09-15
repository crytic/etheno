import enum
import logging
import os
import tempfile
import threading
import time
from typing import Callable, List, Optional, Union

import ptyprocess

CRITICAL = logging.CRITICAL
ERROR = logging.ERROR
WARNING = logging.WARNING
INFO = logging.INFO
DEBUG = logging.DEBUG
NOTSET = logging.NOTSET


class CGAColors(enum.Enum):
    BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE = range(8)


ANSI_RESET = "\033[0m"
ANSI_COLOR = "\033[1;%dm"
ANSI_BOLD = "\033[1m"

LEVEL_COLORS = {
    CRITICAL: CGAColors.MAGENTA,
    ERROR: CGAColors.RED,
    WARNING: CGAColors.YELLOW,
    INFO: CGAColors.GREEN,
    DEBUG: CGAColors.CYAN,
    NOTSET: CGAColors.BLUE
}


def formatter_message(message: str, use_color: bool = True) -> str:
    if use_color:
        message = message.replace("$RESET", RESET_SEQ).replace("$BOLD", BOLD_SEQ)
    else:
        message = message.replace("$RESET", "").replace("$BOLD", "")
    return message


class ComposableFormatter:
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
    def reformat(self, fmt: str) -> str:
        for color in CGAColors:
            fmt = fmt.replace("$%s" % color.name, ANSI_COLOR % (30 + color.value))
        fmt = fmt.replace('$RESET', ANSI_RESET)
        fmt = fmt.replace('$BOLD', ANSI_BOLD)
        return fmt

    @staticmethod
    def remove_color(fmt: str) -> str:
        for color in CGAColors:
            fmt = fmt.replace("$%s" % color.name, '')
        fmt = fmt.replace('$RESET', '')
        fmt = fmt.replace('$BOLD', '')
        fmt = fmt.replace('$LEVELCOLOR', '')
        return fmt

    def new_formatter(self, fmt: str, *args, **kwargs) -> logging.Formatter:
        if 'datefmt' in kwargs:
            kwargs['datefmt'] = self.reformat(kwargs['datefmt'])
        return super().new_formatter(self.reformat(fmt), *args, **kwargs)

    def format(self, *args, **kwargs) -> str:
        levelcolor = LEVEL_COLORS.get(args[0].levelno, LEVEL_COLORS[NOTSET])
        ret = self._parent_formatter.format(*args, **kwargs)
        ret = ret.replace('$LEVELCOLOR', ANSI_COLOR % (30 + levelcolor.value))
        ret = ret.replace('\n', self.reformat('$RESET $BOLD$BLUE\\$RESET\n'), 1)
        ret = ret.replace('\n', self.reformat('\n$RESET$BOLD$BLUE> $RESET'))
        return ret


class NonInfoFormatter(ComposableFormatter):
    _vanilla_formatter = logging.Formatter()

    def format(self, *args, **kwargs) -> str:
        if args and args[0].levelno == INFO:
            return self._vanilla_formatter.format(*args, **kwargs)
        else:
            return self._parent_formatter.format(*args, **kwargs)


ETHENO_LOGGERS = {}

_LOGGING_GETLOGGER = logging.getLogger


def getLogger(name: str):
    if name in ETHENO_LOGGERS:
        # TODO: Only enable this if Etheno was run as a standalone application
        ret = ETHENO_LOGGERS[name]
    else:
        ret = _LOGGING_GETLOGGER(name)
    # ####BEGIN####
    # Horrible hack to workaround Manticore's global logging system.
    # This can be removed after https://github.com/trailofbits/manticore/issues/1369
    # is resolved.
    if name.startswith('manticore'):
        ret.propagate = False
    # ####END####
    return ret


logging.getLogger = getLogger


class EthenoLogger:
    DEFAULT_FORMAT = '$RESET$LEVELCOLOR$BOLD%(levelname)-8s $BLUE[$RESET$WHITE%(asctime)14s$BLUE$BOLD]$NAME$RESET ' \
                     '%(message)s'
    
    def __init__(self,
                 name: str,
                 log_level: Optional[int] = None,
                 parent: Optional["EthenoLogger"] = None,
                 cleanup_empty: bool = False,
                 displayname: Optional[str] = None):
        if name in ETHENO_LOGGERS:
            raise Exception(f'An EthenoLogger instance for name {name} already exists: {ETHENO_LOGGERS[name]}')
        ETHENO_LOGGERS[name] = self
        self._directory: Optional[str] = None
        self.parent: Optional[EthenoLogger] = parent
        self.cleanup_empty: bool = cleanup_empty
        self.children: List[EthenoLogger] = []
        self._descendant_handlers = []
        if displayname is None:
            self.displayname: str = name
        else:
            self.displayname = displayname
        if log_level is None:
            if parent is None:
                raise ValueError('A logger must be provided a parent if `log_level` is None')
            log_level = parent.log_level
        self._log_level: int = log_level
        self._logger: logging.Logger = _LOGGING_GETLOGGER(name)
        self._handlers: List[logging.Handler] = [logging.StreamHandler()]
        if log_level is not None:
            self.log_level = log_level
        formatter = ColorFormatter(self.DEFAULT_FORMAT.replace('$NAME', self._name_format()), datefmt='%m$BLUE-$WHITE%d$BLUE|$WHITE%H$BLUE:$WHITE%M$BLUE:$WHITE%S')
        if self.parent is None:
            formatter = NonInfoFormatter(formatter)
        else:
            parent._add_child(self)
        self._handlers[0].setFormatter(formatter)  # type: ignore
        self._logger.addHandler(self._handlers[0])
        self._tmpdir = None

    def close(self):
        for child in self.children:
            child.close()
        if self.cleanup_empty:
            # first, check any files that handlers have created:
            for h in self._handlers:
                if isinstance(h, logging.FileHandler):
                    if h.stream is not None:
                        log_path = h.stream.name
                        if os.path.exists(log_path) and os.stat(log_path).st_size == 0:
                            h.close()
                            os.remove(log_path)
            # next, check if the output directory can be cleaned up
            if self.directory:
                for dirpath, dirnames, filenames in os.walk(self.directory, topdown=False):
                    if len(dirnames) == 0 and len(filenames) == 0 and dirpath != self.directory:
                        os.rmdir(dirpath)
        if self._tmpdir is not None:
            self._tmpdir.cleanup()
            self._tmpdir = None

    @property
    def directory(self) -> Optional[str]:
        return self._directory

    def _add_child(self, child):
        if child in self.children or any(c for c in self.children if c.name == child.name):
            raise ValueError("Cannot double-add child logger %s to logger %s" % (child.name, self.name))
        self.children.append(child)
        if self.directory is not None:
            child.save_to_directory(os.path.join(self.directory, child.name.replace(os.sep, '-')))
        else:
            child._tmpdir = tempfile.TemporaryDirectory()
            child.save_to_directory(child._tmpdir.name)
        parent = self
        while parent is not None:
            for handler in self._descendant_handlers:
                child.addHandler(handler, include_descendants=True)
            parent = parent.parent

    def _name_format(self):
        if self.parent is not None and self.parent.parent is not None:
            ret = self.parent._name_format()
        else:
            ret = ''
        return ret + "[$RESET$WHITE%s$BLUE$BOLD]" % self.displayname

    def addHandler(self, handler: logging.Handler, include_descendants: bool = True, set_log_level: bool = True):
        if set_log_level:
            handler.setLevel(self.log_level)
        self._logger.addHandler(handler)
        self._handlers.append(handler)
        if include_descendants:
            self._descendant_handlers.append(handler)
            for child in self.children:
                if isinstance(child, EthenoLogger):
                    child.addHandler(handler, include_descendants=include_descendants, set_log_level=set_log_level)
                else:
                    child.addHandler(handler)

    def make_logged_file(self, prefix=None, suffix=None, mode='w+b', dir: Optional[str] = None):
        """Returns an opened file stream to a unique file created according to the provided naming scheme"""
        if dir is None:
            dir = ''
        else:
            dir = os.path.relpath(os.path.realpath(dir), start=os.path.realpath(self.directory))
        os.makedirs(os.path.join(self.directory, dir), exist_ok=True)
        i = 1
        while True:
            if i == 1:
                filename = f"{prefix}{suffix}"
            else:
                filename = f"{prefix}{i}{suffix}"
            path = os.path.join(self.directory, dir, filename)
            if not os.path.exists(path):
                return open(path, mode)
            i += 1

    def make_constant_logged_file(self, contents: Union[str, bytes], *args, **kwargs):
        """Creates a logged file, populates it with the provided contents, and returns the absolute path to the file."""
        if isinstance(contents, str):
            contents = contents.encode('utf-8')
        with self.make_logged_file(*args, **kwargs) as f:
            f.write(contents)  # type: ignore
            return os.path.realpath(f.name)

    def to_log_path(self, absolute_path):
        if self.directory is None:
            return absolute_path
        absolute_path = os.path.realpath(absolute_path)
        dirpath = os.path.realpath(self.directory)
        return os.path.relpath(absolute_path, start=dirpath)

    def save_to_file(self, path, include_descendants=True, log_level=None):
        if log_level is None:
            log_level = self.log_level
        handler = logging.FileHandler(path)
        handler.setLevel(log_level)
        handler.setFormatter(logging.Formatter(ColorFormatter.remove_color(self.DEFAULT_FORMAT.replace('$NAME', self._name_format())), datefmt='%m-%d|%H:%M:%S'))
        self.addHandler(handler, include_descendants=include_descendants, set_log_level=False)

    def save_to_directory(self, path):
        if self.directory == path:
            # we are already set to save to this directory
            return
        elif self.directory is not None:
            raise ValueError("Logger %s's save directory is already set to %s" % (self.name, path))
        self._directory = os.path.realpath(path)
        os.makedirs(path, exist_ok=True)
        self.save_to_file(os.path.join(path, "%s.log" % self.name.replace(os.sep, '-')), include_descendants=False, log_level=DEBUG)
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
        for handler in self._handlers:
            handler.setLevel(level)

    def __getattr__(self, name):
        return getattr(self._logger, name)

    def __repr__(self):
        return f'{type(self).__name__}(name={self.name!r}, log_level={self.log_level!r}, parent={self.parent!r}, cleanup_empty={self.cleanup_empty!r}, displayname={self.displayname!r})'

    
class StreamLogger(threading.Thread):
    def __init__(self, logger: logging.Logger, *streams, newline_char=b'\n'):
        super().__init__(daemon=True)
        self.logger: logging.Logger = logger
        self.streams = streams
        if isinstance(newline_char, str):
            newline_char = newline_char.encode('utf-8')
        self._newline_char = newline_char
        self._buffers = [b'' for i in range(len(streams))]
        self._done: bool = False
        self.log: Callable[[logging.Logger, Union[str, bytes]], ...] = lambda lgr, message: lgr.info(message)

    def is_done(self) -> bool:
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
                                self.log(self.logger, self._buffers[i].decode())
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
    def __init__(self, logger, args, cwd=None, **kwargs):
        self.process = ptyprocess.PtyProcessUnicode.spawn(args, cwd=cwd)
        super().__init__(logger, self.process, **kwargs)

    def is_done(self):
        return not self.process.isalive()

    def __getattr__(self, name):
        return getattr(self.process, name)


if __name__ == '__main__':
    logger = EthenoLogger('Testing', DEBUG)
    logger.info('Info')
    logger.critical('Critical')
