"""
festo_itf.py

call send_pressures with list of six int muscle pressures
    send_pressures([100,200,300,400,500,600])
optionally set a second parm True to read and return actual pressures following the send
    actuals = send_pressures([100,200,300,400,500,600], True)

For info on festo interface library, see: https://github.com/kmpm/fstlib
"""

import sys
import socket
import time
import traceback
import threading
from builtins import input
from output.fstlib import easyip
import logging

log = logging.getLogger(__name__)

BUFSIZE = 1024

class Festo(object):
    # Set the socket parameters for festo requests    
    FST_port = easyip.EASYIP_PORT

    def __init__(self, FST_ip='192.168.0.10'):
        # create festo client
        self.FSTs = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.FST_addr = (FST_ip, self.FST_port)
        self.FSTs.bind(('0.0.0.0', 0))
        self.FSTs.settimeout(1)  # timout after 1 second if no response
        log.info("Using Festo controller socket %s:%d ",  FST_ip, self.FST_port)

        self.wait= False # set true for send confirmation
        self.poll_pressures = False
        self.netlink_ok = False # True if festo responds without error
        self.out_pressures = [0,0,0,0,0,0]
        self.actual_pressures = [0,0,0,0,0,0]    
        
        self.lock = threading.Lock()
        t = threading.Thread(target=self.query_thread, args=(self.lock,))
        t.daemon = True
        t.start()

    def __del__(self): 
        self.FSTs.close()
 
    def query_thread(self, lock):
        while True:
            time.sleep(.02)
            if self.poll_pressures:
                try:
                    p = self._get_festo_pressure()
                    if p != None:
                        with lock:
                           self.actual_pressures = p
                except:
                    pass  # ignore errors, use most recent value
               
               
    def get_pressure(self):
        self.lock.acquire()
        p = self.actual_pressures
        self.lock.release()
        return p

    def send_pressures(self, muscle_pressures):
        # sends muscle pressures to Festo
        try:
            # print "sending pressures:", muscle_pressures
            packet = easyip.Factory.send_flagword(0, muscle_pressures)
            self._output_festo_packet(packet, self.wait)
            self.out_pressures = muscle_pressures
        except Exception as e: 
            log.error("error sending to Festo: %s, %s", e, traceback.format_exc())
        return None
        
    def set_wait_ack(self, state):
        self.wait = state

        # if True, send method will try to get and return actual pressure
        log.debug("festo wait for ack is set to %s", self.wait)

    def enable_poll_pressure(self, state):
        self.poll_pressures = state
        log.info("festo poll for actual pressure is set to %s", state)

    def _output_festo_packet(self, packet, wait_ack):
        data = packet.pack()
        # print "sending to", self.FST_addr, packet
        resp = None
        self.FSTs.sendto(data, self.FST_addr)
        if wait_ack:
            #  print "in sendpacket,waiting for response..."
            t = time.time()
            try:
                data, srvaddr = self.FSTs.recvfrom(BUFSIZE)
                dur = time.time()-t
                self.msg_latency = int(dur * 1000)
                resp = easyip.Packet(data)
                #  print "in sendpacket, response from Festo", resp, srvaddr
                if packet.response_errors(resp) is not None:
                    print(str(packet), str(resp))
                    log.error("festo output error: %s",  str(packet.response_errors(resp)))
                    self.netlink_ok = False
                else:
                    self.netlink_ok = True
            except:
                self.netlink_ok = False
        return resp

    def _get_festo_pressure(self):
        # first arg is the number of requests you'r making. Leave it as 1 always
        # Second arg is number of words you are requesting (probably 6, or 16)
        # third arg is the offset.  (pressure values are expected from offset 10)
        # words 0-5 are what you sent it.
        # words 6-9 are not used
        # words 10-15 are the current values of the presures
        # packet = easyip.Factory.req_flagword(1, nbr registers, register index)
        # print "attempting to get pressure"
        try:
            # print "dummy data"
            packet = easyip.Factory.req_flagword(1, 6, 10)
            resp = self._output_festo_packet(packet, True)
            # print resp
            values = resp.decode_payload(easyip.Packet.DIRECTION_REQ)
            print("in _get_festo_pressure", list(values))
            return list(values)
        except socket.timeout:
            log.warning("timeout waiting for Pressures from Festo")
        return [0,0,0,0,0,0]

        
    def process_test_message(self, msg_str):
        # only used for testing
        fields = msg_str.split(',')
        if len(fields) > 0 and len(fields) <= 6:  # one to six comma separated values
            last_given_field = len(fields)-1
            while len(fields) < 6: # if less than 6 values, fill list with missing values using the last given pressure
                fields.append(fields[last_given_field]) 
            try:
                pressures = [ max(min(int(i),6000),0) for i in fields] # convert the pressure strings to ints clamped at max pressure
                log.debug("attempting to send %s", pressures)
                actuals = self.send_pressures(pressures)
                # for now actual pressures are ignored
            except Exception as e: 
                log.error("invalid festo input err: %s", e)

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)-8s %(message)s',
                    datefmt='%H:%M:%S')
    festo = Festo('192.168.1.16')
    print("Festo address set to 192.168.1.16")
    festo.set_wait_ack(True)
    while True:
        try:
            msg = eval(input("enter one to six comma separated millibar values (0-6000): "))
            if msg:
                festo.process_test_message(msg)
            else:
                exit()
        except: 
            exit()
