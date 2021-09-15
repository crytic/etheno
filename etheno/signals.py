import signal


def add_handler(signal_type, handler):
    current_handler = signal.getsignal(signal_type)
    if current_handler == signal.SIG_IGN or current_handler == signal.SIG_DFL:
        current_handler = None

    def new_handler(sig_type, frame):
        if current_handler:
            current_handler(sig_type, frame)
        handler(sig_type, frame)
    signal.signal(signal_type, new_handler)


def add_sigint_handler(handler):
    add_handler(signal.SIGINT, handler)
