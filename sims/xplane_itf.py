# xplane_itf 

import os, sys
import socket
import struct
import traceback
import copy
import time
from enum import Enum
import logging

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from common.udp_tx_rx import UdpReceive


"""
The coordinate frame follows ROS conventions, positive values: X is forward, Y is left, Z is up,
roll is right side down, pitch is nose down, yaw is CCW; all from perspective of person on platform.
Telemetry msg: Surge (g), Sway (g), Heave (g), Roll rate (rad/s), Pitch rate (rad/s), Yaw rate (rad/s), Roll angle (rad), Pitch angle (rad)
"""    

TELEMETRY_EVT_PORT = 10022 # xplane plugin sends events to this port  
TELEMETRY_CMD_PORT = 10023 # send commands for xplane plugin to this port

# XPLANE_CMD_ADDRESS = (XPLANE_IP_ADDR, TELEMETRY_CMD_PORT)
#XPLANE_UDP_ADDRESS = (XPLANE_IP_ADDR, XPLANE_UDP_PORT)

MCAST_GRP = '239.255.1.1'  # Standard multicast group
MCAST_PORT = 49707  # (MCAST_PORT was 49000 for XPlane10)

log = logging.getLogger(__name__)

# Define states
class State(Enum):
    INITIALIZED = 'Initialized'
    BEACON_RECEIVED = 'Beacon Received'
    RECEIVING_DATAREFS = 'Receiving Datarefs'
    DATAREFS_LOST = 'Datarefs Lost'
    

