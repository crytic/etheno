#!/usr/bin/env python2

import threading
from threading import Condition

def is_main_thread():
    return isinstance(threading.current_thread(), threading._MainThread)

class MainThreadController(object):
    def __init__(self):
        if not is_main_thread():
            raise Exception("A controller can only be created from the main thread")
        self._main_wake_up = Condition()
        self._main_wake_up.acquire()
        self._obj = None
        self._caller_wake_up = None
        self._args = None
        self._kwargs = None
        self._return = None
        self._quit = False
    def invoke(self, obj, *args, **kwargs):
        if is_main_thread():
            return obj.__call__(*args, **kwargs)
        released = False
        self._main_wake_up.acquire()
        try:
            self._caller_wake_up = Condition()
            with self._caller_wake_up:
                self._obj = obj
                self._args = args
                self._kwargs = kwargs
                # tell the main thread to wake up
                self._main_wake_up.notify_all()
                self._main_wake_up.release()
                released = True
                self._caller_wake_up.wait()
                # tell the main thread that we received the result:
                self._caller_wake_up.notify_all()
                ret = self._return
                return ret
        finally:
            self._obj = None
            self._args = None
            self._kwargs = None
            self._caller_wake_up = None
            self._return = None
            if not released:
                self._main_wake_up.release()
    def run(self):
        if not is_main_thread():
            raise Exception("run can only be called from the main thread!")
        import signal
        def signal_handler(signal, frame):
            self._quit = True
        signal.signal(signal.SIGINT, signal_handler)
        while True:
            self._main_wake_up.wait(1.0)
            if self._quit:
                return
            elif self._caller_wake_up is None:
                # we timed out
                continue
            with self._caller_wake_up:
                self._return = self._obj.__call__(*self._args, **self._kwargs)
                self._caller_wake_up.notify_all()
                # wait for the calling thread to confirm it received the result
                self._caller_wake_up.wait()

class MainThreadWrapper(object):
    def __init__(self, mainobj, controller):
        self._main = mainobj
        self._controller = controller
    def __call__(self, *args, **kwargs):
        ret = self._controller.invoke(self._main, *args, **kwargs)
        if id(self._main) == id(ret):
            return MainThreadWrapper(ret, self._controller)
        else:
            return ret
    def __getattribute__(self, name):
        if name == '_main' or name == '_controller':
            return object.__getattribute__(self, name)
        else:
            return MainThreadWrapper(getattr(self._main, name), self._controller)

if __name__ == '__main__':
    class MainThreadOnlyClass(object):
        def do_stuff(self):
            if not is_main_thread():
                raise Exception("ERROR!")
            return 1337

    main_thread_only = MainThreadOnlyClass()

    controller = MainThreadController()

    def dostuff(mtoc):
        print(mtoc.do_stuff())
    
    from threading import Thread
    thread = Thread(target = dostuff, args = (MainThreadWrapper(main_thread_only, controller),))
    thread.start()
    controller.run()
    thread.join()
