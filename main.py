"""main.py — Entry point for the IEEE Certificate/Badge Batch Generator.

Wires together: canvas ↔ project_io ↔ data_engine ↔ render_engine.
"""

import logging
import sys
from pathlib import Path

from PIL import Image as PILImage
from PySide6.QtCore import Qt, QThread, Signal, Slot
from PySide6.QtGui import QAction, QColor, QImage, QPalette, QPixmap
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QPushButton, QLabel, QLineEdit, QComboBox, QSpinBox,
    QColorDialog, QFileDialog, QTableWidget, QTableWidgetItem, QHeaderView,
    QFormLayout, QGroupBox, QMessageBox, QMenu, QGraphicsView, QProgressBar,
    QDialog, QDialogButtonBox, QTextEdit, QFontComboBox
)
from PySide6.QtGui import QFont, QIcon, QPixmap

from project_io import load_project, save_project, TextBoxDef
from canvas import CanvasView, TextBoxItem
from data_engine import load_csv, auto_map, validate_mapping
from render_engine import render_batch, render_single
from email_engine import EmailWorker

log = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


# ── Background render worker ─────────────────────────────────────────

class RenderWorker(QThread):
    progress = Signal(int, int)
    finished_ok = Signal(list)
    finished_err = Signal(str)

    def __init__(self, template_path, text_boxes, datasets, max_rows, output_dir, id_column):
        super().__init__()
        self.template_path = template_path
        self.text_boxes = text_boxes
        self.datasets = datasets
        self.max_rows = max_rows
        self.output_dir = output_dir
        self.id_column = id_column

    def run(self):
        try:
            outputs = render_batch(
                self.template_path, self.text_boxes, self.datasets,
                self.max_rows, self.output_dir, self.id_column,
                progress_cb=lambda cur, tot: self.progress.emit(cur, tot),
            )
            self.finished_ok.emit(outputs)
        except Exception as e:
            self.finished_err.emit(str(e))


import winreg
import os

def build_windows_font_map() -> dict:
    fonts = {}
    font_dir = os.environ.get("WINDIR", "C:\\Windows") + "\\Fonts"
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts") as key:
            info = winreg.QueryInfoKey(key)
            for i in range(info[1]):
                name, value, _ = winreg.EnumValue(key, i)
                if name.endswith(" (TrueType)") or name.endswith(" (OpenType)"):
                    clean_name = name[:name.rfind(" (")].strip()
                    if not os.path.isabs(value):
                        value = os.path.join(font_dir, value)
                    fonts[clean_name] = value
    except Exception as e:
        log.error(f"Failed to read font registry: {e}")
    return fonts

WINDOWS_FONTS = build_windows_font_map()

# ── Resize Handle ────────────────────────────────────────────────────

# ── Preview panel ────────────────────────────────────────────────────

