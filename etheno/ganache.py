#!/usr/bin/env python3

import atexit
import subprocess
import time

from .client import RpcHttpProxy, SelfPostingClient
from .utils import is_port_free

class Ganache(RpcHttpProxy):
    def __init__(self, args=None, port=8546):
        super().__init__("http://127.0.0.1:%d/" % port)
        self.port = port
        if args is None:
            self.args = []
        else:
            self.args = ['/usr/bin/env', 'ganache-cli', '-d', '-p', str(port)] + args
        self.ganache = None
    def start(self):
        if self.ganache:
            return
        self.ganache = subprocess.Popen(self.args)
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

if __name__ == "__main__":
    ganache = Ganache()
    ganache.start()
    print(ganache.post({
        'jsonrpc': '2.0',
        'method': 'eth_accounts',
        'params': [],
        'id': 1
    }))

class GanacheClient(SelfPostingClient):
    def wait_until_running(self):
        while is_port_free(self.client.port):
            time.sleep(0.25)
    def shutdown(self):
        self.client.stop()
