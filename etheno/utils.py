import socket
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
