import sys
import json
from PyQt5.QtWidgets import QApplication, QWidget, QMainWindow
from PyQt5 import uic
from PyQt5.QtCore import Qt, QTimer
from udp_tx_rx import UdpReceive
from datetime import datetime

from telemetry_rec_play import TelemetryPlayer, TelemetryError 

# Norm factors copied from main code
norm_factors = [0.8, 0.8, 0.2, -1.5, 1.5, -1.5]
TARGET_PORT = 10022
HEARTBEAT_PORT = 10030
TELEMETRY_PORT = 10023

FRAME_DURATION_MS = 25
SKIP_FRAMES = 0  # set to 1 to skip every other frame

class DummyXPlaneApp(QMainWindow):
    def __init__(self):
        super().__init__()
        uic.loadUi("dummy_xplane.ui", self)  # Load UI file

        self.transform_values = [0] * 6
        self.icao_code = "C172"
        self.xplane_running = True
        self.enable_telemetry = True
        self.is_playing = False
        self.is_paused = False
        self.player = TelemetryPlayer()
        
        self.controller_addr = "127.0.0.1"

        # Collect slider widgets
        self.sliders = [
            self.findChild(type(self.sld_gain_0), f"sld_gain_{i}")
            for i in range(6)
        ]

        # Connect signals
        for slider in self.sliders:
            slider.setRange(-100, 100)
            slider.setValue(0)
            slider.valueChanged.connect(self.update_values)

        self.txt_icao.textChanged.connect(self.update_icao)
        self.chk_xplane_running.stateChanged.connect(self.update_running_state)
        self.chk_enable_telemetry.stateChanged.connect(self.update_enable_telemetry)
        self.btn_playback.clicked.connect(self.playback_started)

        self.heartbeat_udp = UdpReceive(HEARTBEAT_PORT)
        self.telemetry_udp = UdpReceive(TELEMETRY_PORT)

        # Timer to drive output frames
        self.timer = QTimer()
        self.timer.timeout.connect(self.loop)
        self.timer.start(FRAME_DURATION_MS)  # 25ms = 40Hz, 50ms = 20hz
        self.frame_count = 0

    def update_values(self):
        self.transform_values = [s.value() / 100.0 for s in self.sliders]

    def update_icao(self, text):
        self.icao_code = text

    def update_running_state(self, state):
        self.xplane_running = (state == Qt.Checked)

    def update_enable_telemetry(self, state):
        self.enable_telemetry = (state == Qt.Checked)

    def playback_started(self):
        if self.is_playing:
            self.is_playing = False
            self.player.stop_playback()
            self.btn_playback.setText("Play")
        else:
            fname = self.txt_playback.text()
            try:
                self.player.start_playback(fname)
                self.icao_code  = self.player.vehicle
                self.txt_icao.setText(self.icao_code)
                self.frame_count = 0
            except TelemetryError as err:
                print(f"Cannot start playback: {err}")
                return
                
            self.is_playing = True
            self.btn_playback.setText("Stop")

    def send_telemetry(self):
        if self.is_playing and not self.is_paused :
            rec = self.player.playback_service()
            self.frame_count += 1
            for i in range(6):
                if i == 2:
                    self.sliders[2].setValue(round(rec[2] * norm_factors[i] * 100))
                else:    
                    self.sliders[i].setValue(round(rec[i] * norm_factors[i] * -100))

        if self.enable_telemetry:
            if SKIP_FRAMES == 0 or (SKIP_FRAMES > 0 and self.frame_count % (SKIP_FRAMES + 1) == 0):  
                telemetry_dict = {
                    "header": "xplane_telemetry",
                    "g_axil": -self.transform_values[0] / norm_factors[0],
                    "g_side": -self.transform_values[1] / norm_factors[1],
                    "g_nrml": self.transform_values[2] / norm_factors[2],
                    "Prad": -self.transform_values[3] / norm_factors[3],
                    "Qrad": -self.transform_values[4] / norm_factors[4],
                    "Rrad": -self.transform_values[5] / norm_factors[5],
                    "phi": 0,
                    "theta": 0,
                    "icao": self.icao_code
                }
                telemetry_json = json.dumps(telemetry_dict)
                try:
                    self.telemetry_udp.send(telemetry_json, (self.controller_addr, TARGET_PORT))
                    # print(f"[SEND] frame {self.frame_count}: {telemetry_json} -> {self.controller_addr}:{TARGET_PORT}")
                except Exception as e:
                    print(e)

    def loop(self):
        # Handle heartbeat
        if self.heartbeat_udp.available():
            while self.heartbeat_udp.available() > 0:
                addr, payload = self.heartbeat_udp.get()
            timestamp = datetime.now().strftime("%H:%M:%S")
            if self.xplane_running:
                reply = f"xplane_running at {timestamp}"
            else:
                reply = f"X-Plane not detected at {timestamp}"
            self.heartbeat_udp.send(reply, addr)
            print(f"[HEARTBEAT] {reply} -> {addr}")

        # Send telemetry every 25ms automatically
        self.send_telemetry()
        while self.telemetry_udp.available() > 0:
            self.service_command_msgs()

    def service_command_msgs(self):
        if self.telemetry_udp.available() > 0:
            try:
                addr, payload = self.telemetry_udp.get()
                msg = payload.split(',')
                cmd = msg[0].strip()

                if cmd == 'InitComs':
                    print(f"[INFO] InitCOms received by controller at {addr[0]}")

                elif cmd == 'Run':
                    print("[INFO] Run command received. Unpausing X-Plane.")
                    self.is_paused = False

                elif cmd == 'PauseToggle':
                    print("[INFO] Pause toggle command received.")

                elif cmd == 'Pause':
                    print(f"[INFO] Pause command received. Current pause state: ?")
                    self.is_paused = True

                elif cmd == 'Replay' and len(msg) > 1:
                    filepath = msg[1].strip()
                    print(f"[INFO] Loaded Replay: {filepath}, return={ret}")

                elif cmd == 'Situation' and len(msg) > 1:
                    filepath = msg[1].strip()
                    print(f"[INFO] Loaded Situation: {filepath}, return={ret}")

                elif cmd == 'FlightMode' and len(msg) > 1:
                    try:
                        mode = int(msg[1].strip())
                        print(f"[INFO] Flight mode received: {mode}")
                    except Exception as e:
                        print(f"[ERROR] FlightMode invalid: {e}")
                        
                elif cmd == 'AssistLevel' and len(msg) > 1:
                    try:
                        level = int(msg[1].strip())
                        if 0 <= level <= 2:
                            print(f"[INFO] Assist level received: {level}")
                        else:
                            print(f"[WARN] AssistLevel out of range: {level}")
                    except Exception as e:
                        print(f"[ERROR] AssistLevel invalid: {e}")

            except Exception as e:
                print(f"[ERROR] UDP command handling failed: {e}")
                
    def closeEvent(self, event):
        self.heartbeat_udp.close()
        self.telemetry_udp.close()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = DummyXPlaneApp()
    win.show()
    sys.exit(app.exec_())
