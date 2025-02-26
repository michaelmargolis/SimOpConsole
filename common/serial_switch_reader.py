import serial
import logging
import time # temp for debug

class SerialSwitchReader:
    def __init__(self, evt_callbacks, status_callback=None):
        """
        Initializes the SerialSwitchReader in polled mode.
        
        :param evt_callbacks: List of callback functions for switch values.
        :param status_callback: Optional callback for status updates or errors.
        """
        self.evt_callbacks = evt_callbacks
        self.num_switches = len(evt_callbacks)
        self.status_callback = status_callback
        self.serial_port = None
        self.port = None  # Store the port name for logging
        self.last_known_state = [None] * self.num_switches  # State caching
        self.buffer = "" # store incoming serial data

    def begin(self, port, baud_rate=115200):
        """
        Opens the serial port in non-blocking mode.
        
        :param port: Serial port string (e.g., "/dev/ttyUSB0").
        :param baud_rate: Baud rate for the serial connection.
        :return: True if successful, False otherwise.
        """
        self.port = port  
        try:
            self.serial_port = serial.Serial(
                port=port,
                baudrate=baud_rate,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS,
                timeout=0,  # ⬅ Non-blocking mode for polling
            )
            return True
        except serial.SerialException as e:
            self._log_status(f"{self.port}: Failed to open serial port: {e}", error=True)
            return False

    def poll(self):
        """
        Reads and processes all available serial messages without blocking.
        Call this method in the UI's 50ms polling loop.
        """
        if not self.serial_port or not self.serial_port.is_open:
            return

        try:
            # Read all available bytes (or 1 byte if none are available)
            new_data = self.serial_port.read(self.serial_port.in_waiting or 1).decode('utf-8', errors='ignore')

            if new_data:
                self.buffer += new_data  # Append to buffer
                lines = self.buffer.split("\n")  # Split buffer into lines
                self.buffer = lines[-1]  # Keep the last partial line for next read

                for line in lines[:-1]:  # Process only full lines
                    self._process_line(line.strip())

        except Exception as e:
            self._log_status(f"{self.port}: Error while reading serial data: {e}", error=True)

    def _process_line(self, line):
        """
        Processes a single line of serial data.
        """
        if not line:
            return

        parts = line.split(',')

        if len(parts) < 3:
            self._log_status(f"{self.port}: Ignoring malformed line: {line}")
            return

        header, change_flag, *switch_values = parts

        if header != "Switches":
            self._log_status(f"{self.port}: Ignoring unknown header: {header}")
            return

        if change_flag not in ('0', '1'):
            self._log_status(f"{self.port}: Ignoring invalid change flag: {line}")
            return

        if len(switch_values) != self.num_switches:
            self._log_status(f"{self.port}: Ignoring mismatched switch count: {line}")
            return

        # Convert switch values to integers
        switch_values = [int(value) for value in switch_values]

        # Compare with cached state and update only if changed
        for i in range(self.num_switches):
            if self.last_known_state[i] is None or self.last_known_state[i] != switch_values[i]:
                self.evt_callbacks[i](switch_values[i])  # Invoke UI event handlers
                self.last_known_state[i] = switch_values[i]  # Update cache

    def _log_status(self, message, error=False):
        """
        Logs messages to the console and optionally calls the status callback.
        """
        if self.status_callback:
            self.status_callback(message)
        if error:
            logging.error(message)
        else:
            logging.warning(message)

    def close(self):
        """
        Closes the serial port.
        """
        if self.serial_port:
            self.serial_port.close()
            self.serial_port = None



if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    def switch_callback_1(state):
        print(f"Switch 1: {state}")

    def switch_callback_2(state):
        print(f"Switch 2: {state}")

    def switch_callback_3(state):
        print(f"Switch 3: {state}")

    def switch_callback_4(state):
        print(f"Switch 4: {state}")

    def switch_callback_5(state):
        print(f"Switch 5: {state}")

    def switch_callback_6(state):
        print(f"Switch 6: {state}")

    def switch_callback_7(state):
        print(f"Switch 7: {state}")
    
    # Initialize SerialSwitchReader with 7 callbacks
    reader = SerialSwitchReader([
        switch_callback_1,
        switch_callback_2,
        switch_callback_3,
        switch_callback_4,
        switch_callback_5,
        switch_callback_6,
        switch_callback_7
    ])
    
    if reader.begin("COM5"): # "/dev/ttyUSB0"):
        print("Serial port opened successfully.")
        
        try:
            while True:
                time.sleep(1)  # Keep main thread alive
        except KeyboardInterrupt:
            print("Shutting down.")
            reader.fin()
           