class Telemetry():
    def __init__(self, norm_factors, sleep_func, report_state_cb):
        self.sleep_func = sleep_func
        self.report_state_cb = report_state_cb
        self.xplane_udp = UdpReceive(TELEMETRY_EVT_PORT) 
        self.norm_factors = norm_factors
        # setup xplane beacon multicast receiver
        MCAST_GRP = '239.255.1.1'  # Standard multicast group
        MCAST_PORT = 49707  # (MCAST_PORT was 49000 for XPlane10)
        self.beacon_receiver = UdpReceive(MCAST_PORT, None, MCAST_GRP)
        self.BEACON_TIMEOUT = 2 # report beacon lost if no msg for 2 seconds
        self.state = State.INITIALIZED
        self.last_beacon_time = None
        self.xplane_ip = None
        self.xplane_addr = None
        
        # self.init_plot() # only for dev
        
    def service(self,  washout_callback):
        if self.state == State.INITIALIZED:
            self.handle_initialized()
        elif self.state == State.BEACON_RECEIVED:
            self.handle_beacon_received()
        elif self.state == State.RECEIVING_DATAREFS:
            return self.handle_receiving_datarefs( washout_callback)
        elif self.state == State.DATAREFS_LOST:
            self.handle_datarefs_lost()
        return (0,0,0,0,0,0)   
 
    def handle_initialized(self):
        self.report_state_cb("Initialized - Waiting for beacon...")
        
        beacon = self.receive_beacon_message()
        if beacon:
            self.xplane_ip = beacon['ip']
            self.xplane_addr = (self.xplane_ip, beacon['port'])
            print("X-Plane command address: {}".format(self.xplane_addr))
            self.state = State.BEACON_RECEIVED

    def handle_beacon_received(self):
        self.report_state_cb(f"Found X-Plane, waiting for data...")
        self.xplane_udp.send('InitComs', (self.xplane_ip, TELEMETRY_CMD_PORT)) 
        self.sleep_func(.5)
        if self.xplane_udp.available() > 2 :
            self.report_state_cb("Receiving telemetry events")
            log.info("Receiving telemetry events")
            self.state = State.RECEIVING_DATAREFS       

    def handle_receiving_datarefs(self,  washout_callback):
       # print("State: Receiving Datarefs")
        try:   
            msg = None
            xyzrpy = [0, 0, 0, 0, 0, 0]
            while self.xplane_udp.available() > 0:
                msg = self.xplane_udp.get()
            if msg != None:
                data = msg[1].split(',')
                if len(data) > 8 and data[0] == 'xplane_telemetry':
                    telemetry = [float(ele) for ele in data[1:9]]  
                    # print(','.join(str(t) for t in telemetry))                   
                    xyzrpy[0] = telemetry[0] * self.norm_factors[0] # x accel
                    xyzrpy[1] = telemetry[1] * self.norm_factors[1] # Y accel                     
                    xyzrpy[2] = telemetry[2] * self.norm_factors[2] # Z accel 
                    xyzrpy[3] = telemetry[6] * self.norm_factors[3] # roll angle
                    xyzrpy[4] = telemetry[7] * self.norm_factors[4] # pitch ange                     
                    xyzrpy[5] = telemetry[5] * self.norm_factors[5] # yaw rate 

                    if washout_callback:
                        rates = copy.copy(xyzrpy) # this assumes roll and pitch washout is disabled
                        washout =  washout_callback(rates)                     
                        #### self.plot(xyzrpy, washout)
                        return washout
            else:
                self.state = State.DATAREFS_LOST                
            return xyzrpy
        except Exception as e:
            print("in xplane read:", str(e))
            print(traceback.format_exc())
            return (0,0,0,0,0,0)
       

    def handle_datarefs_lost(self):
        self.report_state_cb("Data connection Lost - Attempting to reconnect...")
        self.beacon_receiver.clear() # remove queued msgs and wait for a new on
        self.last_beacon_time = time.time()
        self.state = State.INITIALIZED


    def receive_beacon_message(self):
        # truncated version just check prolog and return ip address if valid
        """
        if self.beacon_receiver.available():
            addr, message = self.beacon_receiver.get()
            if message.startswith(b'BECN\0'):
               beacon = {"ip": addr}
               return beacon 
        return None       
        """
        """
        Listens for a beacon message from X-Plane and returns the parsed information.
        Returns:
            dict: Contains 'ip', 'port', 'hostname', and other relevant details if a beacon is received, else None.
        """
        if self.beacon_receiver.available():
            addr, message = self.beacon_receiver.get()
            if message.startswith(b'BECN\0'):
                try:
                    # Define the format string for struct unpacking
                    format_str = '<BBiiI H 14s'
                    unpacked_data = struct.unpack(format_str, message[5:])
                    
                    beacon_info = {
                        'beacon_major_version': unpacked_data[0],
                        'beacon_minor_version': unpacked_data[1],
                        'application_host_id': unpacked_data[2],
                        'version_number': unpacked_data[3],
                        'role': unpacked_data[4],
                        'port': unpacked_data[5],
                        #'hostname': unpacked_data[6].decode('utf-8').strip('\x00')
                    }
                    
                    # Extract IP address from the sender's address
                    beacon_info['ip'] = addr[0]
                    
                    return beacon_info
                except struct.error as e:
                    log.error(f"Failed to unpack beacon message: {e}")
            else:
                log.warning("Received message with incorrect prologue.")
        return None

    def get_connection_state(self):
        """
        Returns the connection state of the application.

        Returns:
            connection_status (str): 'ok', 'warning', or 'nogo' based on the connection state.
            data_status (str): 'ok' if receiving datarefs, else 'nogo'.
            state_description (str): A terse description of the current state.
        """
        current_time = time.time()

        # Determine connection status
        if self.state == State.RECEIVING_DATAREFS:
            connection_status = "ok"
        elif self.state == State.INITIALIZED:
            connection_status = "nogo"
        elif self.state == State.DATAREFS_LOST:
            if self.last_beacon_time and (current_time - self.last_beacon_time > self.BEACON_TIMEOUT):
                connection_status = "nogo"
            else:
                connection_status = "warning"
        else:
            connection_status = "warning"

        # Determine data status
        if self.state == State.RECEIVING_DATAREFS:
            data_status = "ok"
        else:
            data_status = "nogo"

        # State description
        state_description = self.state

        return connection_status, data_status, state_description

    def close(self):
        self.xplane_udp.close()
        self.beacon_receiver.close()
        
    def run(self):
        if self.state == State.RECEIVING_DATAREFS:
            self.xplane_udp.send('Run', (self.xplane_ip, TELEMETRY_CMD_PORT))
        else:
            print("X-Plane is not connected")
        
    def pause(self):
        if self.state == State.RECEIVING_DATAREFS:
            self.xplane_udp.send('Pause', (self.xplane_ip, TELEMETRY_CMD_PORT))
        else:    
            print("X-Plane is not connected")    
    
    def reset(self):
        if self.state == State.RECEIVING_DATAREFS:
            #self.send_CMND('sim/replay/rep_end') # only needed because of bug in replay
            #self.send_CMND('sim/replay/rep_begin')
            self.xplane_udp.send('Reset', (self.xplane_ip, TELEMETRY_CMD_PORT)) 
        else:
            print("X-Plane is not connected")                 
        
    def replay(self, filename):
        self.send_SIMO(3, filename)
        """
        msg = 'Replay,{}'.format(filename)
        print("sending", msg, filename)
        self.xplane_udp.send(msg, (self.xplane_ip, TELEMETRY_CMD_PORT))   
        """
        """
        cmd = 3  # 0=Save sit, 1=Load sit, 2=Save Movie, 3=Load Movie
        path = filename.encode('utf-8')  # Relative path from xplane install dir, e.g., 'Output/my_replay.rep'
        #  little-endian SIMO (4 chars)  pad-byte int (4 byte cmd)  150 chars path  2 pad bytes        
        msg = struct.pack('<4sxi150s2x', b'SIMO', cmd, path)
        self.beacon_sock.sendto(msg, self.xplane_addr)
        print("sent", filename, msg)
        """        

    def situation(self, filename): 
        self.send_SIMO(1, filename)
        """
        msg = 'Situation,{}'.format(filename)
        self.xplane_udp.send(msg, (self.xplane_ip, TELEMETRY_CMD_PORT))  
        return
        """
        """
        cmd = 1  # 0=Save sit, 1=Load sit, 2=Save Movie, 3=Load Movie
        path = filename.encode('utf-8')  # Relative path from xplane install dir, e.g., 'Output/situations/my_situation.sit'
        #  little-endian SIMO (4 chars)  pad-byte int (4 byte cmd)  150 chars path  2 pad bytes        
        msg = struct.pack('<4sxi150s2x', b'SIMO', cmd, path)
        # self.beacon_sock.sendto(msg, XPLANE_UDP_ADDRESS)
        self.beacon_sock.sendto(msg, self.xplane_addr)
        print("sent",filename,  msg)    
        """

        """ 
        dref = 'sim/operation/load_situation_1' 
        msg = struct.pack('<4sx500s', b'CMND',dref.encode('utf-8'))               
        self.beacon_sock.sendto(msg, (beacon['ip'], beacon['port']))
        input("press key when ready")
     
        cmd = 3  # 0=Save sit, 1=Load sit, 2=Save Movie, 3=Load Movie
        path = "Output/replays/CessnaSkyhawkReplay.rep".encode('utf-8')  # Relative path, e.g., 'Output/my_movie'
        # path = "Output/situations/Cessna Skyhawk Replay.sit".encode('utf-8')  # Relative path, e.g., 'Output/my_movie'
        #  little-endian SIMO (4 chars)  pad-byte int (4 byte cmd)  150 chars path  2 pad bytes
        msg = struct.pack('<4sxi150s2x', b'SIMO', cmd, path)
        # self.beacon_sock.sendto(msg, XPLANE_UDP_ADDRESS)
        self.beacon_sock.sendto(msg, (beacon['ip'], beacon['port']))
        print("sent", msg)    
        """ 
    def send_SIMO(self, command, filename):
        # commands: 0=Save sit, 1=Load sit, 2=Save Movie, 3=Load Movie
        msg = struct.pack('<4sxi150s2x', b'SIMO', command, filename.encode('utf-8'))
        self.beacon_sock.sendto(msg, self.xplane_addr)
        print("sent", filename,  msg)   
   
    def send_CMND(self, command_str):
        msg = 'CMND\x00' + command_str
        self.beacon_sock.sendto(msg.encode('utf-8'), self.xplane_addr)
        
    
    # following only for washout dev 
    def init_plot(self):
        from . washout import motionCueing
        from common.plot_itf import PlotItf
        nbr_plots = 6
        traces_per_plot = 2
        titles = ('x (surge)', 'y (sway)', 'z (heave)', 'roll', 'pitch', 'yaw')
        legends = ('from xplane', 'washed')
        main_title = "Translations and Rotation washouts from XPlane" 
        self.plotter = PlotItf(main_title, nbr_plots, titles, traces_per_plot, legends=legends,  minmax=(-1,1), grouping= 'traces')
        self.mca = motionCueing()
            
    def plot(self, raw, rates):
        washed = self.mca.wash(rates)
        data = [raw, rates] # washed]
        self.plotter.plot( data)   
      
