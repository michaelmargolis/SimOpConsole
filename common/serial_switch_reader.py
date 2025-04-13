import serial
import logging
import time  # temp for debug
from enum import IntEnum

class SwitchIndex(IntEnum):
    FLY = 0
    PAUSE = 1
    ACTIVATE = 2
    ASSIST = 3
    FLIGHT_MODE = 4
    LOAD = 5
    INTENSITY = 6

class SerialSwitchReader:
    def __init__(self, evt_callbacks, status_callback=None):
        self.evt_callbacks = evt_callbacks
        self.num_switches = len(evt_callbacks)
        self.status_callback = status_callback
        self.serial_port = None
        self.port = None
        self.last_known_state = [None] * self.num_switches
        self.buffer = ""
        self.discard_counter = 0

    def begin(self, port, baud_rate=115200):
        self.port = port
        try:
            self.serial_port = serial.Serial(
                port=port,
                baudrate=baud_rate,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS,
                timeout=0  # Non-blocking mode for polling
            )
            return True
        except serial.SerialException as e:
            self._log_status(f"{self.port}: Failed to open serial port: {e}", error=True)
            return False

    def poll(self):
        if not self.serial_port or not self.serial_port.is_open:
            return

        try:
            while self.serial_port.in_waiting:
                char = self.serial_port.read().decode('utf-8', errors='ignore')
                if char == '<':
                    line = self.serial_port.readline().decode('utf-8', errors='ignore').strip()
                    self._process_line(line)
        except Exception as e:
            self._log_status(f"{self.port}: Error while reading serial data: {e}", error=True)

            
    def _process_line(self, line):
        if not line:
            return

        fields = line.split(',')

        if fields[0] != 'Switches':
            self.discard_counter += 1
            if self.discard_counter > 3:
                self._log_status(f"{self.port}: Invalid header in message: '{line}'")
            return

        try:
            expected_count = int(fields[-1])
            if len(fields) != expected_count:
                raise ValueError(f"Field count mismatch. Got {len(fields)}, expected {expected_count}")
        except Exception as e:
            self.discard_counter += 1
            if self.discard_counter > 3:
                self._log_status(f"{self.port}: Malformed message: '{line}' ({e})")
            return

        self.discard_counter = 0

        try:
            switch_values = list(map(int, fields[1:1 + self.num_switches]))
            for i in range(self.num_switches):
                if self.last_known_state[i] is None or self.last_known_state[i] != switch_values[i]:
                    self.evt_callbacks[i](switch_values[i])
                    self.last_known_state[i] = switch_values[i]
        except Exception as e:
            self._log_status(f"{self.port}: Failed to parse switch values: {e}", error=True)

    def _log_status(self, message, error=False):
        if self.status_callback:
            self.status_callback(message)
        if error:
            logging.error(message)
        else:
            logging.warning(message)

    def close(self):
        if self.serial_port:
            self.serial_port.close()
            self.serial_port = None



if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    def create_callback(index):
        def callback(state):
            print(f"{SwitchIndex(index).name}: {state}")
        return callback

    # Initialize SerialSwitchReader with 7 callbacks
    callbacks = [create_callback(i) for i in range(len(SwitchIndex))]
    reader = SerialSwitchReader(callbacks)

    if reader.begin("COM11"):  # Replace with actual port
        print("Serial port opened successfully.")

        try:
            while True:
                reader.poll()
                time.sleep(0.05)
        except KeyboardInterrupt:
            print("Shutting down.")
            reader.close()
