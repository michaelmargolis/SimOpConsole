import sys, os
import numpy as np
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout
from PyQt5.QtCore import QTimer
import pyqtgraph as pg

from pyqtgraph import InfiniteLine
from PyQt5.QtCore import Qt

# Adjust to match your module path and UDP class location
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from common.udp_tx_rx import UdpReceive

# Constants
NUM_AXES = 6
AXES = ['X', 'Y', 'Z', 'Roll', 'Pitch', 'Yaw']
MAX_PIXELS = 2048
PORT = 10020  # Your specified UDP port

class WashoutScope(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Washout Trace Viewer             Red is input, Blue output")
        self.setGeometry(100, 100, 1200, 800)

        self.plot_data_in = [[] for _ in range(NUM_AXES)]
        self.plot_data_out = [[] for _ in range(NUM_AXES)]
        self.x_vals = np.arange(MAX_PIXELS)

        self.udp = UdpReceive(PORT)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout()
        central.setLayout(layout)

        self.plots = []
        self.curves_in = []
        self.curves_out = []

        for axis in range(NUM_AXES):
            pw = pg.PlotWidget()
            pw.setYRange(-1.5, 1.5, padding=0)
            pw.setXRange(0, MAX_PIXELS, padding=0)
            pw.setLabel('left', AXES[axis])
            pw.setMouseEnabled(x=False, y=False)
            pw.setMenuEnabled(False)
            pw.hideButtons()
            pw.setBackground('w')
            pw.plotItem.showGrid(x=True, y=True)
            pw.getAxis('bottom').setStyle(showValues=False)
            
            zero_line = InfiniteLine(pos=0, angle=0, pen=pg.mkPen('k', width=1, style=Qt.DashLine))
            pw.addItem(zero_line)

            layout.addWidget(pw)

            curve_in = pw.plot(pen=None, symbol='o', symbolPen='r', symbolBrush='r', symbolSize=3)
            curve_out = pw.plot(pen=None, symbol='o', symbolPen='b', symbolBrush='b', symbolSize=3)
            self.curves_in.append(curve_in)
            self.curves_out.append(curve_out)
        
            self.plots.append(pw)

        self.timer = QTimer()
        self.timer.timeout.connect(self.check_udp)
        self.timer.start(5)  # Fast poll for UDP packets
        


    def check_udp(self):
        while self.udp.available():
            addr, msg = self.udp.get()
            self.process_message(msg)

    def process_message(self, msg):
        try:
            parts = msg.strip().split('|')
            input_vals, output_vals = [], []

            for part in parts:
                if part.startswith("pre_washed"):
                    input_vals = [float(x) for x in part.split(",")[1:]]
                elif part.startswith("norm_xform"):
                    output_vals = [float(x) for x in part.split(",")[1:]]

            if len(input_vals) == NUM_AXES and len(output_vals) == NUM_AXES:
                for i in range(NUM_AXES):
                    self.plot_data_in[i].append(input_vals[i])
                    self.plot_data_out[i].append(output_vals[i])

                    # Keep max size
                    if len(self.plot_data_in[i]) > MAX_PIXELS:
                        self.plot_data_in[i].pop(0)
                        self.plot_data_out[i].pop(0)

                    n = len(self.plot_data_in[i])
                    x_range = self.x_vals[:n]
                    self.curves_in[i].setData(x_range, self.plot_data_in[i])
                    self.curves_out[i].setData(x_range, self.plot_data_out[i])
                    # print(f"in={input_vals[i]}, out={output_vals[i]}")

        except Exception as e:
            print(f"[Error parsing message]: {msg}\n{e}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    win = WashoutScope()
    win.show()
    sys.exit(app.exec_())
