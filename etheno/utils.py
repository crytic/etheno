import math
import socket
from urllib.request import urlopen
from urllib.error import HTTPError, URLError

def int_to_bytes(n):
    number_of_bytes = int(math.ceil(n.bit_length() / 8))
    return n.to_bytes(number_of_bytes, byteorder='big')

def decode_hex(data):
    if data is None:
        return None
    if data.startswith('0x'):
        data = data[2:]
    return bytes.fromhex(data)

def decode_value(v):
    if isinstance(v, int):
        return v
    elif v.startswith('0x') or (frozenset(['a', 'b', 'c', 'd', 'e', 'f']) & frozenset(v)):
        # this is a hex string
        return int(v, 16)
    else:
        # assume it is a regular int
        return int(v)

def format_hex_address(addr):
    if addr is None:
        return None
    if isinstance(addr, int):
        addr = "%x" % addr
    if addr.lower().startswith('0x'):
        addr = addr[2:]
    if len(addr) < 40:
        addr = "%s%s" % ('0' * (40 - len(addr)), addr)
    return addr

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
