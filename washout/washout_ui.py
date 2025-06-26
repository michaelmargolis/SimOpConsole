import configparser
import os
from PyQt5.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout, QRadioButton, QLabel,
    QDoubleSpinBox, QPushButton, QButtonGroup, QWidget, QFormLayout,
    QCheckBox, QHBoxLayout, QSizePolicy
)

class WashoutUI:
    def __init__(self, groupbox: QGroupBox, config_path='washout.cfg', on_activate=None):
        self.groupbox = groupbox
        self.config_path = config_path
        self.on_activate = on_activate
        self.config = configparser.ConfigParser()
        self.washout_types = {}
        self.active_type = None
        self.type_buttons = QButtonGroup()
        self.axis_widgets = {}
        self.global_widgets = {}
        self.description_label = QLabel()

        self._read_config()
        self._create_ui()
        self._activate_values()

    def _read_config(self):
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Config file not found: {self.config_path}")

        self.config.read(self.config_path)
        self.active_type = self.config.get('Active', 'type')

        for section in self.config.sections():
            if section in ('Active',):
                continue
            self.washout_types[section] = {
                'name': self.config.get(section, 'name', fallback=section),
                'tooltip': self.config.get(section, 'tooltip', fallback=''),
                'params': [],
                'enabled': {},
                'tooltips': {}
            }
            for key, value in self.config.items(section):
                if key in ('name', 'tooltip'):
                    continue
                if key.startswith("enabled_"):
                    axis = key[len("enabled_"):]  # e.g. enabled_x => x
                    self.washout_types[section]['enabled'][axis] = value.strip() == '1'
                elif '|' in value:
                    val, tip = value.split('|', 1)
                    val_clean = float(val.strip())
                    tip_clean = tip.strip()
                    self.washout_types[section]['params'].append((key, val_clean, tip_clean))
                    self.washout_types[section]['tooltips'][key] = tip_clean

    def _create_ui(self):
        layout = QVBoxLayout()

        # Washout type radio buttons
        for idx, (section, data) in enumerate(self.washout_types.items()):
            btn = QRadioButton(data['name'])
            btn.setToolTip(data['tooltip'])
            if section == self.active_type:
                btn.setChecked(True)
            self.type_buttons.addButton(btn)
            self.type_buttons.setId(btn, idx)
            layout.addWidget(btn)

        # Dynamic parameter area
        self.params_container = QWidget()
        self.params_layout = QFormLayout()
        self.params_container.setLayout(self.params_layout)
        layout.addWidget(self.description_label)
        layout.addWidget(self.params_container)

        self._populate_parameters_ui(self.active_type)

        # Buttons
        btn_layout = QHBoxLayout()
        self.activate_button = QPushButton("Activate Values")
        self.save_button = QPushButton("Save as Default")
        self.activate_button.clicked.connect(self._activate_values)
        self.save_button.clicked.connect(self._save_to_file)
        btn_layout.addWidget(self.activate_button)
        btn_layout.addWidget(self.save_button)
        layout.addLayout(btn_layout)

        self.groupbox.setLayout(layout)
        self.type_buttons.buttonClicked.connect(self._on_type_changed)

    def _populate_parameters_ui(self, washout_type):
        while self.params_layout.count():
            item = self.params_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.axis_widgets.clear()
        self.global_widgets.clear()

        if washout_type not in self.washout_types:
            return

        tooltip_text = self.washout_types[washout_type]['tooltip']
        self.description_label.setText(tooltip_text if washout_type.lower() != 'disabled' else '')

        for key, value, tooltip in self.washout_types[washout_type]['params']:
            spin = QDoubleSpinBox()
            spin.setRange(-1000, 1000)
            spin.setDecimals(4)
            spin.setFixedWidth(100)
            spin.setFixedHeight(24)
            spin.setValue(value)
            spin.setToolTip(self.washout_types[washout_type].get('tooltips', {}).get(key, ''))

            hbox = QHBoxLayout()

            checkbox = QCheckBox()
            checkbox.setToolTip("Enable washout for this axis")
            checkbox.setFixedWidth(20)
            checkbox.setFixedHeight(22)
            checkbox.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

            axis = key.split('_')[-1]
            enabled = self.washout_types[washout_type]['enabled'].get(axis, True)
            checkbox.setChecked(enabled)

            tooltip_label = QLabel(tooltip)
            tooltip_label.setMinimumHeight(24)
            tooltip_label.setWordWrap(True)

            hbox.addWidget(checkbox)
            hbox.addWidget(spin)
            hbox.addWidget(tooltip_label)
            hbox.setStretch(0, 0)
            hbox.setStretch(1, 0)
            hbox.setStretch(2, 1)

            row_widget = QWidget()
            row_widget.setLayout(hbox)

            self.params_layout.addRow(QLabel(key), row_widget)

            if axis in ['x', 'y', 'z', 'roll', 'pitch', 'yaw']:
                self.axis_widgets[key] = (checkbox, spin)
            else:
                self.global_widgets[key] = spin

    def _on_type_changed(self):
        selected_index = self.type_buttons.checkedId()
        selected_section = list(self.washout_types.keys())[selected_index]
        self.active_type = selected_section
        self._populate_parameters_ui(selected_section)

    def _activate_values(self):
        if self.on_activate:
            config_data = {
                "type": self.active_type,
                "axis_params": self._structured_axis_params(),
                "global_params": {k: w.value() for k, w in self.global_widgets.items()}
            }
            self.on_activate(config_data)
        else:
            print("[INFO] No activation callback set")

    def _structured_axis_params(self):
        axis_map = {}
        for k, (checkbox, widget) in self.axis_widgets.items():
            if not checkbox.isChecked():
                continue
            for axis in ['x', 'y', 'z', 'roll', 'pitch', 'yaw']:
                if k.endswith(f"_{axis}"):
                    param_name = k[:-len(f"_{axis}")]
                    axis_entry = axis_map.setdefault(axis, {})
                    axis_entry[param_name] = widget.value()
        return axis_map

    def _save_to_file(self):
        section = self.active_type
        if section not in self.washout_types:
            return

        self.config['Active'] = {'type': section}
        self.config[section] = {
            'name': self.washout_types[section]['name'],
            'tooltip': self.washout_types[section]['tooltip']
        }

        for key, (checkbox, spinbox) in self.axis_widgets.items():
            axis = key.split('_')[-1]
            self.config[section][key] = f"{spinbox.value():.4f} | {spinbox.toolTip()}"
            self.config[section][f"enabled_{axis}"] = '1' if checkbox.isChecked() else '0'

        for key, spinbox in self.global_widgets.items():
            self.config[section][key] = f"{spinbox.value():.4f} | {spinbox.toolTip()}"

        with open(self.config_path, 'w') as f:
            self.config.write(f)

# Example integration in siminterface.py:
# self.washout_ui = WashoutUI(self.grp_washout, config_path="washout.cfg", on_activate=self.apply_washout_configuration)
