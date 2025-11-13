from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QIcon, QPainter, QPixmap, QColor
from PyQt6.QtSvg import QSvgRenderer


def create_colored_svg_icon(svg_path, color="#FFFFFF", icon_size=QSize(24, 24)):
    """
    Load the given .svg file and paint it as a solid-colored QIcon.
    'color' can be "#FFFFFF" (white) or any valid QColor string.
    'icon_size' sets the rendered size in pixels.
    """
    svg_renderer = QSvgRenderer(svg_path)
    pixmap = QPixmap(icon_size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setPen(QColor(color))
    painter.setBrush(QColor(color))
    svg_renderer.render(painter)
    painter.end()

    return QIcon(pixmap)
