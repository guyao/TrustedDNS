from eventloop import EventLoop
from handler import TCPServerHandler
from handler import TCPRequestHandler
from mod_config import get_config

if __name__ == "__main__":
    server_port = int(get_config('server', 'port'))
    dns_server_addr = get_config('server', 'dnsserver')
    el = EventLoop()
    tcp_server = TCPServerHandler(
        ('', server_port), dns_server_addr, TCPRequestHandler)
    tcp_server.add_to_loop(el)
    el.run()
