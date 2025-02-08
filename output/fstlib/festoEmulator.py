import sys
import socket
import logging
import traceback
import time

import easyip
from festo_emulator_gui_defs import *

sys.path.insert(0, '../../common')
from streaming_moving_average import StreamingMovingAverage as MA

log = logging.getLogger(__name__)

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, app):
        QtWidgets.QMainWindow.__init__(self)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.app = app
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # UDP
        self.sock.settimeout(1)
        self.sock.bind(('', easyip.EASYIP_PORT))
        host_name = socket.gethostname() 
        host_ip = socket.gethostbyname(host_name) 
        self.init_gui()
        self.prev_message_time = 0
        self.timeout_start_time = None
        self.ma = MA(10)
        self.requested_pressures = [0,0,0,0,0,0]
        log.info("Festo emulator running on %s", host_ip)

    def init_gui(self):
        self.pressure_bars = [self.ui.muscle_0,self.ui.muscle_1,self.ui.muscle_2,self.ui.muscle_3,self.ui.muscle_4,self.ui.muscle_5]
        self.txt_muscles = [self.ui.txt_muscle_0,self.ui.txt_muscle_1,self.ui.txt_muscle_2,self.ui.txt_muscle_3,self.ui.txt_muscle_4,self.ui.txt_muscle_5]
        for t in self.txt_muscles:
             t.setText('?')

    def show_pressures(self, pressures):
        if pressures == 0:
           self.show_timeout()
        else:
            try:
                self.display_pressure_bars(pressures)
                self.requested_pressures = pressures
            except TypeError as e:
                print(pressures, e)

    def show_timeout(self):
        self.ui.lbl_connection.setText("Idle")
        log.debug("Festo emulator idle")

    def display_pressure_bars(self, pressures):
        for idx, p in enumerate(pressures):
            self.txt_muscles[idx].setText(str(p))
            rect =  self.pressure_bars[idx].rect()
            width = pressures[idx] /20
            if width <= 0: width = 1
            rect.setWidth(width)
            self.pressure_bars[idx].setFrameRect(rect)

    def get_emulated_pressures(self):
        ep = []
        for d in self.requested_pressures:
            ep.append(max(d+random.randint(-100,100), 0))
            return em

    def receive(self):
        while True:
            try:
                data, addr = self.sock.recvfrom(1024) # buffer size is 1024 bytes
                log.debug("received msg from %s", addr)
                t = time.time()
                packet = easyip.Packet(data)
                if packet.reqdata_type == easyip.Operands.FLAG_WORD:
                     print("get pressure request")
                     emulated_pressure = self.get_emulated_pressures()
                     packet = easyip.Factory.send_flagword(0, emulated_pressure)
                     self.send_response(packet, addr)
                else:
                    print("set pressure")
                    values = packet.decode_payload(easyip.Packet.DIRECTION_SEND)
                    print "in emulator", packet, "values=", values
                    self.show_pressures(values)
                self.ui.lbl_connection.setText("Connected to " + addr[0])
                if self.prev_message_time:
                    avg = int(round(self.ma.next((t - self.prev_message_time) *1000)))
                    self.ui.lbl_interval.setText(format("%d" % avg))
                self.send_response(packet, addr)
                self.prev_message_time = t
                self.app.processEvents()
            except socket.timeout:
                log.debug("festo emulator timeout")
                self.show_timeout()
                if self.prev_message_time:
                    self.ui.lbl_interval.setText(format("%d" % (t - self.prev_message_time) *1000))
                self.app.processEvents()
                continue
            except Exception as e:
                log.error("festo emulator recv err: %s,%s", e, traceback.format_exc())

    def send_response(self, in_packet, addr):
         packet = easyip.Factory.response(in_packet,0) # send no error
         data = packet.pack()
         self.sock.sendto(data, addr)


def main():
    log.info("starting festo emulator")
    app = QtWidgets.QApplication(sys.argv)
    win = MainWindow(app)
    win.show()
    win.receive()
    app.exec_() #mm added underscore

    log.info("Finishing PlatformTest\n")
    win.close()
    app.exit()
    sys.exit()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)-8s %(message)s',
                        datefmt='%H:%M:%S')
    main()
