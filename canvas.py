"""canvas.py — QGraphicsView canvas with draggable, resizable text box overlays.

Implements SYSTEM_FLOW step 1 (Design Canvas) from PROJECT_MAP.md.
"""

from PySide6.QtCore import Qt, QRectF, Signal, QPointF, QObject
from PySide6.QtGui import (
    QPixmap, QPen, QColor, QBrush, QFont, QPainter, QFontMetrics,
)
from PySide6.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsRectItem,
    QGraphicsPixmapItem, QGraphicsItem, QMenu, QGraphicsLineItem
)

from project_io import TextBoxDef, new_box_id


# ── Resize handle size (pixels) ──────────────────────────────────────
HANDLE = 8


class ResizeHandle(QGraphicsRectItem):
    """Small square at the corner of a TextBoxItem for resizing."""

    def __init__(self, parent: "TextBoxItem"):
        super().__init__(-HANDLE / 2, -HANDLE / 2, HANDLE, HANDLE, parent)
        self.setBrush(QBrush(QColor("#2196F3")))
        self.setPen(QPen(Qt.NoPen))
        self.setFlag(QGraphicsItem.ItemIsMovable, False)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, False)
        self.setCursor(Qt.SizeFDiagCursor)
        self.setAcceptHoverEvents(True)
        self._parent_box = parent
        self._dragging = False
        self._origin = QPointF()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._origin = event.scenePos()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._dragging:
            delta = event.scenePos() - self._origin
            self._origin = event.scenePos()
            box = self._parent_box
            r = box.rect()
            new_w = max(20, r.width() + delta.x())
            new_h = max(20, r.height() + delta.y())
            box.setRect(QRectF(r.x(), r.y(), new_w, new_h))
            box._sync_handle()
            box._update_label()
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = False
            self._parent_box.box_changed.emit(self._parent_box)
            event.accept()


class TextBoxItem(QObject, QGraphicsRectItem):
    """Draggable, resizable text overlay region on the canvas."""

    box_changed = Signal(object)  # emitted when position/size changes
    box_selected_signal = Signal(object)  # emitted on click for property panel
    box_double_clicked = Signal(object)  # emitted on double click for linking CSV

    def __init__(self, box_def: TextBoxDef, parent=None):
        QObject.__init__(self)
        QGraphicsRectItem.__init__(self, box_def.x, box_def.y, box_def.width, box_def.height, parent)
        self.box_def = box_def
        self._preview_text = ""

        # Appearance
        self.setPen(QPen(QColor("#2196F3"), 2, Qt.DashLine))
        self.setBrush(QBrush(QColor(33, 150, 243, 30)))
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setCursor(Qt.SizeAllCursor)

        # Resize handle (bottom-right corner)
        self._handle = ResizeHandle(self)
        self._sync_handle()

    def _sync_handle(self):
        """Position the resize handle at the bottom-right of the rect."""
        r = self.rect()
        self._handle.setPos(r.right(), r.bottom())

    def _update_label(self):
        """Trigger repaint so the variable label redraws."""
        self.update()

    def sync_def_from_item(self):
        """Push current graphics state back into the TextBoxDef."""
        pos = self.pos()
        r = self.rect()
        self.box_def.x = pos.x() + r.x()
        self.box_def.y = pos.y() + r.y()
        self.box_def.width = r.width()
        self.box_def.height = r.height()

    def sync_item_from_def(self):
        """Pull TextBoxDef values into the graphics item."""
        d = self.box_def
        self.setPos(0, 0)
        self.setRect(QRectF(d.x, d.y, d.width, d.height))
        self._sync_handle()
        self.update()

    def set_preview_text(self, text: str):
        """Set the preview text shown inside the box (from CSV row)."""
        self._preview_text = text
        self.update()

    def clear_preview(self):
        self._preview_text = ""
        self.update()

    def paint(self, painter: QPainter, option, widget=None):
        super().paint(painter, option, widget)
        r = self.rect()
        painter.setClipRect(r)

        # Show either preview text or the variable placeholder
        display = self._preview_text or f"{{{{{self.box_def.variable}}}}}"
        color = QColor(self.box_def.hex_color)

        font = QFont()
        font.setPixelSize(max(10, min(self.box_def.font_size, int(r.height()))))
        painter.setFont(font)
        painter.setPen(color)

        align_flag = {"left": Qt.AlignLeft, "center": Qt.AlignHCenter, "right": Qt.AlignRight}
        flags = align_flag.get(self.box_def.align, Qt.AlignHCenter) | Qt.AlignVCenter
        painter.drawText(r, flags, display)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange and self.scene():
            new_pos = value
            
            box_center_x = new_pos.x() + self.rect().x() + self.rect().width() / 2
            box_center_y = new_pos.y() + self.rect().y() + self.rect().height() / 2
            
            snap_x, snap_y = False, False
            guide_x, guide_y = 0, 0
            
            # Snap to absolute center
            scene_rect = self.scene().sceneRect()
            center_x = scene_rect.center().x()
            center_y = scene_rect.center().y()
            
            if abs(box_center_x - center_x) < 10:
                new_pos.setX(center_x - self.rect().x() - self.rect().width() / 2)
                snap_x = True
                guide_x = center_x
            if abs(box_center_y - center_y) < 10:
                new_pos.setY(center_y - self.rect().y() - self.rect().height() / 2)
                snap_y = True
                guide_y = center_y
                
            # Snap to other items
            views = self.scene().views()
            if views and hasattr(views[0], 'get_text_boxes'):
                for other in views[0].get_text_boxes():
                    if other == self:
                        continue
                    o_center_x = other.pos().x() + other.rect().x() + other.rect().width() / 2
                    o_center_y = other.pos().y() + other.rect().y() + other.rect().height() / 2
                    
                    if not snap_x and abs(box_center_x - o_center_x) < 10:
                        new_pos.setX(o_center_x - self.rect().x() - self.rect().width() / 2)
                        snap_x = True
                        guide_x = o_center_x
                    if not snap_y and abs(box_center_y - o_center_y) < 10:
                        new_pos.setY(o_center_y - self.rect().y() - self.rect().height() / 2)
                        snap_y = True
                        guide_y = o_center_y
            
            value = new_pos
            if views and hasattr(views[0], 'show_guides'):
                views[0].show_guides(snap_x, snap_y, guide_x, guide_y)
                
        elif change == QGraphicsItem.ItemPositionHasChanged:
            self.sync_def_from_item()
            self.box_changed.emit(self)
        return super().itemChange(change, value)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self.sync_def_from_item()
        self.box_changed.emit(self)
        views = self.scene().views()
        if views and hasattr(views[0], 'show_guides'):
            views[0].show_guides(False, False)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self.box_selected_signal.emit(self)

    def mouseDoubleClickEvent(self, event):
        super().mouseDoubleClickEvent(event)
        self.box_double_clicked.emit(self)


