from collections.abc import Sequence
import shlex
import time

from typing import Iterable

from .logger import EthenoLogger, PtyLogger


def make_list(args: Iterable):
    if isinstance(args, str):
        return shlex.split(args)
    elif isinstance(args, Sequence) and not isinstance(args, bytes):
        if isinstance(args, list):
            return args
        else:
            return list(args)
    else:
        return [args]


class Truffle(object):
    def __init__(self, truffle_cmd='truffle', parent_logger=None, log_level=None):
        self._running = False
        self.logger = EthenoLogger('Truffle', log_level=log_level, parent=parent_logger)
        self.truffle_cmd = make_list(truffle_cmd)

    def terminate(self):
        self._running = False

    def run_tests(self):
        return self.run('test')

    def run_migrate(self):
        return self.run('migrate')

    def run(self, args):
        self._running = True
        args = make_list(args)

        p = PtyLogger(self.logger, ['/usr/bin/env'] + self.truffle_cmd + args)
        p.start()

        try:
            while p.isalive():
                if not self._running:
                    self.logger.info("Etheno received a shutdown signal; terminating truffle %s" % ' '.join(args))
                    break
                time.sleep(1.0)
        except KeyboardInterrupt as e:
            self.logger.info("Caught keyboard interrupt; terminating truffle %s" % ' '.join(args))
            raise e
        finally:
            p.close(force=True)
        return p.wait()
