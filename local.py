from eventloop import EventLoop
from handler import UDPServerHandler
from mod_config import get_config
import logging
DNSPORT = 53

if __name__ == "__main__":
    logging.basicConfig(level=getattr(logging, get_config('basic', 'log-level')),
                        format='%(asctime)s - %(levelname)s - pid:%(process)d - %(message)s')
    remote_addr = (get_config('local', 'server'),
                   int(get_config('local', 'port')))
    local_addr = ('', DNSPORT)
    el = EventLoop()
    udp_server = UDPServerHandler(local_addr, remote_server_addr=remote_addr)
    udp_server.add_to_loop(el)
    el.run()
