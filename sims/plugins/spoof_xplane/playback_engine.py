import time
import os

class PlaybackEngine:
    def __init__(self, csv_path, callback, video_time_fn=None):
        self.csv_path = csv_path
        self.callback = callback
        self.video_time_fn = video_time_fn

        self.records = []
        self.index = 0
        self.is_playing = False
        self.is_paused = False
        self.start_perf_time = 0
        self.pause_time = 0
        self.accumulated_pause = 0
        self.vehicle = "UNKNOWN"
        self.interval_ms = 25

        self.load_records()

    def load_records(self):
        if not os.path.exists(self.csv_path):
            raise FileNotFoundError(f"CSV not found: {self.csv_path}")

        with open(self.csv_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                if line.startswith("#"):
                    if ":" in line:
                        key, value = line[1:].split(":", 1)
                        key = key.strip()
                        value = value.strip()
                        if key == "vehicle":
                            self.vehicle = value
                        elif key == "interval_ms":
                            try:
                                self.interval_ms = int(value)
                            except ValueError:
                                pass  # fallback to default
                    continue
                try:
                    parts = [float(val) for val in line.split(",")]
                    if parts:
                        parts[0] *= 1000  # Convert timestamp from seconds to ms
                        last_ts = parts[0]
                        self.records.append(parts)
                except ValueError:
                    print(f"[WARN] Skipping malformed data row: {line}")
            self.duration_ms = last_ts

    def get_vehicle_name(self):
        return self.vehicle

    def get_current_timestamp(self):  
        elapsed = time.perf_counter() - self.start_perf_time - self.accumulated_pause
        # print(f"[get ts] elapsed ={elapsed * 1000}, perf counter {time.perf_counter()}, start {self.start_perf_time}, elapsed pause time{self.accumulated_pause}")
        return int(elapsed * 1000)

    def tick(self):
        if not self.is_playing:
            print("[tick] WARNING: tick called while not playing")
    
        if not self.is_playing or self.is_paused or self.index >= len(self.records):
            return

        current_ts = self.get_current_timestamp()
        # print(f"[tick] current_ts = {current_ts}, index = {self.index}")

        while self.index < len(self.records) and self.records[self.index][0] <= current_ts:
            # print(f"[tick] sending record {self.index}, rec_ts = {self.records[self.index][0]}")
            self.callback(self.records[self.index])
            self.index += 1

        if self.index >= len(self.records):
            # print("[tick] End of records reached, stopping playback")
            self.stop()



    def play(self):
        self.is_playing = True
        self.is_paused = False
        self.start_perf_time = time.perf_counter()
        self.accumulated_pause = 0
        self.index = 0
        # print(f"[PlaybackEngine] start_perf_time set to {self.start_perf_time}")

    def pause(self):
        if self.is_playing and not self.is_paused:
            self.pause_time = time.perf_counter()
            self.is_paused = True

    def resume(self):
        if self.is_playing and self.is_paused:
            self.accumulated_pause += time.perf_counter() - self.pause_time
            self.is_paused = False

    def stop(self):
        self.is_playing = False
        self.is_paused = False
        self.index = 0
