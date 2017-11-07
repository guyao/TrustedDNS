import socket
import logging
from eventloop import EventLoop
from eventloop import POLLNULL, POLLIN, POLLPRI, POLLOUT, POLLERR, \
    POLLHUP, POLLNVAL, POLLRDNORM, POLLRDBAND, \
    POLLWRBAND, POLLEXTEND, POLLATTRIB, POLLNLINK, POLLWRITE
from basehandler import BaseServerHandler, BaseAsyncRequestHandler
from basehandler import async_process
import time
import struct
try:
    import queue
except NameError:
    import Queue

BUFSIZE = 32 * 1024

class TCPServerHandler(BaseServerHandler):

    address_family = socket.AF_INET
    socket_type = socket.SOCK_STREAM
    allow_reuse_address = True
    reuqest_queue_size = 5

    def __init__(self, server_addr, dns_server_addr, RequestHandlerClass, bind_and_active=True):
        self.socket = socket.socket(self.address_family, self.socket_type)
        self.socket.setblocking(False)
        self.server_addr = server_addr
        self.dns_server_addr = dns_server_addr
        self._loop = None
        self.RequestHandlerClass = RequestHandlerClass
        if bind_and_active:
            self.server_bind()
            self.server_active()
        self.setup()

    def process_request(self, request, addr):
        handler = self.RequestHandlerClass(request, addr)
        handler.bind_to_loop(self._loop)
        handler.add_remote_server(self.server_sock, self.server_addr)
        handler.bind_hash_dict(self.hash_dict)
        self._loop.bind_handler(request, handler.handle)
        self._loop.add(request, POLLIN | POLLOUT)

    def connectRemote(self):
        try:
            server_addr = (self.dns_server_addr, 53)
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setblocking(False)
            self.server_addr = server_addr
            self.server_sock = s
            logging.debug('Success to connect dns server')
        except socket.gaierror:
            logging.error(
                'Can not connect to remote server : address-realted error')
        except socket.error:
            logging.error('Can not connect to remote server')
        finally:
            pass

    def retry_connect(self):
        self.connectRemote()

    def server_active(self):
        self.socket.listen(self.reuqest_queue_size)
        logging.debug('Listening')

    def handle(self, events):
        # (f, fd, mode)
        for f, fd, mode in events:
            if f:
                pass
                # logging

            if f is self.socket:
                if mode & POLLIN:
                    self._read_local()

            elif f is self.server_sock:
                if mode & POLLIN:
                    pass
                if mode & POLLOUT:
                    pass
            else:
                pass

    def _read_local(self):
        """
         get_request
        """
        try:
            request, addr = self.get_request()
            request.setblocking(False)
            logging.debug('Get Connection: %s ', addr)
        except OSError:
            return
        if self.verify_request(request, addr):
            try:
                self.process_request(request, addr)
            except:
                self.handle_error(request, addr)
                self.shutdown_request(request)

    def get_request(self):
        return self.socket.accept()

    def setup(self):
        # data_hash -> handler
        self.hash_dict = {}
        self.connectRemote()


class TCPRequestHandler(BaseAsyncRequestHandler):
    """
    request, client_addr, server
    """
    BUFSIZE = 4096

    @async_process
    def handle(self, events):
        #logging.debug('Begin Handler %s. event: %s', self.client_addr, events)
        for f, fd, mode in events:
            if mode & POLLIN:
                self.handle_read()
            if mode & POLLOUT:
                self.handle_write()

    def bind_to_loop(self, loop):
        self._loop = loop

    def finish(self):
        pass

    def bind_hash_dict(self, hash_dict):
        self.hash_dict = hash_dict

    def setup(self):
        self.query = []
        self.response = []

    def query_dns(self):
        for d in self.query:
            self._query_data(d)

    def _query_data(self, data):
        try:
            self.remote_server.sendto(data, self.server_addr)
        except socket.error:
            logging.debug("Error: can not send query")
            return
        print('dns query ', data)
        self.query.remove(data)
        try:
            response, addr = self.remote_server.recvfrom(self.BUFSIZE)
        except socket.error:
            print('not ok yet')
            return
        print('dns response', response)
        self.response.append(response)

    def _response(self):
        try:
            response, addr = self.remote_server.recvfrom(self.BUFSIZE)
        except socket.error:
            return
        print('dns response', response)
        self.response.append(response)

    def handle_read(self):
        data = self.request.recv(self.BUFSIZE)
        if not data:
            self.close()
            return
        print('r')
        print('Get query', data)
        self.query.append(data)
        self._loop.add(self.request, POLLOUT | POLLIN)
        self.query_dns()

    def handle_write(self):
        # handle data
        if self.query:
            self.query_dns()
        if not self.response:
            return
        print('w')
        for response in self.response:
            try:
                self.request.send(response)
            except socket.error:
                logging.error('Error: fail to send back response')
            print('send back rsponse', response)
            self.response.remove(response)
            self._loop.add(self.request, POLLIN | POLLOUT)

    def process_read_data(self):
        pass

    def process_write_data(self):
        pass

    def close(self):
        """
         release all resource
        """
        self._loop.remove(self.request)
        self.request.close()

    def add_remote_server(self, remote_server, server_addr):
        self.remote_server = remote_server
        self.server_addr = server_addr

    def verify_handle(self):
        try:
            self.remote_server
        except NameError:
            logging.error('Remote server is not set')
            self.err = True


