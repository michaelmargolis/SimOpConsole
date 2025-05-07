"""
Mdx_Telemetry Plugin 
Written by Michael Margolis
Updated with ICAO identifier 28March 2025

This plugin sends 6DoF motion telemetry and aircraft identifier (ICAO code) from X-Plane to an external controller via UDP.

Coordinate Conventions:
-----------------------
X-Plane uses OpenGL coordinates: 
    - X = right, Y = up, Z = back

Mdx follows ROS-style platform coordinates:
    - X = forward, Y = left, Z = up
    - Roll = right wing down, Pitch = nose down, Yaw = counterclockwise (CCW)
    - Telemetry is converted to match this convention

DataRef Mappings (from X-Plane):
--------------------------------
Accelerations (in Gs):
    - g_axil  → Surge (X), inverted
    - g_side  → Sway (Y), inverted
    - g_nrml  → Heave (Z), adjusted to remove gravity (i.e., 0 = 1G)

Angular Rates (rad/s):
    - Prad    → Roll rate, inverted
    - Qrad    → Pitch rate, inverted
    - Rrad    → Yaw rate, inverted

Angular Positions (degrees → radians):
    - phi     → Roll (bank), converted and signed
    - theta   → Pitch, converted and inverted

Aircraft Identifier:
--------------------
    - sim/aircraft/type/acf_ICAO → Appended to telemetry message

Telemetry UDP Message Format:
-----------------------------
Message Prefix: xplane_telemetry,
Message Payload:
    surge_accel, sway_accel, heave_accel,
    roll_rate, pitch_rate, yaw_rate,
    roll_angle, pitch_angle, ICAO

Example:
    xplane_telemetry,-0.020,0.005,-0.980,-0.003,0.000,-0.002,0.087,-0.045,C172
"""
import json
from XPPython3 import xp
from collections import namedtuple
from math import radians
from udp_tx_rx import UdpReceive
from situation_loader import SituationLoader
from accessibility import load_accessibility_settings, set_accessibility


transform_refs = namedtuple('transform_refs', (
    'DR_g_axil', 'DR_g_side', 'DR_g_nrml',
    'DR_Prad', 'DR_Qrad', 'DR_Rrad',
    'DR_theta', 'DR_psi', 'DR_phi',
    'DR_groundspeed'
))

TARGET_PORT = 10022