class PreviewPanel(QWidget):
    """Small panel showing a Pillow-rendered preview of the certificate."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap: QPixmap | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        header = QLabel("Preview")
        header.setStyleSheet("font-weight: bold; font-size: 12px;")
        layout.addWidget(header)

        self._image_label = QLabel("No preview yet")
        self._image_label.setAlignment(Qt.AlignCenter)
        self._image_label.setStyleSheet(
            "background: #1a1a1a; border: 1px solid #333; border-radius: 4px; "
            "color: #666; padding: 8px; font-size: 11px;"
        )
        self._image_label.setMinimumHeight(120)
        layout.addWidget(self._image_label, 1)

    def set_preview_image(self, pil_image):
        """Display a PIL Image scaled to fit."""
        img = pil_image.convert("RGBA")
        data = img.tobytes("raw", "RGBA")
        qimg = QImage(data, img.width, img.height, QImage.Format_RGBA8888)
        self._pixmap = QPixmap.fromImage(qimg)
        self._rescale()

    def clear(self):
        self._pixmap = None
        self._image_label.clear()
        self._image_label.setText("No preview yet")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._pixmap:
            self._rescale()

    def _rescale(self):
        if self._pixmap and not self._pixmap.isNull():
            scaled = self._pixmap.scaled(
                self._image_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self._image_label.setPixmap(scaled)


# ── Action buttons panel ─────────────────────────────────────────────

class ActionPanel(QWidget):
    """Prominent action buttons for primary workflows."""

    load_template_clicked = Signal()
    load_folder_clicked = Signal()
    load_csv_clicked = Signal()
    generate_clicked = Signal()
    email_clicked = Signal()
    new_project_clicked = Signal()
    open_project_clicked = Signal()
    save_project_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # ── Title Area ──
        title_lay = QHBoxLayout()
        title_lay.setAlignment(Qt.AlignCenter)
        
        icon_label = QLabel()
        pixmap = QPixmap("icon.png").scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        icon_label.setPixmap(pixmap)
        
        title_label = QLabel("Badgr")
        title_font = QFont("Impact", 28, QFont.Normal)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #4285F4; margin-bottom: 5px;")
        
        title_lay.addWidget(icon_label)
        title_lay.addWidget(title_label)
        layout.addLayout(title_lay)



        # ── Import section ──
        imp_group = QGroupBox("Import")
        imp_lay = QVBoxLayout(imp_group)
        imp_lay.setSpacing(4)
        self._btn_png = self._make_btn(
            "\U0001F4C4  Load Template (PNG)", "#1976D2", imp_lay, 42)
        self._btn_folder = self._make_btn(
            "\U0001F4C1  Load Folder (PNGs)", "#1565C0", imp_lay, 42)
        self._btn_csv = self._make_btn(
            "\U0001F4CA  Load CSV Data", "#2E7D32", imp_lay, 42)
        layout.addWidget(imp_group)

        # ── Generate section ──
        gen_group = QGroupBox("Generate")
        gen_lay = QVBoxLayout(gen_group)
        gen_lay.setSpacing(4)
        self._btn_generate = self._make_btn(
            "\U0001F680  Batch Generate", "#C62828", gen_lay, 52)
        self._btn_email = self._make_btn(
            "\U0001F4E7  Send Emails", "#4A148C", gen_lay, 42)
        layout.addWidget(gen_group)

        layout.addStretch()

        # Wire signals
        self._btn_png.clicked.connect(self.load_template_clicked)
        self._btn_folder.clicked.connect(self.load_folder_clicked)
        self._btn_csv.clicked.connect(self.load_csv_clicked)
        self._btn_generate.clicked.connect(self.generate_clicked)
        self._btn_email.clicked.connect(self.email_clicked)

    @staticmethod
    def _make_btn(text, bg_color, parent_layout, height=34):
        btn = QPushButton(text)
        btn.setMinimumHeight(height)
        btn.setCursor(Qt.PointingHandCursor)
        c = QColor(bg_color)
        hover = c.lighter(130).name()
        pressed = c.darker(120).name()
        btn.setStyleSheet(
            f"QPushButton {{ background: {bg_color}; color: #eee; border: none; "
            f"border-radius: 4px; font-size: 13px; font-weight: bold; "
            f"padding: 4px 10px; }}"
            f"QPushButton:hover {{ background: {hover}; }}"
            f"QPushButton:pressed {{ background: {pressed}; }}"
        )
        parent_layout.addWidget(btn)
        return btn


# ── Properties panel ─────────────────────────────────────────────────

class PropertiesPanel(QWidget):
    """Editor for the selected text box's properties."""

    property_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_item: TextBoxItem | None = None

        layout = QFormLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # Mapping Row (New)
        self._csv_label = QLabel("None")
        layout.addRow("Linked CSV:", self._csv_label)
        
        self._var_combo = QComboBox()
        self._var_combo.setEditable(True)
        layout.addRow("Variable:", self._var_combo)

        self._font_combo = QFontComboBox()
        self._font_combo.setEditable(True)
        layout.addRow("Font:", self._font_combo)

        self._size_spin = QSpinBox()
        self._size_spin.setRange(1, 999)
        self._size_spin.setValue(36)
        layout.addRow("Font Size:", self._size_spin)

        self._color_btn = QPushButton()
        self._color_btn.setFixedSize(60, 28)
        self._color_label = QLabel("#1A1A1A")
        color_row = QHBoxLayout()
        color_row.addWidget(self._color_btn)
        color_row.addWidget(self._color_label)
        layout.addRow("Color:", color_row)

        self._align_combo = QComboBox()
        self._align_combo.addItems(["left", "center", "right"])
        layout.addRow("Align:", self._align_combo)

        self._pos_label = QLabel("")
        layout.addRow("Position:", self._pos_label)

        self._size_label = QLabel("")
        layout.addRow("Size:", self._size_label)

        # Connections
        self._var_combo.currentTextChanged.connect(self._apply)
        self._font_combo.currentFontChanged.connect(self._on_font_changed)
        self._size_spin.valueChanged.connect(self._apply)
        self._color_btn.clicked.connect(self._pick_color)
        self._align_combo.currentIndexChanged.connect(self._apply)

        self.setEnabled(False)
        self._datasets_ref = {}

    def set_datasets(self, datasets: dict):
        self._datasets_ref = datasets
        self._refresh_var_combo()

    def set_item(self, item: TextBoxItem | None):
        self._current_item = item
        self.setEnabled(item is not None)
        if item is None:
            return
        d = item.box_def
        self._csv_label.setText(d.linked_csv if d.linked_csv else "None")
        self._refresh_var_combo()
        
        # Reverse lookup font family
        self._font_combo.blockSignals(True)
        fam_match = None
        for fam, path in WINDOWS_FONTS.items():
            if d.font_path and path.lower() == d.font_path.lower():
                fam_match = fam
                break
        if fam_match:
            self._font_combo.setCurrentFont(QFont(fam_match))
        elif d.font_path:
            # Maybe it's a direct path not in standard registry
            pass
        self._font_combo.blockSignals(False)
        self._size_spin.setValue(d.font_size)
        self._set_color_swatch(d.hex_color)
        self._color_label.setText(d.hex_color)
        idx = self._align_combo.findText(d.align)
        if idx >= 0:
            self._align_combo.setCurrentIndex(idx)
        self._update_pos_size(d)

    def _refresh_var_combo(self):
        self._var_combo.blockSignals(True)
        self._var_combo.clear()
        if self._current_item:
            csv_id = self._current_item.box_def.linked_csv
            if csv_id and csv_id in self._datasets_ref:
                self._var_combo.addItems([""] + self._datasets_ref[csv_id]["headers"])
            self._var_combo.setCurrentText(self._current_item.box_def.variable)
        self._var_combo.blockSignals(False)

    def _update_pos_size(self, d: TextBoxDef):
        self._pos_label.setText(f"({d.x:.0f}, {d.y:.0f})")
        self._size_label.setText(f"{d.width:.0f} × {d.height:.0f}")

    def refresh_position(self):
        """Called when the box is dragged/resized."""
        if self._current_item:
            self._update_pos_size(self._current_item.box_def)

    def _set_color_swatch(self, hex_color: str):
        self._color_btn.setStyleSheet(
            f"background-color: {hex_color}; border: 1px solid #666;"
        )

    def _on_font_changed(self, font: QFont):
        if not self._current_item:
            return
        family = font.family()
        
        # Find path from Windows registry mapping
        # Exact match
        path = WINDOWS_FONTS.get(family)
        if not path:
            # Try to find closely named family (e.g. "Arial" matching "Arial Bold" if exact fails, though QFontComboBox usually maps well)
            for k, v in WINDOWS_FONTS.items():
                if k.startswith(family):
                    path = v
                    break
                    
        if path:
            self._current_item.box_def.font_path = path
            self._current_item.update()
            self.property_changed.emit()

    def _pick_color(self):
        if not self._current_item:
            return
        color = QColorDialog.getColor(
            QColor(self._current_item.box_def.hex_color), self, "Pick Text Color",
            options=QColorDialog.DontUseNativeDialog
        )
        if color.isValid():
            hex_val = color.name()
            self._current_item.box_def.hex_color = hex_val
            self._set_color_swatch(hex_val)
            self._color_label.setText(hex_val)
            self._current_item.update()
            self.property_changed.emit()

    def _apply(self):
        if not self._current_item:
            return
        d = self._current_item.box_def
        d.variable = self._var_combo.currentText().strip() or "Variable"
        d.font_size = self._size_spin.value()
        d.align = self._align_combo.currentText()
        self._current_item.update()
        self.property_changed.emit()


