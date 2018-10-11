#!/usr/bin/env python3

import atexit
import json
import socket
import subprocess
import time
from urllib.request import urlopen
from urllib.error import HTTPError, URLError

def webserver_is_up(url):
    try:
        return urlopen(url).getcode()
    except HTTPError:
        # This means we connected
        return True
    except URLError:
        return False

def is_port_free(port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    return sock.connect_ex(('127.0.0.1', port)) != 0

def find_open_port(starting_port=1025):
    for port in range(starting_port, 65536):
        if is_port_free(port):
            return port
    return -1

class RpcHttpProxy(object):
    def __init__(self, urlstring):
        self.urlstring = urlstring
        self.rpc_id = 0
    def post(self, data):
        data = dict(data)
        self.rpc_id += 1
        rpc_id = self.rpc_id
        return_id = None
        if 'jsonrpc' not in data:
            data['jsonrpc'] = '2.0'
        if 'id' in data:
            return_id = data['id']
            data['id'] = self.rpc_id
        ret = json.loads(urlopen(self.urlstring, data = bytearray(json.dumps(data), 'utf8')).read())
        if return_id is not None and 'id' in ret:
            ret['id'] = return_id
        return ret

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
