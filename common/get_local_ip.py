import socket

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))  # Google's DNS - does not require actual internet access
        ip = s.getsockname()[0]
    finally:
        s.close()
    return ip

if __name__ == '__main__':
    print(f"Local IP: {get_local_ip()}")