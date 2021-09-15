import math
import os
import socket
import tempfile
from typing import Optional, Union
from urllib.request import urlopen
from urllib.error import HTTPError, URLError


class ConstantTemporaryFile:
    def __init__(self, constant_content, **kwargs):
        self.constant_content = constant_content
        self._file = None
        self._kwargs = dict(kwargs)
        self._kwargs['mode'] = 'w+b'
        self._kwargs['delete'] = False

    def __enter__(self) -> str:
        self._file = tempfile.NamedTemporaryFile(**self._kwargs)
        self._file.write(self.constant_content)
        self._file.close()
        return self._file.name

    def __exit__(self, type, value, traceback):
        if self._file and os.path.exists(self._file.name):
            os.remove(self._file.name)
        self._file = None


def int_to_bytes(n: int) -> bytes:
    number_of_bytes = int(math.ceil(n.bit_length() / 8))
    return n.to_bytes(number_of_bytes, byteorder='big')


def decode_hex(data: Optional[str]) -> Optional[bytes]:
    if data is None:
        return None
    if data.startswith('0x'):
        data = data[2:]
    return bytes.fromhex(data)


def decode_value(v: Union[str, int]) -> int:
    if isinstance(v, int):
        return v
    elif v.startswith('0x') or (frozenset(['a', 'b', 'c', 'd', 'e', 'f']) & frozenset(v)):
        # this is a hex string
        return int(v, 16)
    else:
        # assume it is a regular int
        return int(v)


def format_hex_address(addr: Optional[Union[int, str]], add_0x: bool = False) -> Optional[str]:
    if addr is None:
        return None
    if isinstance(addr, int):
        addr = "%x" % addr
    if addr.lower().startswith('0x'):
        addr = addr[2:]
    if len(addr) < 40:
        addr = "%s%s" % ('0' * (40 - len(addr)), addr)
    elif 40 < len(addr) < 64:
        # this is likely something like a transaction hash, so round up to 32 bytes:
        addr = "%s%s" % ('0' * (64 - len(addr)), addr)
    if add_0x:
        addr = "0x%s" % addr
    return addr


def webserver_is_up(url: str) -> bool:
    try:
        return urlopen(url).getcode()
    except HTTPError:
        # This means we connected
        return True
    except URLError:
        return False


def is_port_free(port: int) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    return sock.connect_ex(('127.0.0.1', port)) != 0


def find_open_port(starting_port: int = 1025) -> int:
    for port in range(starting_port, 65536):
        if is_port_free(port):
            return port
    return -1


def clear_directory(path: str):
    """
    Deletes the contents of a directory, but not the directory itself. 
    This is safe to use on symlinked directories.
    Symlinks will be deleted, but the files and directories they point to will not be deleted.
    If `path` itself is a symlink, the symlink will be deleted.
    """
    if os.path.islink(path):
        os.unlink(path)
        return

    for dirpath, dirnames, filenames in os.walk(path, topdown=False):
        for dirname in dirnames:
            subdir = os.path.join(dirpath, dirname)
            os.rmdir(subdir)
        for filename in filenames:
            os.remove(os.path.join(dirpath, filename))


def ynprompt(prompt: str) -> bool:
    while True:
        yn = input(prompt)
        yn = yn[0:1].lower()
        if yn == 'n' or yn == '':
            return False
        elif yn == 'y':
            return True