class UDPServerHandler(BaseServerHandler):
    address_family = socket.AF_INET
    socket_type = socket.SOCK_DGRAM
    allow_reuse_address = True
    reuqest_queue_size = 5
    max_packet_size = 4096

    def __init__(self, server_addr, remote_server_addr, bind_and_active=True):
        self.socket = socket.socket(self.address_family, self.socket_type)
        self.socket.setblocking(False)
        self.server_addr = server_addr
        self.remote_server_addr = remote_server_addr
        self.server_sock = None
        self._loop = None
        if bind_and_active:
            self.server_bind()
            self.server_active()
        self.setup()

    def setup(self):
        self.queryQueue = queue.Queue()
        self.id_to_addr = {}
        self.responseQueue = queue.Queue()
        self.connectRemote()

    def _register_to_loop(self):
        self._loop.bind_handler(self.socket, self.handle)
        self._loop.bind_handler(self.server_sock, self.handle)
        self._loop.add(self.socket, POLLIN | POLLOUT)
        self._loop.add(self.server_sock, POLLIN | POLLOUT)

    def connectRemote(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setblocking(False)
            self.server_sock = s
            s.connect(self.remote_server_addr)
        except socket.gaierror:
            logging.error(
                'Can not connect to remote server : address-realted error')

        except socket.error:
            logging.error('Can not connect to remote server')

    def retry_connect(self):
        time.sleep(1)
        self.connectRemote()

    def server_active(self):
        pass

    def verify_remote_data(self, data):
        # TODO
        # check hmac
        return True

    def _process_get_local(self, request, addr):
        if not request:
            return
        querydata, sock = request
        if not querydata:
            return
        print('query ', querydata)
        self.register_query(querydata, addr)

    def _process_put_local(self, data, addr):
        if not data:
            return
        print('back query', data)
        self.put_local(data, addr)
        self.unregister_query(data)

    def _process_get_remote(self, responseData):
        # verify
        if not responseData:
            return
        if self.verify_remote_data(responseData):
            # decode
            responseData = self.decode(responseData)
            #put in responseQueue
            self.responseQueue.put(responseData)
            print('get remote ', responseData)

    def _process_put_remote(self, requestdata):
        # encode
        if not requestdata:
            return
        data = self.encode(requestdata)
        print('put remote', requestdata)
        # sent to remote
        self.put_remote(data)

    def _verify_get_local(self, request, addr):
        return True

    def _verify_get_remote(self, request, addr):
        return True

    def register_query(self, querydata, addr):
        query_id = struct.unpack('!H', querydata[0:2])
        self.queryQueue.put(querydata)
        self.id_to_addr[query_id] = addr

    def unregister_query(self, responseData):
        response_id = struct.unpack('!H', responseData[0:2])
        try:
            del self.id_to_addr[response_id]
        except KeyError:
            return

    def get_client_addr(self, responseData):
        response_id = struct.unpack('!H', responseData[0:2])
        try:
            addr = self.id_to_addr[response_id]
        except KeyError:
            return
        return addr

    def handle(self, events):
        for f, fd, mode in events:
            if f is self.socket:
                if mode & POLLIN:
                    self._read_local()

                if mode & POLLOUT:
                    self._write_local()

            if f is self.server_sock:
                if mode & POLLIN:
                    self._read_remote()

                if mode & POLLOUT:
                    self._write_remote()

    def _read_local(self):
        # put queryQueue
        try:
            request = self.get_local()
            if not request:
                return
            request, addr = request
        except OSError:
            return
        if self._verify_get_local(request, addr):
            try:
                self._process_get_local(request, addr)
            except:
                self.handle_error(request, addr)
                self.shutdown_request(request)

    def _write_local(self):
        # pop responseQueue
        try:
            responseData = self.responseQueue.get(block=False)
        except queue.Empty:
            return
        if not responseData:
            return
        addr = self.get_client_addr(responseData)
        if not addr:
            return
        self._process_put_local(responseData, addr)

    def _read_remote(self):
        try:
            responseData = self.get_remote()
        except socket.error:
            logging.error('Error: can not get remote')
            return
        if not responseData:
            return
        self._process_get_remote(responseData)

    def _write_remote(self):
        # pop queryQueue
        try:
            data = self.queryQueue.get(block=False)
        except queue.Empty:
            return
        if not data:
            return
        self._process_put_remote(data)

    def get_local(self):
        try:
            data, client_addr = self.socket.recvfrom(self.max_packet_size)
        except socket.error:
            return
        return (data, self.socket), client_addr

    def put_local(self, data, addr):
        length = len(data)
        try:
            sent_length = self.socket.sendto(data, addr)
        except socket.error:
            logging.error("Fail to send back request, retry")

        if sent_length < length:
            self.retry(self.put_local, data[sent_length:], addr)

    def get_remote(self):
        try:
            data = self.server_sock.recv(self.max_packet_size)
        except socket.error:
            return
        return data

    def put_remote(self, data):
        try:
            self.server_sock.send(data)
        except socket.error:
            logging.error("Errors: can not send to remote")

    def retry(self, func, *args, **kw):
        func(*args, **kw)

    def encode(self, data):
        return data

    def decode(self, data):
        return data


def testTCPhandler():
    eventloop = EventLoop()
    server_addr = ('', 9999)
    tcp_server = TCPServerHandler(server_addr, TCPRequestHandler)
    tcp_server.add_to_loop(eventloop)
    eventloop.run()


def testUDPhandler():
    eventloop = EventLoop()
    udp_server = UDPServerHandler(('', 8989))
    udp_server.add_to_loop(eventloop)
    eventloop.run()


def testALL():
    eventloop = EventLoop()
    tcp_server = TCPServerHandler(('', 9999), TCPRequestHandler)
    tcp_server.add_to_loop(eventloop)

    udp_server = UDPServerHandler(('', 8888))
    udp_server.add_to_loop(eventloop)
    eventloop.run()


if __name__ == "__main__":
    logging.basicConfig(
        level='DEBUG', format='%(asctime)s - %(levelname)s - pid:%(process)d - %(message)s')
    testTCPhandler()
