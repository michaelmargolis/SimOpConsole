import sys, os
import numpy as np
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout
from PyQt5.QtCore import Qt
import pyqtgraph as pg
from pyqtgraph import InfiniteLine


NUM_AXES = 6
AXES = ['X', 'Y', 'Z', 'Roll', 'Pitch', 'Yaw']
MAX_PIXELS = 2048
PORT = 10020

class WashoutScope:
    def __init__(self, parent_widget):
        self.plot_data_in = [[] for _ in range(NUM_AXES)]
        self.plot_data_out = [[] for _ in range(NUM_AXES)]
        self.x_vals = np.arange(MAX_PIXELS)

        self.plots = []
        self.curves_in = []
        self.curves_out = []

        layout = QVBoxLayout()
        parent_widget.setLayout(layout)  # Set the layout of the passed-in widget

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


    def update(self, pre_washed, post_washed):

        if len(pre_washed) != NUM_AXES or len(post_washed) != NUM_AXES:
            print("[Warning] Tuple length mismatch")
            return

        # print(f"pre: {pre_washed}, post: {post_washed}")

        for i in range(NUM_AXES):
            try:
                in_val = float(pre_washed[i])
                out_val = float(post_washed[i])
                # print(f"Axis {i} -> in: {in_val}, out: {out_val}")

                self.plot_data_in[i].append(in_val)
                self.plot_data_out[i].append(out_val)

                if len(self.plot_data_in[i]) > MAX_PIXELS:
                    self.plot_data_in[i].pop(0)
                    self.plot_data_out[i].pop(0)

                n = len(self.plot_data_in[i])
                x_range = np.arange(n)
                y_in = np.array(self.plot_data_in[i], dtype=np.float64)
                y_out = np.array(self.plot_data_out[i], dtype=np.float64)

                self.curves_in[i].setData(x_range, y_in)
                self.curves_out[i].setData(x_range, y_out)

                # print(f"Axis {i}: {n} points")

            except Exception as e:
                # print(f"[Update Error] Axis {i}: pre={pre_washed[i]}, post={post_washed[i]} -- {e}")
                pass

def test_update(scope):
    import sys
    from PyQt5.QtWidgets import QApplication

    print("\n[Debug Mode] Enter 6 comma-separated values (floats) for pre_washed input.")
    print("post_washed will be calculated as the negative of pre_washed.")
    print("Type 'exit' to stop.\n")

    while True:
        try:
            line = input("Enter 6 comma-separated values: ").strip()
            if line.lower() == 'exit':
                break

            values = [float(v.strip()) for v in line.split(",")]
            if len(values) != NUM_AXES:
                print(f"Please enter exactly {NUM_AXES} values.")
                continue

            pre_washed = tuple(values)
            post_washed = tuple(-v for v in pre_washed)

            print(f"pre: {pre_washed}")
            print(f"post: {post_washed}")

            scope.update(pre_washed, post_washed)
            QApplication.processEvents()  # 🧠 refresh the UI

        except ValueError as ve:
            print(f"[Error] Invalid input: {ve}")
        except KeyboardInterrupt:
            print("\n[Interrupted]")
            sys.exit(0)



def parse_message(msg):
    """Parses a UDP message and returns pre_washed and post_washed tuples."""
    try:
        parts = msg.strip().split('|')
        input_vals, output_vals = [], []

        for part in parts:
            if part.startswith("pre_washed"):
                input_vals = [float(x) for x in part.split(",")[1:]]
            elif part.startswith("norm_xform"):
                output_vals = [float(x) for x in part.split(",")[1:]]

        if len(input_vals) == NUM_AXES and len(output_vals) == NUM_AXES:
            return tuple(input_vals), tuple(output_vals)
    except Exception as e:
        print(f"[Error parsing message]: {msg}\n{e}")
    return None, None


CONSOLE_INPUT = False

if __name__ == '__main__':
    from PyQt5.QtCore import QTimer
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from common.udp_tx_rx import UdpReceive  # Adjust path if needed

    app = QApplication(sys.argv)
 
    main_window = QMainWindow()
    main_window.setWindowTitle("Washout Trace Viewer             Red is input, Blue output")
    main_window.setGeometry(100, 100, 1200, 800)

    central_widget = QWidget()
    main_window.setCentralWidget(central_widget)

    scope = WashoutScope(central_widget)  # Pass the widget, not a layout
    
    if CONSOLE_INPUT:
        main_window.show()
        test_update(scope)
    else:   
        print(f"Expecting UDP packest on port {PORT})")
        udp = UdpReceive(PORT)
        def poll_udp():
            while udp.available():
                addr, msg = udp.get()
                # print(msg)
                pre, post = parse_message(msg)
                if pre and post:
                    scope.update(pre, post)

        timer = QTimer()
        timer.timeout.connect(poll_udp)
        timer.start(5)
        main_window.show()
        
    sys.exit(app.exec_())
