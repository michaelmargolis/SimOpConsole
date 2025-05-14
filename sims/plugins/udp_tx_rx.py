"""
 udp_tx_rx.py
 
 threaded classes for sending and receiving UDP text messages
"""

import socket
import threading
import traceback
import signal

try:
    #  python 3.x
    from queue import Queue
except ImportError:
    #  python 2.7
    from Queue import Queue

import logging
log = logging.getLogger(__name__)

class UdpSend(object):
    def __init__(self):
        self.send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def send(self, data, addr):
        self.send_sock.sendto(data, addr)

class UdpReceive(object):

    def __init__(self, port):
        self.in_q = Queue()
        listen_address = ('', port)
        self.sender_addr = None # populated upon receiving messages
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) 
        self.sock.bind(listen_address)
        t = threading.Thread(target=self.listener_thread, args= (self.sock, self.in_q))
        t.daemon = True
        log.debug("UDP receiver listening on port %d", listen_address[1])
        self.isRunning = True
        t.start()

    def close(self):
        self.sock.shutdown(socket.SHUT_RDWR)
        self.sock.close()
    
    def available(self):
        return self.in_q.qsize()
 
    def get(self):  # returns address, msg
        if self.available():
            msg = self.in_q.get_nowait()
            self.sender_addr = msg[0]
            return msg
        else:
            return None

    def send(self, data, addr):
        self.sock.sendto(data.encode('utf-8'), addr) 

    def reply(self, data): # send to the address of the last received msg    
        if self.sender_addr:
            self.sock.sendto(data.encode('utf-8'), self.sender_addr)     

    def listener_thread(self, sock, in_q ):
        MAX_MSG_LEN = 256
        while self.isRunning:
            try:
                msg, addr = sock.recvfrom(MAX_MSG_LEN)
                #  print addr, msg
                msg = msg.decode('utf-8').rstrip()
                self.in_q.put((addr, msg))
            except Exception as e:
                pass
                # print("Udp listen error", e)


""" the following is for testing """

if __name__ == "__main__":
    import argparse
    import time
    
    def man():
        parser = argparse.ArgumentParser(description='UDP tx rx tester')
        parser.add_argument("-l", "--log",
                            dest="logLevel",
                            choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                            help="Set the logging level")
        parser.add_argument("-a", "--addr",
                            dest="address",
                            help="Set the target ip address")
                            
        parser.add_argument("-p", "--port",
                            dest="port",
                            help="Set the target socket port")
        
        parser.add_argument("-c", "--cmd",  action='store_true',
                            dest="panel_cmds",
                            help="do panel commands")    
        
        parser.add_argument("-e", "--evt",  action='store_true',
                            dest="panel_events",
                            help="do panel events")  
        return parser
 
    PANEL_PORT = 10024
       
    def panel_cmds(address = '127.0.0.1', port = PANEL_PORT ):
        print("Panel udp sender sending to port", port)
        udp = UdpReceive(port+1)
        while(1):
            msg = input("cmd msg: ")
            if msg == '':
                return         
            udp.send(msg, (address, port))
            time.sleep(.2)
            while udp.available():
                print('got', udp.get())
     
     
    # cmd;{"Parking_brake":1,"Landing_gear":1,"Flaps":0.1,"Throttle":0,"Mixture":1} 
     
         
    def panel_events(address = '127.0.0.1', port = PANEL_PORT ):
        print("Panel udp receiver listening on port", port)
        udp = UdpReceive(port)
        while(1): 
            while udp.available():
                got = udp.get()
                print("data=", got[1])
                print("addr=", got[0])
                udp.send('got'+got[1], got[0])


    args = man().parse_args()
    print(args)
    logging.basicConfig(format='%(asctime)s %(levelname)-8s %(message)s',
                    datefmt='%H:%M:%S')
    if args.logLevel:
        level = args.logLevel
    else:
        level = 'DEBUG'
    print(level, "logging level")
    log.setLevel(level)
    

    
    if args.port:
        port = int(args.port)
    else:
        port = PANEL_PORT 
        
    if args.address:
        address = args.address
    else:
        address = '127.0.0.1'

    if args.panel_events:
         panel_events(address, port) 
        
    panel_cmds(address, port) 
    


