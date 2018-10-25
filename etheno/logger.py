import logging

CRITICAL = logging.CRITICAL
ERROR    = logging.ERROR
WARNING  = logging.WARNING
INFO     = logging.INFO
DEBUG    = logging.DEBUG
NOTSET   = logging.NOTSET

class NonInfoFormatter(object):
    def __init__(self, parent_formatter):
        self._parent_formatter = parent_formatter
        self._vanilla_formatter = logging.Formatter()
    def format(self, *args, **kwargs):
        if args and args[0].levelno == INFO:
            return self._vanilla_formatter.format(*args, **kwargs)
        else:
            return self._parent_formatter.format(*args, **kwargs)
    def __getattr__(self, name):
        return getattr(self._parent_formatter, name)

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
        formatter = logging.Formatter('%(levelname)-8s [%(asctime)14s][%(name)s] %(message)s', datefmt='%m-%d|%H:%M:%S')
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

if __name__ == '__main__':
    logger = EthenoLogger('Testing', DEBUG)
    logger.info('Info')
    logger.critical('Critical')