"""    
def find_xp(sock, wait=1.0):

    # Waits for X-Plane to startup, and returns IP (and other) info
    # wait: floating point, maximum seconds to wait. 0 will block
    # derived from https://github.com/charlylima/XPlaneUDP/blob/master/XPlaneUdp.py

  
    # Set up to listen for a multicast beacon
    # sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)

    if wait > 0:
        sock.settimeout(wait)
    
    beacon_data = {}
    while not beacon_data:
        try:
            packet, sender = sock.recvfrom(15000)
            header = packet[0:5]
            if header != b"BECN\x00":
                print("Unknown packet from " + sender[0], packet)
            else:
                data = packet[5:21]
                (beacon_major_version, beacon_minor_version, application_host_id,
                 xplane_version_number, role, port) = struct.unpack("<BBiiIH", data)
                computer_name = packet[21:]  # Python3, these are bytes, not a string
                computer_name = computer_name.split(b'\x00')[0]  # get name upto, but excluding first null byte
                if all([beacon_major_version == 1,
                        beacon_minor_version == 2,
                        application_host_id == 1]):
                    beacon_data = {
                        'ip': sender[0],
                        'port': port,
                        'hostname': computer_name.decode('utf-8'),
                        'xplane_version': xplane_version_number
                    }
                    return beacon_data

        except socket.timeout:
            print("wha timeout")
            return None
        except TimeoutError: 
            return None
        return None
"""        

    
    