class PythonInterface:
    def XPluginStart(self):
        self.Name = "PlatformItf v1.01"
        self.Sig = "Mdx.Python.UdpTelemetry"
        self.Desc = "Sends 6DoF telemetry + ICAO code over UDP to platform."

        self.controller_addr = []
        self.udp = UdpReceive(10023)
        self.situation_loader = SituationLoader()
        self.settings = load_accessibility_settings()

        self.init_drefs()
        xp.registerFlightLoopCallback(self.InputOutputLoopCallback, 1.0, 0)

        return self.Name, self.Sig, self.Desc

    def XPluginStop(self):
        xp.unregisterFlightLoopCallback(self.InputOutputLoopCallback, 0)
        self.udp.close()

    def XPluginEnable(self):
        return 1

    def XPluginDisable(self):
        pass

    def XPluginReceiveMessage(self, inFromWho, inMessage, inParam):
        pass

    def init_drefs(self):
        self.xform_drefs = [
            'sim/flightmodel/forces/g_axil',
            'sim/flightmodel/forces/g_side',
            'sim/flightmodel/forces/g_nrml',
            'sim/flightmodel/position/Prad',
            'sim/flightmodel/position/Qrad',
            'sim/flightmodel/position/Rrad',
            'sim/flightmodel/position/theta',
            'sim/flightmodel/position/psi',
            'sim/flightmodel/position/phi',
            'sim/flightmodel/position/groundspeed'
        ]
        self.OutputDataRef = [xp.findDataRef(ref) for ref in self.xform_drefs]
        self.NumberOfDatarefs = len(self.OutputDataRef)
        self.pauseCmd = xp.findCommand("sim/operation/pause_toggle")
        self.pauseStateDR = xp.findDataRef("sim/time/paused")
        self.replay_play = xp.findCommand("sim/replay/rep_play_rf")
        self.go_to_replay_begin = xp.findCommand("sim/replay/rep_begin")
        self.acf_icao_ref = xp.findDataRef("sim/aircraft/view/acf_ICAO")
        if self.acf_icao_ref is None:
            xp.log("[WARN] acf_icao_ref dataref not found.")

    def InputOutputLoopCallback(self, elapsedMe, elapsedSim, counter, refcon):
        try:
            # telemetry, icao = self.read_telemetry()
            # msg = "xplane_telemetry," + ",".join(f"{x:.3f}" for x in telemetry) + f",{icao}\n"
            msg = self.read_telemetry()
            for addr in self.controller_addr:
                self.udp.send(msg, (addr, TARGET_PORT))
        except Exception as e:
            xp.log(f"[ERROR] Telemetry send failed: {e}")

        while self.udp.available() > 0:
            try:
                addr, payload = self.udp.get()
                msg = payload.split(',')
                cmd = msg[0].strip()

                if cmd == 'InitComs':
                    if addr[0] not in self.controller_addr:
                        self.controller_addr.append(addr[0])
                        xp.log(f"[INFO] Controller added: {addr[0]}")

                elif cmd == 'Run':
                    if xp.getDatai(self.pauseStateDR):
                        xp.log("[INFO] Run command received. Unpausing X-Plane.")
                        xp.commandOnce(self.pauseCmd)

                elif cmd == 'PauseToggle':
                    xp.log("[INFO] Pause toggle command received.")
                    xp.commandOnce(self.pauseCmd)

                elif cmd == 'Pause':
                    is_paused = xp.getDatai(self.pauseStateDR)
                    xp.log(f"[INFO] Pause command received. Current pause state: {is_paused}")
                    if not is_paused:
                        xp.commandOnce(self.pauseCmd)

                elif cmd == 'Play':
                    xp.commandOnce(self.replay_play)

                elif cmd == 'Reset_playback':
                    xp.commandOnce(self.go_to_replay_begin)

                elif cmd == 'Replay' and len(msg) > 1:
                    filepath = msg[1].strip()
                    ret = xp.loadDataFile(xp.DataFile_ReplayMovie, filepath)
                    xp.log(f"[INFO] Loaded Replay: {filepath}, return={ret}")

                elif cmd == 'Situation' and len(msg) > 1:
                    filepath = msg[1].strip()
                    ret = xp.loadDataFile(xp.DataFile_Situation, filepath)
                    xp.log(f"[INFO] Loaded Situation: {filepath}, return={ret}")

                elif cmd == 'FlightMode' and len(msg) > 1:
                    try:
                        mode = int(msg[1].strip())
                        self.situation_loader.load_situation(mode)
                    except Exception as e:
                        xp.log(f"[ERROR] FlightMode invalid: {e}")
                        
                elif cmd == 'AssistLevel' and len(msg) > 1:
                    try:
                        level = int(msg[1].strip())
                        if 0 <= level <= 2:
                            xp.log(f"[INFO] Assist level received: {level}")
                            set_accessibility(['HIGH', 'MODERATE', 'NONE'][level])
                            xp.log(f"[INFO] Set Pilot Assist to: {['HIGH', 'MODERATE', 'NONE'][level]}")
                        else:
                            xp.log(f"[WARN] AssistLevel out of range: {level}")
                    except Exception as e:
                        xp.log(f"[ERROR] AssistLevel invalid: {e}")

            except Exception as e:
                xp.log(f"[ERROR] UDP command handling failed: {e}")

        return 0.025

    def read_telemetry(self):
        try:
            if self.acf_icao_ref is not None:
                icao_buf = [0] * 40
                xp.getDatab(self.acf_icao_ref, icao_buf, 0, 40)
                icao = bytes(icao_buf).decode('utf-8').strip('\x00')
            else:
                raise ValueError("acf_icao_ref is None")
        except Exception as e:
            # xp.log(f"[WARN] Failed to read ICAO: {e}")
            icao = "unknown"
            
        data = [xp.getDataf(ref) for ref in self.OutputDataRef]
        named = transform_refs._make(data)
        
        telemetry_dict = {
            "header": "xplane_telemetry",
            "g_axil":  -named.DR_Rrad,
            "g_side":  -named.DR_Qrad,
            "g_nrml":  -named.DR_Prad,
            "Prad":    named.DR_g_nrml - 1.0,
            "Qrad":    -named.DR_g_side,
            "Rrad":    -named.DR_g_axil,
            "phi":     radians(named.DR_phi),
            "theta":   -radians(named.DR_theta),
            "icao":     icao
        }
        telemetry_json = json.dumps(telemetry_dict)
        return telemetry_json
        
    """
    def read_telemetry(self):
        try:
            data = [xp.getDataf(ref) for ref in self.OutputDataRef]
            named = transform_refs._make(data)
            telemetry = [
                -named.DR_g_axil,
                -named.DR_g_side,
                named.DR_g_nrml - 1.0,
                -named.DR_Prad,
                -named.DR_Qrad,
                -named.DR_Rrad,
                radians(named.DR_phi),
                -radians(named.DR_theta)
            ]

            try:
                if self.acf_icao_ref is not None:
                    icao_buf = [0] * 40
                    xp.getDatab(self.acf_icao_ref, icao_buf, 0, 40)
                    icao = bytes(icao_buf).decode('utf-8').strip('\x00')
                else:
                    raise ValueError("acf_icao_ref is None")
            except Exception as e:
                xp.log(f"[WARN] Failed to read ICAO: {e}")
                icao = "unknown"

            return telemetry, icao
        except Exception as e:
            xp.log(f"[ERROR] Telemetry read failed: {e}")
            return [0.0] * 8, "unknown"
    """ 



