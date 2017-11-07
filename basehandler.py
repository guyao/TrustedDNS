"""
Usage:
    BaseServerHandler:
        * self.socket -> the socket for listening
        for default, it is a TCP socket with AF_INET(IPv4)
        to change the type of the socket, override it
        * user add_to_loop() to bind to a eventloop
        when the socket is ready, the handle() method called
        you have to override the handle() method

    BaseRequestHandler:
        self.request -> the request
"""
import socket
import logging
from eventloop import POLLNULL, POLLIN, POLLPRI, POLLOUT, POLLERR, \
    POLLHUP, POLLNVAL, POLLRDNORM, POLLRDBAND, \
    POLLWRBAND, POLLEXTEND, POLLATTRIB, POLLNLINK, POLLWRITE


class BaseServerHandler(object):
    """
    have to overridden handle() manully
    use:
        * initial
        * add_to_loop(event_loop)
    start when called event_loop.run()

    function:
        construction: __init__ ->   |server_bind(),server_active()
                                    |setup()

        call_back func: self.handle()

    """
    address_family = socket.AF_INET
    socket_type = socket.SOCK_STREAM
    allow_reuse_address = True
    reuqest_queue_size = 5

    def __init__(self, server_addr, RequestHandlerClass, bind_and_active=True):
        self.socket = socket.socket(self.address_family, self.socket_type)
        self.socket.setblocking(False)
        self.server_addr = server_addr
        self._loop = None
        self.RequestHandlerClass = RequestHandlerClass
        if bind_and_active:
            self.server_bind()
            self.server_active()
        self.setup()

    def setup(self):
        """
        may be overridden
        add extra members
        called in constructor
        """
        pass

    def add_to_loop(self, eventloop):
        self._bind_eventloop(eventloop)
        self._register_to_loop()

    def _register_to_loop(self):
        self._loop.add(self.socket, POLLIN)
        self._loop.bind_handler(self.socket, self.handle)

    def handle(self, events):
        pass

    def _bind_eventloop(self, eventloop):
        self._loop = eventloop

    def server_bind(self):
        if self.allow_reuse_address:
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(self.server_addr)
        self.server_addr = self.socket.getsockname()

    def server_active(self):
        # for TCP self.socket.listen(self.reuqest_queue_size)
        # for UDP no need to listen
        pass

    def finish(self):
        pass

    def verify_request(self, request, addr):
        """
        May be overridden
        """
        return True

    def handle_error(self, request, addr):
        """
        May be overridden
        """
        pass

    def shutdown_request(self, request):
        """
        May be overridden
        """
        pass


class BaseRequestHandler(object):

    def __init__(self, request, client_addr):
        self.request = request
        self.client_addr = client_addr
        try:
            self.handle()
        finally:
            self.finish()

    def handle(self):
        pass

    def finish(self):
        pass


def async_process(func):
    def w(*args, **kw):
        body = args[0]
        body.verify_handle()
        if not body.err:
            f = func(*args, **kw)
        else:
            return
        body.finish()
        return f
    return w


class BaseAsyncRequestHandler(object):
    """
    BaseAsyncRequestHandler
        handler for request that no need to reply immediately
        reply when handle() called

        handle(self,mode) have a parameter "mode" to handle different circumstance
    """

    timeout = None

    def __init__(self, request, client_addr):
        self.request = request
        self.connection = self.request
        self.client_addr = client_addr
        self.remote_server = None
        self.err = False
        self._setup()
        self.setup()

    def _setup(self):
        if self.timeout is not None:
            self.connection.settimeout(self.timeout)

    def setup(self):
        """
        may be overridden
        to add extra members
        called manully
        """
        pass

    def handle(self, mode):
        pass

    def verify_handle(self):
        return True

    def finish(self):
        pass
