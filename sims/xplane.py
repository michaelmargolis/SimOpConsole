# sim class for X-Plane using XPPython3 Mdx_telemetry and Mdx_controls plugins
# update 26 Feb 2025: xplane_itf module no longer required

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
from . import xplane_cfg as config


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

class Sim():
    """ this class is imported by the motion platform SimInterface """
    def __init__(self, sleep_func, frame, report_state_cb):
        self.sleep_func = sleep_func
        self.frame = frame
        self.report_state_cb = report_state_cb
        self.name = "X-Plane"
        self.prev_yaw = None
        self.norm_factors = config.norm_factors # edit xplane_cfg.py to change
        self.washout_callback = None
        self.xplane_udp = UdpReceive(TELEMETRY_EVT_PORT) 
        # setup xplane beacon multicast receiver
        MCAST_GRP = '239.255.1.1'  # Standard multicast group
        MCAST_PORT = 49707  # (MCAST_PORT was 49000 for XPlane10)
        self.beacon = UdpReceive(MCAST_PORT, None, MCAST_GRP)
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
        self.beacon.clear() # remove queued msgs and wait for a new on
        self.last_beacon_time = time.time()
        self.state = State.INITIALIZED


    def receive_beacon_message(self):
        # truncated version just check prolog and return ip address if valid
        """
        if self.beacon.available():
            addr, message = self.beacon.get()
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
        if self.beacon.available():
            addr, message = self.beacon.get()
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
        
    def ui_action(self, action):
        if action[-3:] == 'sit':
           print("do situation", action)
           self.situation(action)      

        elif action[-3:] == 'rep':
            print("do replay", action)
            self.replay(action)                 
    
    def set_state_callback(self, callback):
        self.report_state_cb = callback
        
    def set_default_address(self, ip_address):
            pass # code may be added here if needed  

    def load(self, loader):
        log.info("Load not supported in this version")
    
    def connect(self, server_addr = None):
        self.service(self.washout_callback)   

    def is_Connected(self):
        return True  # xplane autoconnects if needed so return True in any state
        
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
        
    def fin(self):
        self.xplane_udp.close()
        self.beacon.close()
        
    def run(self):
        if self.state == State.RECEIVING_DATAREFS:
            self.xplane_udp.send('Run', (self.xplane_ip, TELEMETRY_CMD_PORT))
        else:
            print("X-Plane is not connected")

    def play(self):
        # start the preselected play file 
        if self.state == State.RECEIVING_DATAREFS:
            self.xplane_udp.send('Play', (self.xplane_ip, TELEMETRY_CMD_PORT))
        else:
            print("X-Plane is not connected")
            
    def pause(self):
        if self.state == State.RECEIVING_DATAREFS:
            self.xplane_udp.send('Pause', (self.xplane_ip, TELEMETRY_CMD_PORT))
        else:    
            print("X-Plane is not connected")    
    
    def reset_playback(self):
        if self.state == State.RECEIVING_DATAREFS:
            #self.send_CMND('sim/replay/rep_end') # only needed because of bug in replay
            #self.send_CMND('sim/replay/rep_begin')
            self.xplane_udp.send('Reset_playback', (self.xplane_ip, TELEMETRY_CMD_PORT)) 
        else:
            print("X-Plane is not connected")                 
 
    def read(self):
        return self.service(self.washout_callback)
  
    def set_scenario(self, mode, skill_level):
        if self.state == State.RECEIVING_DATAREFS:
            msg = f'Scenario,{mode},{skill_level}'
            print("sending:", msg)
            self.xplane_udp.send(msg, (self.xplane_ip, TELEMETRY_CMD_PORT))
            # self.pause() # is this needed?
        else:
            print("Not connected to X-Plane, scenario not sent")
     
    # NOT USED int this version: replay,   set_situation, send_SIMO, send_CMND
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

    def set_situation(self, filename): 
        # self.send_SIMO(1, filename)
      
        msg = f"Situation,{filename}"
        print(f"sending {msg} to {self.xplane_ip}:{TELEMETRY_CMD_PORT}")
        self.xplane_udp.send(msg, (self.xplane_ip, TELEMETRY_CMD_PORT))  
        return

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
        filename_bytes = filename.encode('utf-8') + b'\x00'
        filename_padded = filename_bytes.ljust(153, b'\x00')  # Ensure exactly 150 bytes
        msg = struct.pack('<4s i 153s', b'SIMO', command, filename_padded)
        print(len(msg))

        self.beacon.send_bytes(msg, self.xplane_addr)
        print(f"sent {filename} to {self.xplane_addr} encoded as {msg}")   
   
    def send_CMND(self, command_str):
        msg = 'CMND\x00' + command_str
        self.beacon.send_bytes(msg, self.xplane_addr)
        
    
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
        
    def get_washout_config(self):
        return config.washout_time       
        
    def set_washout_callback(self, callback):
        self.washout_callback = callback 

"""        
if __name__ == "__main__":
    from time import sleep
    from common.plot_itf import PlotItf
    from washout.washout import motionCueing
    RUNTIME_DIR = os.path.dirname(os.path.abspath(__file__))
    sys.path.append(os.path.dirname(RUNTIME_DIR))

    xplane = X_Plane(sleep)
    mca = motionCueing()

       
    plot = 'xform'
    if plot == 'xform':
        nbr_plots = 6
        traces_per_plot = 2
        titles = ('x (surge)', 'y (sway)', 'z (heave)', 'roll', 'pitch', 'yaw')
        legends = ('from xplane', 'washed')
    else:
        nbr_plots =3
        traces_per_plot = 4
        titles = ('axil', 'side', 'normal')
        legends = ('prop', 'aero', 'gear', 'g')

    main_title = "Translations and Rotations from XPlane"  
    plotter = PlotItf(nbr_plots, traces_per_plot, main_title, titles,  legends=legends,  minmax=(-1,1), grouping= 'traces') 
    err = xplane.connect()
    if err:
        print(err)
    else:
        while(1): 
            transform = xplane.telemetry.read(None)      #fixme washout is not implimented!!      
            washed = mca.wash(transform)
            if plot == 'xform':                 
                data = [transform, washed]
            else:    
               data = xplane._get_xlate()
            print("<",data,">")   
            plotter.plot( data)
            sleep(.05)
"""