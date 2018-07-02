#!/usr/bin/env python2

import atexit
import json
import socket
import subprocess
import time
import urllib2

def is_port_free(port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    return sock.connect_ex(('127.0.0.1', port)) != 0

def find_open_port(starting_port = 1025):
    for port in range(starting_port, 65536):
        if is_port_free(port):
            return port
    return -1

class Ganache(object):
    def __init__(self, args = None, port = 8546):
        self.port = port
        self.rpc_id = 0
        if args is None:
            args = []
        args = ['/usr/bin/env', 'ganache-cli', '-d', '-p', str(port)] + args
        self.ganache = subprocess.Popen(args)
        atexit.register(Ganache.shutdown.__get__(self, Ganache))
        # wait until Ganache has started listening:
        while is_port_free(self.port):
            time.sleep(0.25)
    def post(self, data):
        data = dict(data)
        self.rpc_id += 1
        rpc_id = self.rpc_id
        return_id = None
        if 'id' in data:
            return_id = data['id']
            data['id'] = self.rpc_id
        ret = json.loads(urllib2.urlopen("http://127.0.0.1:%d/" % self.port, data = json.dumps(data)).read())
        if return_id is not None and 'id' in ret:
            ret['id'] = return_id
        return ret
    def shutdown(self):
        if self.ganache is not None:
            ganache = self.ganache
            self.ganache = None
            ganache.terminate()
            ganache.wait()

if __name__ == "__main__":
    ganache = Ganache()
    print ganache.post({
        'jsonrpc': '2.0',
        'method': 'eth_accounts',
        'params': [],
        'id': 1
    })
