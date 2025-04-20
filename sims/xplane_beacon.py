import struct
import logging
import time
try:
    from common.udp_tx_rx import UdpReceive
except: 
    # only needed if running main test harness
    import sys, os
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from common.udp_tx_rx import UdpReceive

DEFAULT_BEACON_PORT = 49707  # standard for X-Plane beacon

class XplaneBeacon:
    def __init__(self, port=DEFAULT_BEACON_PORT):
        self.beacon = UdpReceive(port)

    def get_message(self):
        """
        Parse and return a dictionary representing a beacon message, or None if no message available.
        """
        if self.beacon.available():
            try:
                addr, message = self.beacon.get()

                if not message.startswith('BECN\0'):
                    logging.warning("Beacon message with incorrect prologue")
                    return None

                raw = message[5:21]  # next 16 bytes
                unpacked = struct.unpack('<BBiiIH', raw)

                return {
                    'beacon_major_version': unpacked[0],
                    'beacon_minor_version': unpacked[1],
                    'application_host_id': unpacked[2],
                    'version_number': unpacked[3],
                    'role': unpacked[4],
                    'port': unpacked[5],
                    'ip': addr[0]
                }

            except Exception as e:
                logging.warning(f"Failed to parse beacon: {e}")
        return None

    def send(self, message: str, addr: tuple):
        """
        Send a plain text message to the given (ip, port) address.
        """
        try:
            self.beacon.send(message, addr)
        except Exception as e:
            logging.warning(f"Failed to send beacon message to {addr}: {e}")


    def send_bytes(self, message: str, addr: tuple):
        """
        Send a plain text message to the given (ip, port) address.
        """
        try:
            self.beacon.send_bytes(message, addr)
        except Exception as e:
            logging.warning(f"Failed to send beacon bytes message to {addr}: {e}")

    def close():
        self.beacon.close()
        
if __name__ == "__main__":    
    logging.basicConfig(level=logging.INFO)
    beacon = XplaneBeacon()
    print("Listening for X-Plane beacon messages...")

    try:
        while True:
            msg = beacon.get_message()
            if msg:
                print("Beacon received:", msg)
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("Beacon test interrupted.")