class CanvasView(QGraphicsView):
    """The main design canvas. Displays a certificate template with text box overlays."""

    box_selected = Signal(object)   # TextBoxItem or None
    box_double_clicked = Signal(object) # TextBoxItem
    boxes_changed = Signal()        # any box added/removed/moved

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.default_csv_id = ""
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHint(QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.NoDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)

        self._template_item: QGraphicsPixmapItem | None = None
        self._text_items: list[TextBoxItem] = []

        # Guides
        self._guide_v = QGraphicsLineItem()
        self._guide_v.setPen(QPen(Qt.red, 1, Qt.DashLine))
        self._guide_v.setZValue(100)
        self._guide_v.hide()
        self._scene.addItem(self._guide_v)
        
        self._guide_h = QGraphicsLineItem()
        self._guide_h.setPen(QPen(Qt.red, 1, Qt.DashLine))
        self._guide_h.setZValue(100)
        self._guide_h.hide()
        self._scene.addItem(self._guide_h)

    def show_guides(self, v: bool, h: bool, cx: float = 0, cy: float = 0):
        rect = self._scene.sceneRect()
        
        if v:
            self._guide_v.setLine(cx, rect.top(), cx, rect.bottom())
            self._guide_v.show()
        else:
            self._guide_v.hide()
            
        if h:
            self._guide_h.setLine(rect.left(), cy, rect.right(), cy)
            self._guide_h.show()
        else:
            self._guide_h.hide()

    # ── Template management ───────────────────────────────────────────

    def load_template(self, path: str):
        """Load a PNG as the background template."""
        pixmap = QPixmap(path)
        if pixmap.isNull():
            raise ValueError(f"Cannot load image: {path}")

        if self._template_item:
            self._scene.removeItem(self._template_item)

        self._template_item = QGraphicsPixmapItem(pixmap)
        self._template_item.setZValue(-1)
        self._scene.addItem(self._template_item)
        self.setSceneRect(QRectF(pixmap.rect()))
        self.fitInView(self._template_item, Qt.KeepAspectRatio)

    # ── Text box management ───────────────────────────────────────────

    def add_text_box(self, box_def: TextBoxDef | None = None) -> TextBoxItem:
        """Add a text box to the canvas. If no def given, creates a default."""
        if box_def is None:
            sr = self.sceneRect()
            box_def = TextBoxDef(
                id=new_box_id(),
                x=sr.width() / 4, y=sr.height() / 4,
                width=sr.width() / 2, height=60,
                font_path="", font_size=36,
                hex_color="#1A1A1A", variable="Variable",
            )

        item = TextBoxItem(box_def)
        # Connect signals — these are custom signals on QGraphicsRectItem subclass,
        # so we connect via the underlying Qt mechanism on the scene/view side.
        item.box_changed.connect(lambda _: self.boxes_changed.emit())
        item.box_selected_signal.connect(lambda it: self.box_selected.emit(it))
        item.box_double_clicked.connect(lambda it: self.box_double_clicked.emit(it))
        self._scene.addItem(item)
        self._text_items.append(item)
        self.boxes_changed.emit()
        return item

    def remove_text_box(self, item: TextBoxItem):
        if item in self._text_items:
            self._text_items.remove(item)
            self._scene.removeItem(item)
            self.boxes_changed.emit()

    # ── Drag and Drop ─────────────────────────────────────────────────

    def dragEnterEvent(self, event):
        if event.mimeData().hasText() and event.mimeData().text().startswith("PRINTGEN_DRAG:"):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasText() and event.mimeData().text().startswith("PRINTGEN_DRAG:"):
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        text = event.mimeData().text()
        if text.startswith("PRINTGEN_DRAG:"):
            _, tab_id, header = text.split(":", 2)
            scene_pos = self.mapToScene(event.pos())
            box_def = TextBoxDef(
                id=new_box_id(),
                x=scene_pos.x(), y=scene_pos.y(),
                width=200, height=50,
                font_path="", font_size=36,
                hex_color="#1A1A1A", variable=header,
                linked_csv=tab_id
            )
            self.add_text_box(box_def)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)

    def get_text_boxes(self) -> list[TextBoxItem]:
        return list(self._text_items)

    def get_box_defs(self) -> list[TextBoxDef]:
        """Get current TextBoxDef list (positions synced)."""
        for item in self._text_items:
            item.sync_def_from_item()
        return [item.box_def for item in self._text_items]

    def clear_boxes(self):
        for item in list(self._text_items):
            self._scene.removeItem(item)
        self._text_items.clear()
        self.boxes_changed.emit()

    def load_boxes(self, defs: list[TextBoxDef]):
        """Replace all boxes with the given definitions."""
        self.clear_boxes()
        for d in defs:
            self.add_text_box(d)

    # ── Preview ───────────────────────────────────────────────────────

    def set_preview(self, row_data: dict[str, dict]):
        """Inject one CSV row's values from multiple datasets into the text boxes for preview."""
        for item in self._text_items:
            tab_id = item.box_def.linked_csv
            header = item.box_def.variable
            if tab_id and tab_id in row_data and header in row_data[tab_id]:
                item.set_preview_text(str(row_data[tab_id][header]))
            else:
                item.clear_preview()

    def clear_preview(self):
        for item in self._text_items:
            item.clear_preview()

    # ── Context menu ──────────────────────────────────────────────────

    def contextMenuEvent(self, event):
        scene_pos = self.mapToScene(event.pos())
        item_at = self._scene.itemAt(scene_pos, self.transform())

        menu = QMenu(self)
        if isinstance(item_at, (TextBoxItem, ResizeHandle)):
            target = item_at if isinstance(item_at, TextBoxItem) else item_at._parent_box
            delete_act = menu.addAction("Delete Box")
            delete_act.triggered.connect(lambda: self.remove_text_box(target))
        else:
            add_act = menu.addAction("Add Text Box")
            add_act.triggered.connect(lambda: self._add_box_at(scene_pos))

        menu.exec_(event.globalPos())

    def _add_box_at(self, pos: QPointF):
        box_def = TextBoxDef(
            id=new_box_id(),
            x=pos.x(), y=pos.y(),
            width=200, height=50,
            font_path="", font_size=36,
            hex_color="#1A1A1A", variable="Variable",
            linked_csv=self.default_csv_id
        )
        self.add_text_box(box_def)

    # ── Zoom ──────────────────────────────────────────────────────────

    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._template_item:
            self.fitInView(self._template_item, Qt.KeepAspectRatio)
