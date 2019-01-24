#!/usr/bin/env python3

import atexit
import subprocess
import time

from .client import RpcHttpProxy, SelfPostingClient
from .logger import PtyLogger
from .utils import is_port_free

class Ganache(RpcHttpProxy):
    def __init__(self, args=None, port=8546):
        super().__init__("http://127.0.0.1:%d/" % port)
        self.port = port
        if args is None:
            args = []
        self.args = ['/usr/bin/env', 'ganache-cli', '-d', '-p', str(port)] + args
        self.ganache = None
        self._client = None
    def start(self):
        if self.ganache:
            return
        if self._client:
            self.ganache = PtyLogger(self._client.logger, self.args)
            self.ganache.start()
        else:
            self.ganache = subprocess.Popen(self.args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=1)
        atexit.register(Ganache.stop.__get__(self, Ganache))
        # wait until Ganache has started listening:
        while is_port_free(self.port):
            time.sleep(0.25)
    def post(self, data):
        if self.ganache is None:
            self.start()
        return super().post(data)
    def stop(self):
        if self.ganache is not None:
            ganache = self.ganache
            self.ganache = None
            ganache.terminate()
            ganache.wait()
            if isinstance(ganache, PtyLogger):
                ganache.close()

if __name__ == "__main__":
    ganache = Ganache()
    ganache.start()

class GanacheClient(SelfPostingClient):
    def __init__(self, ganache_instance):
        super().__init__(ganache_instance)
        ganache_instance._client = self
        self.short_name = "Ganache@%d" % ganache_instance.port
    def wait_until_running(self):
        while is_port_free(self.client.port):
            time.sleep(0.25)
    def shutdown(self):
        self.client.stop()
