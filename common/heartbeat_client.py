# heartbeat_client.py

import time
import logging
from common.udp_tx_rx import UdpReceive

class HeartbeatClient:
    def __init__(self, heartbeat_addr, target_app, interval=1.0):
        self.heartbeat_addr = heartbeat_addr
        self.target_app = target_app
        self.interval = interval
        self.last_ping_time = 0
        self.last_recv_time = None
        self._ok = False
        self._running = False
        rx_port = heartbeat_addr[1] + 1
        self.sock = UdpReceive(rx_port)

    def send_ping(self):
        try:
            self.sock.send("ping", self.heartbeat_addr)
            self.last_ping_time = time.time()
        except Exception as e:
            logging.warning(f"[HeartbeatClient] Ping to {self.heartbeat_addr} failed: {e}")

    def query_status(self, now):
        try:
            # Check for new messages
            while self.sock.available():
                addr, message = self.sock.get()
                self._ok = True
                self._running = self.target_app in message
                self.last_recv_time = now

            # Send ping if needed
            if now - self.last_ping_time > self.interval:
                self.send_ping()

            # Timeout if no message received after double the interval time
            if self.last_recv_time is None or (now - self.last_recv_time > self.interval * 2):
                self._ok = False
                self._running = False

        except Exception as e:
            logging.warning(f"[HeartbeatClient] Query failed: {e}")
            self._ok = False
            self._running = False
        # print(f"heartbeat debug: ok {self._ok}, running {self._running}")  
        return self._ok, self._running
