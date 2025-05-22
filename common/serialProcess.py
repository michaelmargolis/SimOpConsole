"""
serialProcess.py

A high level wrapper for pyserial functionality

"""



import threading
from time import time
import serial
from serial.tools import list_ports
from queue import Queue

import logging
log = logging.getLogger(__name__)
TERM_CHARS = bytearray([10]) # expect newline terminated msgs 
        
class SerialProcess(object):
    def __init__(self, result_queue=None):
        if result_queue is True:
            self.queue = Queue() # modified mar 2023 to create cue if arg is True
            # print("created queue")
        else:
            self.queue = result_queue 
        self.lock = threading.Lock()
        self.s = serial.Serial()
        self.is_started = False
        self.data = None   
        log.debug("TODO in SerialProcess, check default term char")

    @staticmethod
    def list_ports():
        return list_ports.comports()

    def get_ports(self):
        ports = []
        for port in self.list_ports():
            ports.append(port[0])
        return ports

    def is_port_available(self, port):
        for ports in self.list_ports():
            if ports[0] == port:
                return True
        return False

    def open_port(self, port, bd=115200, timeout=1):
        try:
            if not self.s.isOpen():
                self.s = serial.Serial(port, bd)
                self.s.timeout = timeout
                start = time()
                while time()-start < 1.1:
                    if self.s.isOpen():
                        self.is_started = True
                        t = threading.Thread(target=self.rx_thread)
                        t.daemon = True
                        t.start()
                        # print port, "opened"
                        return True
            else:
                log.warning("%s port already open\n", port)
        except Exception as e:
            log.error("Serial error: %s", e)
        return False

    def close_port(self):
        log.info("SerialProcess finishing...")
        self.is_started = False  # port will be closed when thread terminates

    def write(self, msg):
        if self.s.isOpen():
            self.s.write(msg)
        else:
            log.error("serial port not open")
            # todo put this in try block

    def read(self):
        if self.queue != None:
            return self.queue.get(False)  #dont block
        else:
            data = None
            with self.lock:
                data = self.data
            return data
        
    def available(self):
        if self.queue != None:
            return self.queue.qsize()
        elif self.data != None:
            return 1
        else:
            return 0

    def is_open(self):
        return self.s.isOpen()
       
    def rx_thread(self):
        while self.is_started == True:
            try:
                data = self.s.read_until().decode()           
                if data:
                    if self.queue != None:
                        self.queue.put(data)
                    else:                        
                        with self.lock: 
                            self.data = data
            except Exception as e:
                print(e)
                log.error("unable to read line from serial")
        self.s.close()
        log.info("SerialProcess finished")

'''
sp = SerialProcess()
ports = sp.list_ports()
for p in ports:
    print(str(p))
sp.open_port("COM10", 115200)
while True:
    msg = input('\nType msg to send')
    if len(msg) < 2:
        break
    sp.write(msg)
'''