# ── Data panel (CSV table + mapping) ─────────────────────────────────

class DraggableTableWidget(QTableWidget):
    def mimeData(self, items):
        mime = super().mimeData(items)
        if items:
            col = items[0].column()
            header = self.horizontalHeaderItem(col).text()
            tab_id = self.property("tab_id")
            mime.setText(f"PRINTGEN_DRAG:{tab_id}:{header}")
        return mime

class DataPanel(QWidget):
    """Left-side panel: CSV data tables in tabs."""

    data_changed = Signal()  # emitted when a new CSV is loaded or closed

    def __init__(self, parent=None):
        super().__init__(parent)
        self.csv_datasets: dict[str, dict] = {} # tab_id -> {"headers": [...], "rows": [...], "name": str}
        self._counter = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        from PySide6.QtWidgets import QTabWidget
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self._on_tab_close)
        layout.addWidget(self.tabs)

    def load_data(self, headers: list[str], rows: list[dict], filename: str = ""):
        tab_id = str(self._counter)
        self._counter += 1
        name = Path(filename).name if filename else f"CSV {tab_id}"
        
        self.csv_datasets[tab_id] = {"headers": headers, "rows": rows, "name": name}

        # CSV preview table
        table = DraggableTableWidget()
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setDragEnabled(True)
        table.setDragDropMode(QTableWidget.DragOnly)
        table.setSelectionBehavior(QTableWidget.SelectItems)
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        preview_rows = rows[:50]  # ponytail: only show first 50 rows in UI preview
        table.setRowCount(len(preview_rows))
        for r, row in enumerate(preview_rows):
            for c, h in enumerate(headers):
                table.setItem(r, c, QTableWidgetItem(str(row.get(h, ""))))
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)

        table.setProperty("tab_id", tab_id)
        self.tabs.addTab(table, f"{tab_id}: {name}")
        self.tabs.setCurrentWidget(table)
        self.data_changed.emit()

    def _on_tab_close(self, index: int):
        widget = self.tabs.widget(index)
        tab_id = widget.property("tab_id")
        if tab_id in self.csv_datasets:
            del self.csv_datasets[tab_id]
        self.tabs.removeTab(index)
        widget.deleteLater()
        self.data_changed.emit()

    def get_datasets(self) -> dict[str, dict]:
        return self.csv_datasets


