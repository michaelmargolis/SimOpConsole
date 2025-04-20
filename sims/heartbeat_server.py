import socket
import time
from datetime import datetime

import subprocess


HEARTBEAT_PORT = 10030
CHECK_INTERVAL = 5  # seconds to recheck process list


def is_program_running(program_name):
    try:
        # Run the tasklist command to get the list of running processes
        output = subprocess.check_output(['tasklist'], shell=True).decode()
        
        # Check if the program name is in the output
        if program_name.lower() in output.lower():
            return True
        else:
            return False
    except subprocess.CalledProcessError as e:
        print(f"Error checking for program: {e}")
        return False


def get_ipv4_address():
        hostname = socket.gethostname()
        ipv4_address = socket.gethostbyname(hostname)
        return ipv4_address


def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", HEARTBEAT_PORT))
    sock.settimeout(1.0)
    
    print(f"this PCs IPv4 Address: {ipv4_address}")
    print(f"[Heartbeat Server] Listening on UDP port {HEARTBEAT_PORT}...")

    xplane_state = is_program_running("X-Plane")
    last_check = time.time()

    while True:
        try:
            # Refresh state periodically
            if time.time() - last_check > CHECK_INTERVAL:
                xplane_state = is_program_running("X-Plane")
                last_check = time.time()

            data, addr = sock.recvfrom(1024)
            if data.strip().lower() == b'ping':
                timestamp = datetime.now().strftime("%H:%M:%S")
                if xplane_state:
                   reply = f"xplane_running at {timestamp}".encode()
                else:   
                     reply = f"X-Plane not detected at {timestamp}".encode()
                sock.sendto(reply, addr)
                print(f"Replying {reply} to {addr}")
        except socket.timeout:
            continue
        except Exception as e:
            print(f"[ERROR] {e}")

if __name__ == "__main__":
    main()
