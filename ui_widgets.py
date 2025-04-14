import sys
import re
from PyQt5 import QtWidgets, QtCore, QtGui


class ButtonGroupHelper:
    def __init__(self, parent, buttons_with_ids, callback):
        self.group = QtWidgets.QButtonGroup(parent)
        for button, id_ in buttons_with_ids:
            self.group.addButton(button, id_)
        self.group.buttonClicked[int].connect(callback)

    def checked_id(self):
        return self.group.checkedId()

    def set_checked(self, id_):
        button = self.group.button(id_)
        if button:
            button.setChecked(True)
            
class ActivationButton(QtWidgets.QPushButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._activation_percent = 0
        self._background_color = QtCore.Qt.lightGray
        self._fill_color = QtCore.Qt.green
        
        self._border_radius = 15
        self.setCheckable(True)
        self.parse_stylesheet()

    def set_activation_percent(self, percent: int):
        self._activation_percent = max(0, min(100, percent))
        self.update()

    def parse_stylesheet(self):
        ss = self.styleSheet()
        bg_match = re.search(r'background-color:\s*(.*?);', ss)
        fill_match = re.search(r'color:\s*(.*?);', ss)

        if bg_match:
            self._background_color = QtGui.QColor(bg_match.group(1).strip())
        if fill_match:
            self._fill_color = QtGui.QColor(fill_match.group(1).strip())

    def paintEvent(self, event):
        super().paintEvent(event)  # Qt paints base button visuals (label, border)

        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        rect = self.rect()
        radius = self._border_radius

        # Clip fill to rounded area
        path = QtGui.QPainterPath()
        path.addRoundedRect(QtCore.QRectF(rect), radius, radius)
        painter.setClipPath(path)

        # Draw gray background over default fill
        painter.setBrush(QtGui.QBrush(self._background_color))
        painter.setPen(QtCore.Qt.NoPen)
        painter.drawRoundedRect(QtCore.QRectF(rect), radius, radius)

        # Draw green activation bar from bottom up
        if self._activation_percent > 0:
            bar_height = int((self._activation_percent / 100.0) * rect.height())
            fill_rect = QtCore.QRect(
                rect.x(),
                rect.bottom() - bar_height + 1,
                rect.width(),
                bar_height
            )
            painter.setBrush(QtGui.QBrush(self._fill_color))
            painter.drawRect(fill_rect)

        # draw label manually over everything
        painter.setPen(QtCore.Qt.black if self._activation_percent >= 50 else QtCore.Qt.red)
        painter.setFont(self.font())
        painter.drawText(rect, QtCore.Qt.AlignCenter, self.text())


# ------------------------------------------------------------------------------
# Test Harness
# ------------------------------------------------------------------------------

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)

    window = QtWidgets.QMainWindow()
    window.setWindowTitle("ActivationButton Test")
    window.resize(300, 200)

    # Create and style the button
    btn = ActivationButton(window)
    btn.setGeometry(80, 50, 140, 60)
    btn.setText("INACTIVE")
    btn.setStyleSheet("background-color: gray; color: green; border-radius: 15px;")

    window.show()

    # Respond to toggle by changing text and animating percent
    def handle_toggled(state):
        btn.setText("ACTIVATED" if state else "INACTIVE")
        print("Activated" if state else "Deactivated")
        stepper.start_animation(1 if state else -1)

    btn.toggled.connect(handle_toggled)

    class ActivationStepper(QtCore.QObject):
        def __init__(self, button: ActivationButton):
            super().__init__()
            self.button = button
            self.percent = 0
            self.direction = 1
            self.timer = QtCore.QTimer(self)
            self.timer.timeout.connect(self.step)

        def start_animation(self, direction: int):
            self.direction = direction
            self.percent = self.button._activation_percent
            self.timer.start(100)

        def step(self):
            self.percent += 10 * self.direction
            self.percent = max(0, min(100, self.percent))
            self.button.set_activation_percent(self.percent)

            if self.percent == 0 or self.percent == 100:
                self.timer.stop()

    stepper = ActivationStepper(btn)

    sys.exit(app.exec_())
