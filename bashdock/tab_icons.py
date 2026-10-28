"""Original line icons shared by tabs and their picker; no fonts or external files."""
from functools import lru_cache

from .tab_icon_catalog import GENERIC, SYMBOLS, CATALOG, next_generic, assign_missing


@lru_cache(maxsize=256)
def icon(key, color='#dde4ef'):
    from PySide6.QtCore import QByteArray, Qt
    from PySide6.QtGui import QIcon, QPainter, QPixmap
    from PySide6.QtSvg import QSvgRenderer
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
           f'fill="none" stroke="{color}" stroke-width="1.8" stroke-linecap="round" '
           f'stroke-linejoin="round">{CATALOG[key][1]}</svg>')
    renderer = QSvgRenderer(QByteArray(svg.encode()))
    result = QIcon()
    for size in (16, 20, 24, 32, 48, 64):
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        result.addPixmap(pixmap)
    return result
