import sys
import os
import json
import time
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtMultimediaWidgets import QVideoWidget
from PyQt5.QtCore import QUrl, QTimer, Qt
from PyQt5 import uic
from udp_tx_rx import UdpReceive
from datetime import datetime

from playback_engine import PlaybackEngine

version = "0.5.1"

# Norm factors copied from main code
norm_factors = [0.8, 0.8, 0.2, -1.5, 1.5, -1.5]
TARGET_PORT = 10022
HEARTBEAT_PORT = 10030
TELEMETRY_PORT = 10023
FRAME_DURATION_MS = 25

        
class SpoofXPlaneApp(QMainWindow):
    def __init__(self):
        super().__init__()
        uic.loadUi("spoof_xplane.ui", self)

        self.transform_values = [0] * 6
        self.icao_code = "C172"
        self.xplane_running = True
        self.enable_telemetry = True
        self.is_playing = False
        self.is_paused = False
        self.media_loaded = False
        self.duration_ms: int | None = None

        self.controller_addr = "127.0.0.1"
        self.playback_engine = None

        self.sliders = [self.findChild(type(self.sld_gain_0), f"sld_gain_{i}") for i in range(6)]
        for slider in self.sliders:
            slider.setRange(-100, 100)
            slider.setValue(0)
            slider.valueChanged.connect(self.update_values)

        self.txt_icao.textChanged.connect(self.update_icao)
        self.chk_xplane_running.stateChanged.connect(self.update_running_state)
        self.chk_enable_telemetry.stateChanged.connect(self.update_enable_telemetry)
        self.btn_load_file.clicked.connect(self.load_file)
        self.btn_playback.clicked.connect(self.toggle_playback)
        self.btn_pause.clicked.connect(self.toggle_pause)
        self.sld_record.valueChanged.connect(self.update_slider)

        self.heartbeat_udp = UdpReceive(HEARTBEAT_PORT)
        self.telemetry_udp = UdpReceive(TELEMETRY_PORT)

        self.config_video()

        self.timer = QTimer()
        self.timer.timeout.connect(self.main_tick)
        self.timer.start(FRAME_DURATION_MS)
       
        self.setWindowTitle(f"Spoof XPlane v{version}")


    def config_video(self):
        self.video_window = QMainWindow(self)
        self.video_window.setWindowTitle("Video Playback")
        self.video_window.resize(800, 585)
        self.video_widget = QVideoWidget()
        self.video_window.setCentralWidget(self.video_widget)
        self.media_player = QMediaPlayer(self)
        self.media_player.setVideoOutput(self.video_widget)

    def update_values(self):
        self.transform_values = [s.value() / 100.0 for s in self.sliders]

    def update_icao(self, text):
        self.icao_code = text

    def update_running_state(self, state):
        self.xplane_running = (state == Qt.Checked)

    def update_enable_telemetry(self, state):
        self.enable_telemetry = (state == Qt.Checked)

    def load_file(self):
        self.filename = self.txt_playback.text()
        self.btn_playback.setEnabled(False)
        self.btn_pause.setEnabled(False)

        video_path = self.filename + '.mp4'
        csv_path = self.filename + '.csv'

        if os.path.exists(csv_path):
            self.btn_playback.setEnabled(True)
            self.btn_pause.setEnabled(True)

            if os.path.exists(video_path):
                self.media_loaded = True
                self.media_player.setMedia(QMediaContent(QUrl.fromLocalFile(video_path)))
                self.media_player.mediaStatusChanged.connect(self.show_first_frame)
                self.video_window.show()
            else:
                self.media_loaded = False

            self.playback_engine = PlaybackEngine(
                csv_path=csv_path,
                callback=self.handle_playback_record,
                video_time_fn=(lambda: self.media_player.position()) if self.media_loaded else None
            )
            self.duration_ms = self.playback_engine.duration_ms

    def show_first_frame(self, status):
        if status == QMediaPlayer.LoadedMedia:
            self.media_player.setPosition(0)
            self.media_player.pause()
            self.media_player.mediaStatusChanged.disconnect(self.show_first_frame)

    def toggle_playback(self):
        if self.is_playing:
            self.playback_engine.stop()
            self.media_player.stop()
            self.is_playing = False
            self.btn_playback.setText("Play")
        else:
            try:
                self.playback_engine.play()
                self.icao_code = self.playback_engine.get_vehicle_name() or "C172"
                self.txt_icao.setText(self.icao_code)
                if self.media_loaded:
                    self.media_player.play()
                self.is_playing = True
                self.btn_playback.setText("Stop")
            except Exception as e:
                print(f"Playback failed: {e}")

    def toggle_pause(self):
        if not self.playback_engine:
            return

        self.is_paused = not self.is_paused
        if self.is_paused:
            self.playback_engine.pause()
            if self.media_loaded:
                self.media_player.pause()
            self.btn_pause.setText("Resume")
        else:
            self.playback_engine.resume()
            if self.media_loaded:
                self.media_player.play()
            self.btn_pause.setText("Pause")

    def update_slider(self, value):
        if not self.playback_engine or not self.is_playing:
            return
        print("wha dur", self.duration_ms)  
        # Convert slider value (0–10000) to ms
        target_ts = (value / self.sld_record.maximum()) * self.duration_ms

        # Seek to the closest index
        records = self.playback_engine.records
        idx = next((i for i, r in enumerate(records) if r[0] >= target_ts), len(records) - 1)

        self.playback_engine.index = idx

        # Reset start_perf_time so playback resumes at correct time
        self.playback_engine.start_perf_time = time.perf_counter() - (records[idx][0] / 1000.0)
        self.playback_engine.accumulated_pause = 0

        if self.media_loaded:
            self.media_player.setPosition(int(records[idx][0]))

        # Optional: immediately show new frame
        self.handle_playback_record(records[idx])


    def handle_playback_record(self, rec):
        if len(rec) > 6:
            # Set sliders from playback values
            # print(rec)
            for i in range(6):
                val = rec[i + 1] * norm_factors[i] * (-1 if i != 2 else 1)
                self.sliders[i].setValue(round(val * 100))
            self.update_values()  # Ensure transform_values is updated

            # Send telemetry for this frame
            self.send_telemetry()

            # Update time label
            timestamp = rec[0]
            self.txt_recno.setText(f"{timestamp / 1000:.2f}s")
            # Sync slider position with timestamp
            if self.duration_ms and self.duration_ms > 0:
                percent = timestamp / self.duration_ms
                slider_val = int(percent * self.sld_record.maximum())
                self.sld_record.blockSignals(True)
                self.sld_record.setValue(slider_val)
                self.sld_record.blockSignals(False)


    def send_telemetry(self):
        if not self.enable_telemetry:
            return
        telemetry_dict = {
            "header": "xplane_telemetry",
            "g_axil": -self.transform_values[0] / norm_factors[0],
            "g_side": -self.transform_values[1] / norm_factors[1],
            "g_nrml": self.transform_values[2] / norm_factors[2],
            "Prad": 0,
            "Qrad": 0, 
            "Rrad": -self.transform_values[5] / norm_factors[5],
            "phi": -self.transform_values[3] / norm_factors[3],
            "theta": -self.transform_values[4] / norm_factors[4],
            "icao": self.icao_code
        }
        try:
            self.telemetry_udp.send(json.dumps(telemetry_dict), (self.controller_addr, TARGET_PORT))
        except Exception as e:
            print(e)

    def main_tick(self):
        if self.playback_engine and self.is_playing and not self.is_paused:
            self.playback_engine.tick()
        else:
            self.send_telemetry()
        self.service_heartbeat()

    def service_heartbeat(self):
        if self.heartbeat_udp.available():
            while self.heartbeat_udp.available():
                addr, payload = self.heartbeat_udp.get()
            timestamp = datetime.now().strftime("%H:%M:%S")
            reply = f"{'xplane_running' if self.xplane_running else 'X-Plane not detected'} at {timestamp}"
            self.heartbeat_udp.send(reply, addr)

        while self.telemetry_udp.available():
            self.service_command_msgs()

    def service_command_msgs(self):
        try:
            addr, payload = self.telemetry_udp.get()
            msg = payload.split(',')
            cmd = msg[0].strip()

            if cmd == 'InitComs':
                print(f"[INFO] InitComs received by controller at {addr[0]}")
            elif cmd == 'Run':
                print("[INFO] Run command received. Unpausing X-Plane.")
                self.is_paused = False
            elif cmd == 'PauseToggle':
                print("[INFO] Pause toggle command received.")
            elif cmd == 'Pause':
                print("[INFO] Pause command received.")
                self.is_paused = True
            elif cmd == 'Replay' and len(msg) > 1:
                print(f"[INFO] Loaded Replay: {msg[1].strip()}")
            elif cmd == 'Situation' and len(msg) > 1:
                print(f"[INFO] Loaded Situation: {msg[1].strip()}")
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
    win = SpoofXPlaneApp()
    win.show()
    sys.exit(app.exec_())
