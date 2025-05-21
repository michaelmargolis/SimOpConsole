import serial, json, logging, time 
from enum import IntEnum
import traceback

class SwitchIndex(IntEnum):
    FLY        = 0
    PAUSE      = 1
    ACTIVATE   = 2
    ASSIST     = 3
    FLIGHT_MODE= 4
    LOAD       = 5
    INTENSITY  = 6

# ---------- key map used in the Arduino sketch ----------
KEY_TO_INDEX = {
    "fly":        SwitchIndex.FLY,
    "pause":      SwitchIndex.PAUSE,
    "activate":   SwitchIndex.ACTIVATE,
    "assist":     SwitchIndex.ASSIST,
    "mode":       SwitchIndex.FLIGHT_MODE,
    "load":       SwitchIndex.LOAD,
    "intensity":  SwitchIndex.INTENSITY,
}

class SerialSwitchReader:
    def __init__(self, evt_callbacks, status_callback=None):
        self.evt_callbacks   = evt_callbacks
        self.num_switches    = len(evt_callbacks)
        self.status_callback = status_callback
        self.serial_port     = None
        self.port            = None
        self.last_known_state= [None] * self.num_switches
        self.discard_counter = 0

    # ---------- identical begin() ----------
    def begin(self, port, baud_rate=115200):
        self.port = port
        try:
            self.serial_port = serial.Serial(
                port     = port,
                baudrate = baud_rate,
                parity   = serial.PARITY_NONE,
                stopbits = serial.STOPBITS_ONE,
                bytesize = serial.EIGHTBITS,
                timeout  = .01        # non blocking
            )
            return True
        except serial.SerialException as e:
            self._log_status(f"{self.port}: Failed to open serial port: {e}", True)
            return False

    # ---------- poll() tweaked for newline terminated JSON ----------
    def poll(self):
        if not self.serial_port or not self.serial_port.is_open:
            return
        try:
            while self.serial_port.in_waiting:
                line = self.serial_port.readline().decode('utf-8', errors='ignore').strip()
                if line:
                    self._process_json_line(line)
        except Exception as e:
            self._log_status(f"{self.port}: Error while reading serial data: {e}", True)
            print(traceback.format_exc())
            

    # ---------- NEW: parse JSON full & delta objects ----------
    def _process_json_line(self, line: str):
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            self.discard_counter += 1
            if self.discard_counter > 3:
                self._log_status(f"{self.port}: Malformed JSON: '{line}'")
            return

        self.discard_counter = 0

        # obj can be full state (7 keys) or delta (1‑6 keys)
        for key, val in obj.items():
            if key not in KEY_TO_INDEX:
                self._log_status(f"{self.port}: Unknown key '{key}' in msg", True)
                continue
            idx = KEY_TO_INDEX[key]
            if self.last_known_state[idx] is None or self.last_known_state[idx] != val:
                self.evt_callbacks[idx](val)
                self.last_known_state[idx] = val

    # ---------- unchanged helpers ----------
    def _log_status(self, msg, error=False):
        if self.status_callback:
            self.status_callback(msg)
        logging.error(msg) if error else logging.warning(msg)

    def close(self):
        if self.serial_port:
            self.serial_port.close()
            self.serial_port = None


# ------------------- test harness (unchanged) -------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    def create_callback(index):
        def cb(state):
            print(f"{SwitchIndex(index).name}: {state}")
        return cb

    callbacks = [create_callback(i) for i in range(len(SwitchIndex))]
    reader    = SerialSwitchReader(callbacks)

    if reader.begin("COM11"):                          # <-- set your port
        print("Serial port opened successfully.")
        try:
            while True:
                reader.poll()
                time.sleep(0.05)
        except KeyboardInterrupt:
            print("Shutting down.")
            reader.close()
