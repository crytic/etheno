from collections.abc import Sequence
import time

from .logger import EthenoLogger, PtyLogger

class Truffle(object):
    def __init__(self, parent_logger=None, log_level=None):
        self._running = False
        self.logger = EthenoLogger('Truffle', log_level=log_level, parent=parent_logger)

    def terminate(self):
        self._running = False

    def run_tests(self):
        return self.run('test')

    def run_migrate(self):
        return self.run('migrate')

    def run(self, args):
        self._running = True
        if isinstance(args, Sequence):
            if not isinstance(args, list):
                args = list(args)
        else:
            args = [args]

        p = PtyLogger(self.logger, ['/usr/bin/env', 'truffle'] + args)
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