# ── Main Window ──────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Badgr - Certificate/Badge Generator")
        self.setWindowIcon(QIcon("icon.png"))
        self.resize(1400, 850)

        self._project_path: str | None = None
        self._template_path: str = ""
        self._csv_path: str | None = None
        self._id_column: str | None = None
        self._worker: RenderWorker | None = None

        # ── Build panels ──
        self._canvas = CanvasView()
        self._preview_panel = PreviewPanel()
        self._data_panel = DataPanel()
        self._props = PropertiesPanel()
        self._actions = ActionPanel()

        # ── Left column: Preview (top) + CSV Data (bottom) ──
        left_splitter = QSplitter(Qt.Vertical)
        left_splitter.addWidget(self._preview_panel)
        left_splitter.addWidget(self._data_panel)
        left_splitter.setSizes([250, 400])
        left_splitter.setMinimumWidth(220)

        # ── Right column: Actions (top) + Properties (bottom) ──
        right_splitter = QSplitter(Qt.Vertical)
        right_splitter.addWidget(self._actions)
        right_splitter.addWidget(self._props)
        right_splitter.setSizes([380, 350])
        right_splitter.setMinimumWidth(220)

        # ── Main 3-column splitter: Left | Canvas | Right ──
        main_splitter = QSplitter(Qt.Horizontal)
        main_splitter.addWidget(left_splitter)
        main_splitter.addWidget(self._canvas)
        main_splitter.addWidget(right_splitter)
        main_splitter.setSizes([260, 780, 280])
        main_splitter.setStretchFactor(0, 0)  # left: fixed
        main_splitter.setStretchFactor(1, 1)  # canvas: takes remaining space
        main_splitter.setStretchFactor(2, 0)  # right: fixed

        self.setCentralWidget(main_splitter)

        # Progress bar in status bar
        self._progress = QProgressBar()
        self._progress.setMaximumWidth(300)
        self._progress.setVisible(False)
        self.statusBar().addPermanentWidget(self._progress)
        self.statusBar().showMessage("Ready")
        
        # Add footer label
        footer_label = QLabel("created with love by Bechir Touskié")
        footer_label.setStyleSheet("color: #888888; font-style: italic;")
        self.statusBar().addWidget(footer_label)

        self._connect_signals()
        self._apply_dark_theme()
        log.info("Application started")

    def _apply_dark_theme(self):
        """Apply a dark color palette for a modern look."""
        p = QPalette()
        p.setColor(QPalette.Window, QColor(30, 30, 30))
        p.setColor(QPalette.WindowText, QColor(220, 220, 220))
        p.setColor(QPalette.Base, QColor(25, 25, 25))
        p.setColor(QPalette.AlternateBase, QColor(35, 35, 35))
        p.setColor(QPalette.ToolTipBase, QColor(50, 50, 50))
        p.setColor(QPalette.ToolTipText, QColor(220, 220, 220))
        p.setColor(QPalette.Text, QColor(220, 220, 220))
        p.setColor(QPalette.Button, QColor(45, 45, 45))
        p.setColor(QPalette.ButtonText, QColor(220, 220, 220))
        p.setColor(QPalette.Link, QColor(66, 133, 244))
        p.setColor(QPalette.Highlight, QColor(66, 133, 244))
        p.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
        QApplication.instance().setPalette(p)



    def _connect_signals(self):
        # Canvas signals
        self._canvas.box_selected.connect(self._on_box_selected)
        self._canvas.box_double_clicked.connect(self._on_box_double_clicked)
        self._canvas.boxes_changed.connect(self._on_boxes_changed)
        self._props.property_changed.connect(self._on_property_changed)
        self._data_panel.data_changed.connect(self._on_data_changed)

        # Action panel buttons
        self._actions.load_template_clicked.connect(self._import_template)
        self._actions.load_folder_clicked.connect(self._load_folder)
        self._actions.load_csv_clicked.connect(self._load_csv)
        self._actions.generate_clicked.connect(self._batch_render)
        self._actions.email_clicked.connect(self._email_batch)

    # ── Signal handlers ───────────────────────────────────────────────

    def _on_box_selected(self, item: TextBoxItem):
        self._props.set_item(item)

    def _on_boxes_changed(self):
        self._props.refresh_position()
        self._preview()

    def _on_property_changed(self):
        self._preview()

    def _on_data_changed(self):
        datasets = self._data_panel.get_datasets()
        self._props.set_datasets(datasets)
        self._canvas.default_csv_id = list(datasets.keys())[0] if datasets else ""
        self._preview()

    def _on_box_double_clicked(self, item: TextBoxItem):
        datasets = self._data_panel.get_datasets()
        if not datasets:
            QMessageBox.information(self, "No CSVs", "Please load a CSV first.")
            return

        from PySide6.QtWidgets import QDialog, QVBoxLayout, QListWidget, QDialogButtonBox
        dlg = QDialog(self)
        dlg.setWindowTitle("Link CSV")
        layout = QVBoxLayout(dlg)
        
        list_widget = QListWidget()
        for tab_id, ds in datasets.items():
            list_widget.addItem(f"{tab_id}: {ds['name']}")
        
        for i in range(list_widget.count()):
            if list_widget.item(i).text().startswith(f"{item.box_def.linked_csv}:"):
                list_widget.setCurrentRow(i)

        layout.addWidget(list_widget)

        bbox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bbox.accepted.connect(dlg.accept)
        bbox.rejected.connect(dlg.reject)
        layout.addWidget(bbox)

        if dlg.exec() == QDialog.Accepted and list_widget.currentItem():
            tab_id = list_widget.currentItem().text().split(":")[0]
            item.box_def.linked_csv = tab_id
            self._props.set_item(item)
            self._preview()

    # ── File actions ──────────────────────────────────────────────────

    def _import_template(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Template Image", "",
            "Images (*.png *.jpg *.jpeg *.bmp);;All Files (*)"
        )
        if path:
            try:
                self._canvas.load_template(path)
                self._template_path = path
                self.statusBar().showMessage(f"Template loaded: {Path(path).name}")
                log.info("Template loaded: %s", path)
            except ValueError as e:
                QMessageBox.critical(self, "Error", str(e))
                log.error("Template load failed: %s", e)

    def _load_folder(self):
        """Import a folder of PNG templates — loads the first, reports count."""
        folder = QFileDialog.getExistingDirectory(self, "Select Template Folder")
        if not folder:
            return
        pngs = sorted(Path(folder).glob("*.png"))
        if not pngs:
            QMessageBox.warning(self, "No PNGs", "No .png files found in that folder.")
            return
        try:
            self._canvas.load_template(str(pngs[0]))
            self._template_path = str(pngs[0])
            self.statusBar().showMessage(
                f"Loaded: {pngs[0].name}  ({len(pngs)} PNGs in folder)"
            )
            log.info("Loaded template from folder: %s (%d PNGs)", folder, len(pngs))
        except ValueError as e:
            QMessageBox.critical(self, "Error", str(e))
            log.error("Folder template load failed: %s", e)


    # ── Data actions ──────────────────────────────────────────────────

    def _load_csv(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Load CSV", "",
            "CSV Files (*.csv);;Text Files (*.txt);;All Files (*)"
        )
        if not path:
            return
        try:
            headers, rows = load_csv(path)
            self._data_panel.load_data(headers, rows, filename=path)

            self.statusBar().showMessage(
                f"CSV loaded: {len(rows)} rows, {len(headers)} columns. "
            )
            log.info("CSV loaded: %s (%d rows)", path, len(rows))
        except (ValueError, OSError) as e:
            QMessageBox.critical(self, "Error", f"Cannot load CSV:\n{e}")
            log.error("CSV load failed: %s", e)

    def _set_id_column(self):
        datasets = self._data_panel.get_datasets()
        if not datasets:
            QMessageBox.information(self, "Info", "Load a CSV first.")
            return

        from PySide6.QtWidgets import QInputDialog
        # For simplicity, if multiple datasets, we just gather all headers with tab_id prefix
        options = []
        for tab_id, ds in datasets.items():
            for h in ds["headers"]:
                options.append(f"[{tab_id}] {h}")
        
        col, ok = QInputDialog.getItem(
            self, "Set ID Column",
            "Choose the column whose values become output filenames:",
            options, 0, False,
        )
        if ok:
            self._id_column = col
            self.statusBar().showMessage(f"ID column set to: {col}")
            log.info("ID column set to: %s", col)

    # ── Generate actions ──────────────────────────────────────────────

    def _build_row0_preview(self) -> dict:
        datasets = self._data_panel.get_datasets()
        row_data = {}
        for tab_id, ds in datasets.items():
            if ds["rows"]:
                row_data[tab_id] = ds["rows"][0]
        return row_data

    def _preview(self):
        datasets = self._data_panel.get_datasets()
        row_data = self._build_row0_preview()
        
        # Canvas preview (QPainter-based, fast approximation)
        self._canvas.set_preview(row_data) # wait, we need to update canvas.py set_preview
        
        # Rendered preview (Pillow actual output in the preview panel)
        if self._template_path and Path(self._template_path).exists():
            try:
                template = PILImage.open(self._template_path).convert("RGBA")
                rendered = render_single(
                    template, self._canvas.get_box_defs(), datasets, row_index=0
                )
                self._preview_panel.set_preview_image(rendered)
            except Exception as e:
                log.error("Preview render failed: %s", e)
        self.statusBar().showMessage("Preview: showing row 1 values")

    def _clear_preview(self):
        self._canvas.clear_preview()
        self._preview_panel.clear()

    def _batch_render(self):
        if not self._template_path:
            QMessageBox.warning(self, "Warning", "Import a template image first.")
            return
        datasets = self._data_panel.get_datasets()
        if not datasets:
            QMessageBox.warning(self, "Warning", "Load a CSV first.")
            return
        box_defs = self._canvas.get_box_defs()

        # Determine max rows
        max_rows = max([len(ds["rows"]) for ds in datasets.values()])
        if max_rows == 0:
            return

        output_dir = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if not output_dir:
            return

        # ID column logic: if not set, fallback to something
        id_col = self._id_column
        if not id_col:
            # Pick first column of first dataset
            first_tab = list(datasets.keys())[0]
            id_col = f"[{first_tab}] {datasets[first_tab]['headers'][0]}"

        # Launch background render
        self._progress.setVisible(True)
        self._progress.setRange(0, max_rows)
        self._progress.setValue(0)
        self.statusBar().showMessage("Rendering…")
        log.info("Batch render started: %d rows → %s", max_rows, output_dir)

        self._worker = RenderWorker(
            self._template_path, box_defs, datasets, max_rows, output_dir, id_col
        )
        self._worker.progress.connect(self._on_render_progress)
        self._worker.finished_ok.connect(self._on_render_done)
        self._worker.finished_err.connect(self._on_render_error)
        self._worker.start()

    def _email_batch(self):
        if not self._template_path:
            QMessageBox.warning(self, "Warning", "Import a template image first.")
            return
        datasets = self._data_panel.get_datasets()
        if not datasets:
            QMessageBox.warning(self, "Warning", "Load a CSV first.")
            return
            
        max_rows = max([len(ds["rows"]) for ds in datasets.values()])
        if max_rows == 0:
            return

        options = []
        for tab_id, ds in datasets.items():
            for h in ds["headers"]:
                options.append(f"[{tab_id}] {h}")
                
        # EmailDialog class nested for simplicity
        class EmailDialog(QDialog):
            def __init__(self, headers, parent=None):
                super().__init__(parent)
                self.setWindowTitle("Configure Batch Email")
                self.resize(400, 400)
                layout = QVBoxLayout(self)

                form = QFormLayout()
                self.smtp_server = QLineEdit("smtp.gmail.com")
                form.addRow("SMTP Server:", self.smtp_server)
                self.smtp_port = QSpinBox()
                self.smtp_port.setRange(1, 65535)
                self.smtp_port.setValue(587)
                form.addRow("SMTP Port:", self.smtp_port)
                self.sender = QLineEdit()
                self.sender.setPlaceholderText("your.email@gmail.com")
                form.addRow("Sender Email:", self.sender)
                self.password = QLineEdit()
                self.password.setEchoMode(QLineEdit.Password)
                self.password.setPlaceholderText("App Password")
                form.addRow("Password:", self.password)
                self.receiver = QComboBox()
                self.receiver.addItems(headers)
                form.addRow("Receiver Column:", self.receiver)
                self.subject = QLineEdit("Your Certificate")
                form.addRow("Subject:", self.subject)
                self.body = QTextEdit("Attached is your certificate.")
                form.addRow("Body:", self.body)
                
                layout.addLayout(form)
                bbox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
                bbox.accepted.connect(self.accept)
                bbox.rejected.connect(self.reject)
                layout.addWidget(bbox)

            def get_data(self):
                return {
                    "smtp_server": self.smtp_server.text(), "smtp_port": self.smtp_port.value(),
                    "sender": self.sender.text(), "password": self.password.text(),
                    "receiver_column": self.receiver.currentText(), "subject": self.subject.text(),
                    "body": self.body.toPlainText()
                }

        dlg = EmailDialog(options, self)
        if dlg.exec() != QDialog.Accepted:
            return
            
        data = dlg.get_data()
        
        self._progress.setVisible(True)
        self._progress.setRange(0, max_rows)
        self._progress.setValue(0)
        self.statusBar().showMessage("Sending Emails...")
        log.info("Batch email started.")
        
        self._worker = EmailWorker(
            self._template_path, self._canvas.get_box_defs(), datasets, max_rows,
            data["smtp_server"], data["smtp_port"], data["sender"], data["password"],
            data["receiver_column"], data["subject"], data["body"]
        )
        self._worker.progress.connect(self._on_render_progress)
        self._worker.finished_ok.connect(self._on_email_done)
        self._worker.finished_err.connect(self._on_render_error)
        self._worker.start()

    @Slot(int)
    def _on_email_done(self, count: int):
        self._progress.setVisible(False)
        self._worker = None
        self.statusBar().showMessage(f"Done! {count} emails sent successfully.")
        log.info("Batch email complete: %d sent", count)
        QMessageBox.information(self, "Success", f"Successfully sent {count} emails.")

    @Slot(int, int)
    def _on_render_progress(self, current: int, total: int):
        self._progress.setValue(current)
        self.statusBar().showMessage(f"Rendering… {current}/{total}")

    @Slot(list)
    def _on_render_done(self, outputs: list):
        self._progress.setVisible(False)
        self._worker = None
        self.statusBar().showMessage(f"Done! {len(outputs)} certificates generated.")
        log.info("Batch render complete: %d certificates", len(outputs))
        QMessageBox.information(
            self, "Batch Render Complete",
            f"Generated {len(outputs)} certificate(s).\n\n"
            f"Output directory:\n{outputs[0].parent if outputs else '(none)'}",
        )

    @Slot(str)
    def _on_render_error(self, error: str):
        self._progress.setVisible(False)
        self._worker = None
        self.statusBar().showMessage("Render failed.")
        log.error("Batch render failed: %s", error)
        QMessageBox.critical(self, "Render Error", f"Batch render failed:\n{error}")


# ── Entry point ──────────────────────────────────────────────────────

import ctypes

def main():
    try:
        # Tell Windows this is a distinct app so the taskbar uses the QIcon
        myappid = 'pash.badgr.printgen.1'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception:
        pass

    app = QApplication(sys.argv)
    app.setApplicationName("Badgr Certificate Generator")
    app.setStyle("Fusion")

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
