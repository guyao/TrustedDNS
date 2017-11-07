import select
import logging
from collections import defaultdict
POLLNULL = 0x0000
POLLIN = 0x0001  # 00000000 00000001 any readable data available
POLLPRI = 0x0002  # 00000000 00000010 OOB/Urgent readable data
POLLOUT = 0x0004  # 00000000 00000100 file descriptor is writeable
POLLERR = 0x0008  # 00000000 00001000 some poll error occurred
POLLHUP = 0x0010  # 00000000 00010000 file descriptor was "hung up"
POLLNVAL = 0x0020  # 00000000 00100000 requested events "invalid"
POLLRDNORM = 0x0040  # 00000000 01000000 non-OOB/URG data available
POLLRDBAND = 0x0080  # 00000000 10000000 OOB/Urgent readable data
POLLWRBAND = 0x0100  # 00000001 00000000 OOB/Urgent data can be written
POLLEXTEND = 0x0200  # 00000010 00000000 file may have been extended
POLLATTRIB = 0x0400  # 00000100 00000000 file attributes may have changed
POLLNLINK = 0x0800  # 00001000 00000000 (un)link/rename may have happened
POLLWRITE = 0x1000  # 00010000 00000000 file's contents may have changed

#MODELS = ['epll', 'kqueue', 'select', 'poll']


class SelectLoop(object):
    """
    SelectLoop
    Methods:
        * __init__()
        * pool()
        * add_fd()
        * remove_fd()
        * modify_fd()
    """

    def __init__(self):
        # check models
        self._r_list = set()
        self._w_list = set()
        self._x_list = set()

    def poll(self, timeout):
        r, w, x = select.select(
            self._r_list, self._w_list, self._x_list, timeout)
        result = defaultdict(lambda: POLLNULL)
        for f_list in [(r, POLLIN), (w, POLLOUT), (x, POLLERR)]:
            for fd in f_list[0]:
                result[fd] = result[fd] | f_list[1]
        return result.items()

    def add_fd(self, fd, mode):
        if mode & POLLIN:
            self._r_list.add(fd)
        if mode & POLLOUT:
            self._w_list.add(fd)
        if mode & POLLERR:
            self._x_list.add(fd)

    def remove_fd(self, fd):
        if fd in self._r_list:
            self._r_list.remove(fd)
        if fd in self._w_list:
            self._w_list.remove(fd)
        if fd in self._x_list:
            self._x_list.remove(fd)

    def edit_fd(self, fd, mode):
        self.remove_fd(fd)
        self.add_fd(fd, mode)


class EventLoop(object):
    """
    EventLoop:
        Methods:
            * __init__()
            * run()

        Variables:
            * MODELDICT: modelname->modelclass
            * MODELS : modelnames
            * _fd_f: fd->f
            * _f_handler: f->handler
            * _handler_f: handler->f

            handler->fs: _handler_f[handler]
            f->fd: f.fileno()
            fd->f: _fd_f[fd]
            f->handler:nouse
    """
    MODELDICT = {'select': SelectLoop}
    # valid mod
    MODELS = ['select']

    def __init__(self):
        model = ''
        for mod in self.MODELS:
            try:
                if hasattr(select, mod):
                    self._poll_mod = self.MODELDICT[mod]()
                    model = mod
            except KeyError:
                raise Exception('invalid model name in MODELS')
        logging.debug('using EventLoop model: %s', model)
        self._handlers = []
        self._fd_f = {}
        self._fd_handler = {}
        self._handler_fd = defaultdict(list)

    def get_fd_f(self):
        return self._fd_f

    def poll(self, timeout=1):
        # handler->(f, fd, mode)
        events = self._poll_mod.poll(timeout)
        result = defaultdict(list)
        for fd, mode in events:
            result[self._fd_handler[fd]].append((self._fd_f[fd], fd, mode))
        return result

    def _add_f(self, f, mode):
        # add: _fd->f
        # mode
        # POLLIN -> rlist: wait until ready for reading
        # POLLOUT -> wlist: wait until ready for writing
        # POLLERR -> xlist: wait for a exception
        fd = f.fileno()
        self._fd_f[fd] = f
        self._poll_mod.add_fd(fd, mode)

    def _add_handler(self, handler):
        self._handlers.append(handler)

    def _remove_handler(self, handler):
        self._handlers.remove(handler)
        #del self._handler_f[handler]

    def add(self, f, mode):
        self._add_f(f, mode)

    def remove_handler(self, handler):
        self._remove_handler(handler)

    def bind_handler(self, f, handler):
        self._add_handler(handler)
        self._fd_handler[f.fileno()] = handler
        self._handler_fd[handler].append(f.fileno())

    def add_and_bind(self, f_info, handler):
        """
            f_info, a pair (file, mode)
        """
        f = f_info[0]
        mode = f_info[1]
        self._add_f(f, mode)
        self._add_handler(handler)
        # self._handler_f[handler].append(f)
        self._fd_handler[f.fileno()] = handler

    def remove(self, f):
        fd = f.fileno()
        self._poll_mod.remove_fd(fd)
        handler = None
        handler = self._fd_handler[fd]
        del self._fd_f[fd]
        del self._fd_handler[fd]
        self._handler_fd[handler].remove(f.fileno())

    def modify(self, f, mode):
        fd = f.fileno()
        self._poll_mod.edit_fd(fd, mode)

    def run(self, timeout=1):
        events = {}
        while self._handlers:
            events = self.poll(timeout)
            for handler in self._handlers:
                if len(self._handler_fd[handler]) > 0:
                    handler(events[handler])
                else:
                    self._remove_handler(handler)


def test():
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('', 9999))
    s.setblocking(False)
    s.listen(5)

    def h(events):
        print(events)
        for event in events:
            if event[0] is s:
                print(event)
                if event[2] & POLLIN:
                    try:
                        conn, addr = s.accept()
                        print('Get connection ', conn, addr)
                        el.bind_handler(conn, h)
                        el.add(conn, POLLIN)
                    except OSError:
                        continue
            else:
                print(event)
                try:
                    data = event[0].recv(4096)
                    if not data:
                        el.remove(event[0])
                        event[0].close()
                        continue
                    print(data)
                except IOError:
                    continue
        print('-' * 40)

    el = EventLoop()
    el.bind_handler(s, h)
    el.add(s, POLLIN)
    el.run()


def testUDP():
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('', 9999))

    def h(events):
        print(events)
        for f, fd, mode in events:
            pass

    el = EventLoop()
    el.bind_handler(s, h)
    el.add(s, POLLIN)
    el.run()


if __name__ == "__main__":
    testUDP()
