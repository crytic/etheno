from collections.abc import Sequence
import subprocess

class Truffle(object):
    def __init__(self):
        self._running = False

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

        with subprocess.Popen(['/usr/bin/env', 'truffle'] + args) as p:
            def terminate():
                print("Terminating truffle %s..." % ''.join(args))
                try:
                    p.terminate()
                except OSError:
                    pass
            while True:
                try:
                    return p.wait(1.0)
                except subprocess.TimeoutExpired:
                    if not self._running:
                        terminate()
                        return None
                    continue
                except KeyboardInterrupt:
                    p.wait()
                    raise