"""
read and set xplane flight controls
command msg format:  'cmd;{"Parking_brake":(0/1),"Landing_gear":(0/1),"Flaps":(0..1),"Throttle":(0..1),"Mixture":(0..1)}\n'  
event msg format     'evt;{"Parking_brake":(0/1),"Landing_gear":(0/1),"Flaps":(0..1),"Throttle":(0..1),"Mixture":(0..1)}\n

"""
class Controls():
    def __init__(self, xplane_ip, controls_port):
        self.xplane_ip = xplane_ip
        self.port = controls_port # port in xplane plugin listening for these messages
                                  # send port is self.port-1 
        self.xplane_udp = UdpReceive(controls_port+1)         
        self.msg_fields =  ('Parking_brake', 'Landing_gear', 'Flaps', 'Throttle', 'Mixture')
        self.evt_cache =     [0,              0,              0,       0,          0] # cache received values
        
    def read(self):
        while self.xplane_udp.available() > 0:
            self.sender, payload = self.xplane_udp.get()
            # print( self.sender,payload)
            try:
                msg = payload.split(';') 
                if len(msg) == 2 and msg[0] == 'evt':
                    json_cmds = json.loads(msg[1])
                    for field in json_cmds:
                        try:
                            Index = self.msg_fields.index(field) 
                            if self.evt_cache[Index] != json_cmds[field]:
                                self.evt_cache[Index] = json_cmds[field]
                                #  xp.setWidgetDescriptor(self.InputEdit[Index], '{:.3f}'.format(self.cmd_cache[Index]))
                                #print(field, self.cmd_dict[field], 'index=', self.fields.index(field), 'sender', got[0])
                        except ValueError:
                            xp.log('unexpected field: {}'.format(field)) 
                            pass # field is not one of our commands
            except Exception as e:
                print('Control read error', str(e))
                self.xplane_udp.send('! ' + str(e), self.sender) 
    
  
            while self.xplane_udp.available() > 0:
                self.sender,payload = self.xplane_udp.get()
                data = msg[1].split(',')
                if data[0] == 'evt':
                    xyzrpy = [float(ele) for ele in data[1:7]]  
                    # print(msg)                    
                    return xyzrpy
            return (0,0,0,0,0,0)
    
    def set_brake(self, value):
        # 0 brake off, 1 is on     
        self.send(value, 'Parking_brake')
        
    def set_gear(self, value):
        self.send('Landing_gear', value)

    def set_flaps(self, value):
        self.send('Flaps', value)
        
    def set_throttle(self, value):
        self.send('Throttle', value)
        
    def send(self, field, value):
        cmd = 'cmd;{"' + field + '":{:.3f}}}'.format(value)
        print("sending cmd {} as {} ({})".format(field, value, cmd))
        self.xplane_udp.send(cmd, ( self.xplane_ip, self.port-1)) # default send port is 10024    