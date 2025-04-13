# sim.py (complete version with state machine integration)

import os, sys
import socket
import struct
import traceback
import copy
import time
import logging
from enum import Enum

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from common.udp_tx_rx import UdpReceive
from . import xplane_cfg as config
from .xplane_cfg import TELEMETRY_CMD_PORT, TELEMETRY_EVT_PORT, MCAST_GRP, MCAST_PORT, HEARTBEAT_PORT
from .state_machine import SimStateMachine, SimState
from .shared_types import AircraftInfo

log = logging.getLogger(__name__)


class Sim:
    def __init__(self, sleep_func, frame, report_state_cb):
        self.sleep_func = sleep_func
        self.frame = frame
        self.report_state_cb = report_state_cb
        self.name = "X-Plane"
        self.prev_yaw = None
        self.norm_factors = config.norm_factors
        self.washout_callback = None
        self.xplane_udp = UdpReceive(TELEMETRY_EVT_PORT)
        self.beacon = UdpReceive(MCAST_PORT, None, MCAST_GRP)
        self.BEACON_TIMEOUT = 2
        self.state = SimState.INITIALIZED
        self.last_beacon_time = None
        self.xplane_ip = None
        self.xplane_addr = None
        self.aircraft_info = AircraftInfo(status="nogo", name="Aircraft")
        self.state_machine = SimStateMachine(self)
        self.heartbeat = UdpReceive(HEARTBEAT_PORT+1)
        self.heartbeat_ok = False
        self.xplane_running = False
        self.last_heartbeat_recv_time = None
        self.last_heartbeat_ping_time = 0
        self.HEARTBEAT_INTERVAL = 1.0  # seconds
        self.HEARTBEAT_TIMEOUT = 2.0
 
    def service(self, washout_callback = None):
        return self.state_machine.handle(washout_callback)

    def read(self):
        return self.service(self.washout_callback)

    def connect(self, server_addr=None):
        self.service(self.washout_callback)

    def set_default_address(self, ip_address):
        pass

    def set_state_callback(self, callback):
        self.report_state_cb = callback

    def set_washout_callback(self, callback):
        self.washout_callback = callback

    def get_washout_config(self):
        return config.washout_time

    def is_Connected(self):
        return True

    def get_connection_state(self):
        self.query_heartbeat_status()

        # Send heartbeat ping at interval
        now = time.time()
        if self.xplane_ip and now - self.last_heartbeat_ping_time > self.HEARTBEAT_INTERVAL:
            try:
                self.heartbeat.send("ping", (self.xplane_ip, HEARTBEAT_PORT))
                self.last_heartbeat_ping_time = now
            except Exception as e:
                log.warning(f"Heartbeat send failed: {e}")

        # Determine connection status
        if not self.heartbeat_ok:
            connection_status = "nogo"      # Red
        elif not self.xplane_running:
            connection_status = "warning"   # Orange
        else:
            connection_status = "ok"        # Green

        # Determine data stream status (now includes 'warning' as spec'd)
        if connection_status != "ok":
            data_status = "nogo"
        elif self.state != SimState.RECEIVING_DATAREFS:
            data_status = "warning"
        else:
            data_status = "ok"

        # Aircraft status and label
        if connection_status != "ok":
            aircraft_info = AircraftInfo(status="nogo", name="Aircraft")
        elif self.state != SimState.RECEIVING_DATAREFS:
            aircraft_info = AircraftInfo(status="warning", name=self.aircraft_info.name)
        else:
            name = self.aircraft_info.name
            status = "ok" if self.is_icao_supported(name) else "nogo"
            aircraft_info = AircraftInfo(status=status, name=name)

        return connection_status, data_status, aircraft_info

    def is_icao_supported(self, icao):
        return icao.startswith("C172")  # Placeholder – replace with config-based check

    def query_heartbeat_status(self):
        try: 
            if self.heartbeat.available():
                while self.heartbeat.available():  # get most recent message
                    addr, message = self.heartbeat.get()
                self.heartbeat_ok = True
                self.xplane_running = "xplane_running" in message
                self.last_heartbeat_recv_time = time.time()
            else:
                # Check for timeout if no new message was received
                if self.last_heartbeat_recv_time is None or (time.time() - self.last_heartbeat_recv_time) > self.HEARTBEAT_TIMEOUT:
                    self.heartbeat_ok = False
                    self.xplane_running = False
        except Exception:
            self.heartbeat_ok = False
            self.xplane_running = False

    def receive_beacon_message(self):
        if self.beacon.available():
            addr, message = self.beacon.get()
            if message.startswith(b'BECN\0'):
                message = message[5:21]
                try:
                    unpacked_data = struct.unpack('<BBiiI H', message)
                    beacon_info = {
                        'beacon_major_version': unpacked_data[0],
                        'beacon_minor_version': unpacked_data[1],
                        'application_host_id': unpacked_data[2],
                        'version_number': unpacked_data[3],
                        'role': unpacked_data[4],
                        'port': unpacked_data[5],
                        'ip': addr[0]
                    }
                    self.last_beacon_time = time.time()
                    log.debug(f"Updated beacon timestamp: {self.last_beacon_time}")
                    return beacon_info
                except struct.error as e:
                    log.error(f"Failed to unpack beacon message: {e}")
            else:
                log.warning("Received message with incorrect prologue.")
        return None

    def run(self):
        self._send_command('Run')

    def play(self):
        self._send_command('Play')

    def pause(self):
        self._send_command('Pause')

    def reset_playback(self):
        self._send_command('Reset_playback')

    def set_flight_mode(self, mode):
        self._send_command(f'FlightMode,{mode}')

    def set_pilot_assist(self, level):
        self._send_command(f'AssistLevel,{level}')

    def _send_command(self, msg):
        if self.state == SimState.RECEIVING_DATAREFS:
            self.xplane_udp.send(msg, (self.xplane_ip, TELEMETRY_CMD_PORT))
        else:
            log.warning("X-Plane is not connected")

    def ui_action(self, action):
        if action.endswith('sit'):
            print("do situation", action)
            self.set_situation(action)
        elif action.endswith('rep'):
            print("do replay", action)
            self.replay(action)

    def set_situation(self, filename):
        msg = f"Situation,{filename}"
        print(f"sending {msg} to {self.xplane_ip}:{TELEMETRY_CMD_PORT}")
        self.xplane_udp.send(msg, (self.xplane_ip, TELEMETRY_CMD_PORT))

    def replay(self, filename):
        self.send_SIMO(3, filename)

    def send_SIMO(self, command, filename):
        filename_bytes = filename.encode('utf-8') + b'\x00'
        filename_padded = filename_bytes.ljust(153, b'\x00')
        msg = struct.pack('<4s i 153s', b'SIMO', command, filename_padded)
        print(len(msg))
        self.beacon.send_bytes(msg, self.xplane_addr)
        print(f"sent {filename} to {self.xplane_addr} encoded as {msg}")

    def send_CMND(self, command_str):
        msg = 'CMND\x00' + command_str
        self.beacon.send_bytes(msg, self.xplane_addr)

    def fin(self):
        self.xplane_udp.close()
        self.beacon.close()
        self.heartbeat.close()

    def init_plot(self):
        from .washout import motionCueing
        from common.plot_itf import PlotItf
        nbr_plots = 6
        traces_per_plot = 2
        titles = ('x (surge)', 'y (sway)', 'z (heave)', 'roll', 'pitch', 'yaw')
        legends = ('from xplane', 'washed')
        main_title = "Translations and Rotation washouts from XPlane"
        self.plotter = PlotItf(main_title, nbr_plots, titles, traces_per_plot, legends=legends, minmax=(-1,1), grouping='traces')
        self.mca = motionCueing()

    def plot(self, raw, rates):
        washed = self.mca.wash(rates)
        self.plotter.plot([raw, rates])
