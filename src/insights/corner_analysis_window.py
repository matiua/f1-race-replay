import sys

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QLineEdit, QPushButton
)
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt

from src.gui.pit_wall_window import PitWallWindow

_MS_PER_KMH = 1000.0 / 3600.0   # km/h -> m/s
_G = 9.81                       # m/s^2 per g
_CORNER_WINDOW_M = 60.0         # metres either side of the corner apex distance

_COLUMNS = [
    "Driver", "Entry (km/h)", "Min/Apex (km/h)", "Exit (km/h)",
    "Avg (km/h)", "Time in Corner (s)", "Gap to Fastest (s)", "Braking G", "Accel G",
]


class CornerAnalysisWindow(PitWallWindow):
    """
    Pit wall insight that analyses how each driver takes a selected corner:
    entry / minimum (apex) / exit speed, average speed, time spent in the
    corner, braking (deceleration) and acceleration g-force, with a table
    comparing all known drivers side by side.
    """

    def __init__(self):
        self._corners: list[dict] = []          # [{"number", "letter", "distance"}, ...]
        self._corner_labels: dict[int, str] = {}  # corner number -> user-given name, e.g. "Hairpin"
        self._known_drivers: list[str] = []
        # per-driver in-progress lap buffer: {"lap", "start_dist", "samples": [(dist, t, speed_kmh)]}
        self._lap_buffers: dict[str, dict] = {}
        # per-driver, per-corner-number metrics for the most recently completed lap
        self._last_lap_metrics: dict[str, dict[int, dict]] = {}
        # per-driver, per-corner-number metrics for the fastest (best) lap seen so far
        self._best_lap_metrics: dict[str, dict[int, dict]] = {}
        self._lap_mode = "best"   # "best" | "last"
        super().__init__()
        self.setWindowTitle("F1 Race Replay - Corner Analysis")

    # ── UI setup ─────────────────────────────────────────────────────────

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        root_layout = QVBoxLayout(central_widget)
        root_layout.setSpacing(8)
        root_layout.setContentsMargins(10, 10, 10, 10)

        control_row = QHBoxLayout()

        corner_label = QLabel("Corner:")
        corner_label.setFont(QFont("Arial", 11))
        self.corner_combo = QComboBox()
        self.corner_combo.setMinimumWidth(140)
        self.corner_combo.setPlaceholderText("Waiting for circuit data…")
        self.corner_combo.setFont(QFont("Arial", 11))
        self.corner_combo.currentIndexChanged.connect(self._on_corner_selected)

        mode_label = QLabel("Lap:")
        mode_label.setFont(QFont("Arial", 11))
        self.mode_combo = QComboBox()
        self.mode_combo.setFont(QFont("Arial", 11))
        self.mode_combo.addItems(["Best Lap", "Last Completed Lap"])
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)

        control_row.addWidget(corner_label)
        control_row.addWidget(self.corner_combo)
        control_row.addSpacing(20)
        control_row.addWidget(mode_label)
        control_row.addWidget(self.mode_combo)
        control_row.addStretch()
        root_layout.addLayout(control_row)

        # Rename row — label the selected corner (e.g. "Hairpin") so it's easy to find again
        rename_row = QHBoxLayout()
        rename_label = QLabel("Name this corner:")
        rename_label.setFont(QFont("Arial", 11))
        self.rename_input = QLineEdit()
        self.rename_input.setPlaceholderText("e.g. Hairpin")
        self.rename_input.setFont(QFont("Arial", 11))
        self.rename_input.returnPressed.connect(self._on_rename_applied)
        rename_btn = QPushButton("Apply")
        rename_btn.clicked.connect(self._on_rename_applied)

        rename_row.addWidget(rename_label)
        rename_row.addWidget(self.rename_input)
        rename_row.addWidget(rename_btn)
        root_layout.addLayout(rename_row)

        self.table = QTableWidget(0, len(_COLUMNS))
        self.table.setHorizontalHeaderLabels(_COLUMNS)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        root_layout.addWidget(self.table)

        hint = QLabel(
            "Braking G / Accel G are peak longitudinal deceleration and acceleration "
            f"through a ±{_CORNER_WINDOW_M:.0f}m window around the corner apex."
        )
        hint.setFont(QFont("Arial", 9))
        hint.setStyleSheet("color: gray;")
        root_layout.addWidget(hint)

    # ── Corner / mode selectors ───────────────────────────────────────────

    def _on_corner_selected(self, _index: int):
        self._refresh_table()

    def _on_mode_changed(self, index: int):
        self._lap_mode = "best" if index == 0 else "last"
        self._refresh_table()

    def _on_rename_applied(self):
        corner = self._selected_corner()
        name = self.rename_input.text().strip()
        if corner is None or not name:
            return
        self._corner_labels[corner["number"]] = name
        self.rename_input.clear()
        self._repopulate_corner_combo(keep_selection=corner["number"])

    def _corner_display_label(self, corner: dict) -> str:
        custom = self._corner_labels.get(corner["number"])
        base = f"Turn {corner['number']}{corner['letter']} ({corner['distance']:.0f}m)"
        return f"{base} — {custom}" if custom else base

    def _repopulate_corner_combo(self, keep_selection: int | None = None):
        self.corner_combo.blockSignals(True)
        self.corner_combo.clear()
        for corner in self._corners:
            self.corner_combo.addItem(self._corner_display_label(corner), corner["number"])
        self.corner_combo.blockSignals(False)
        if keep_selection is not None:
            idx = next((i for i, c in enumerate(self._corners) if c["number"] == keep_selection), 0)
        else:
            idx = 0
        if self._corners:
            self.corner_combo.setCurrentIndex(idx)
        self._refresh_table()

    def _refresh_corner_list(self, corners: list[dict]):
        if not corners or self._corners:
            return
        self._corners = sorted(corners, key=lambda c: c["distance"])
        self._repopulate_corner_combo()

    def _selected_corner(self) -> dict | None:
        idx = self.corner_combo.currentIndex()
        if idx < 0 or idx >= len(self._corners):
            return None
        return self._corners[idx]

    # ── Buffer management ─────────────────────────────────────────────────

    def _ensure_buffer(self, code: str):
        if code not in self._lap_buffers:
            self._lap_buffers[code] = {"lap": None, "start_dist": 0.0, "samples": []}
        if code not in self._last_lap_metrics:
            self._last_lap_metrics[code] = {}
        if code not in self._best_lap_metrics:
            self._best_lap_metrics[code] = {}

    def _append_sample(self, code: str, driver: dict, session_t: float):
        self._ensure_buffer(code)

        speed = float(driver.get("speed") or 0)
        dist = float(driver.get("dist") or 0)
        lap = driver.get("lap")

        lb = self._lap_buffers[code]
        if lap is not None and lap != lb["lap"]:
            if lb["lap"] is not None and lb["samples"]:
                self._compute_lap_metrics(code, lb["samples"])
            lb["lap"] = lap
            lb["start_dist"] = dist
            lb["samples"] = []

        lap_dist = dist - lb["start_dist"]
        lb["samples"].append((lap_dist, session_t, speed))

    def _compute_lap_metrics(self, code: str, samples: list[tuple[float, float, float]]):
        """Compute per-corner metrics for one just-completed lap and store them."""
        if not self._corners or len(samples) < 3:
            return

        for corner in self._corners:
            apex_dist = corner["distance"]
            window_lo = apex_dist - _CORNER_WINDOW_M
            window_hi = apex_dist + _CORNER_WINDOW_M

            window_samples = [s for s in samples if window_lo <= s[0] <= window_hi]
            if len(window_samples) < 3:
                continue

            entry_dist, entry_t, entry_speed = window_samples[0]
            exit_dist, exit_t, exit_speed = window_samples[-1]

            apex_idx = min(range(len(window_samples)), key=lambda i: window_samples[i][2])
            _, apex_t, min_speed = window_samples[apex_idx]

            avg_speed = sum(s[2] for s in window_samples) / len(window_samples)
            time_in_corner = exit_t - entry_t

            braking_g = self._peak_g(window_samples[:apex_idx + 1])
            accel_g = self._peak_g(window_samples[apex_idx:])

            metrics = {
                "entry_speed": entry_speed,
                "min_speed": min_speed,
                "exit_speed": exit_speed,
                "avg_speed": avg_speed,
                "time_in_corner": time_in_corner,
                "braking_g": braking_g,
                "accel_g": accel_g,
            }

            self._last_lap_metrics[code][corner["number"]] = metrics

            best = self._best_lap_metrics[code].get(corner["number"])
            if best is None or time_in_corner < best["time_in_corner"]:
                self._best_lap_metrics[code][corner["number"]] = metrics

    @staticmethod
    def _peak_g(samples: list[tuple[float, float, float]]) -> float:
        """Largest instantaneous longitudinal acceleration magnitude (in g) between
        consecutive samples. Positive = accelerating, negative = decelerating."""
        peak = 0.0
        for (_, t0, v0), (_, t1, v1) in zip(samples, samples[1:]):
            dt = t1 - t0
            if dt <= 0:
                continue
            dv_ms = (v1 - v0) * _MS_PER_KMH
            accel_g = (dv_ms / dt) / _G
            if abs(accel_g) > abs(peak):
                peak = accel_g
        return peak

    # ── Driver list ────────────────────────────────────────────────────────

    def _refresh_driver_list(self, drivers: dict):
        incoming = sorted(drivers.keys())
        if incoming == self._known_drivers:
            return
        self._known_drivers = incoming

    # ── Table redraw ──────────────────────────────────────────────────────

    def _refresh_table(self):
        corner = self._selected_corner()
        if corner is None:
            self.table.setRowCount(0)
            return

        source = self._best_lap_metrics if self._lap_mode == "best" else self._last_lap_metrics

        rows = []
        for code in self._known_drivers:
            metrics = source.get(code, {}).get(corner["number"])
            if metrics:
                rows.append((code, metrics))

        # Fastest time in corner first
        rows.sort(key=lambda r: r[1]["time_in_corner"])
        fastest_time = rows[0][1]["time_in_corner"] if rows else None

        self.table.setRowCount(len(rows))
        for row_idx, (code, m) in enumerate(rows):
            gap = m["time_in_corner"] - fastest_time
            values = [
                code,
                f"{m['entry_speed']:.0f}",
                f"{m['min_speed']:.0f}",
                f"{m['exit_speed']:.0f}",
                f"{m['avg_speed']:.0f}",
                f"{m['time_in_corner']:.2f}",
                "Fastest" if gap == 0 else f"+{gap:.2f}",
                f"{m['braking_g']:.2f}",
                f"{m['accel_g']:.2f}",
            ]
            for col_idx, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row_idx, col_idx, item)

    # ── PitWallWindow overrides ───────────────────────────────────────────

    def on_telemetry_data(self, data):
        if "frame" not in data or not data["frame"]:
            return
        drivers = data["frame"].get("drivers", {})
        if not drivers:
            return

        if data.get("circuit_corners"):
            self._refresh_corner_list(data["circuit_corners"])

        session_t = float(data["frame"].get("t") or 0)

        self._refresh_driver_list(drivers)

        for code, driver in drivers.items():
            self._append_sample(code, driver, session_t)

        self._refresh_table()

    def on_connection_status_changed(self, status):
        if status != "Connected":
            self.table.setRowCount(0)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Corner Analysis")
    window = CornerAnalysisWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
