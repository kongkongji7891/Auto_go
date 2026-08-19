"""
PyQt6 围棋棋盘控件（增强缩小率）
上方数字（1~19），左侧字母（A~T），自适应正方形，动态字号。
双行文字更靠近中心，单行字号降低，窗口缩小时缩小率更大。
"""
from __future__ import annotations

from typing import Optional, List, Dict, Any

from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import (
    QPainter, QPen, QBrush, QColor, QFont, QPolygonF,
    QFontMetrics,
)
from PyQt6.QtWidgets import QWidget, QSizePolicy


class go_board(QWidget):
    """围棋棋盘控件（19×19）"""

    LEFT_LETTERS = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H',
                    'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T']

    def __init__(self, show_coords: bool = True,
                 bg_color: str = "#DEB887",
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._show_coords = show_coords
        self._bg_color = QColor(bg_color)
        self._grid_color = QColor("#333333")
        self._star_color = QColor("#333333")
        self._coords_color = QColor("#222222")
        self._text_color = QColor("#FFFFFF")

        self._board: List[List[Optional[Dict[str, Any]]]] = [
            [None for _ in range(19)] for _ in range(19)
        ]

        self.setMinimumSize(320, 320)  # 允许更小的窗口
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Expanding)

    # ---------- 公共接口 ----------
    def set_stone(self, row: int, col: int, data: Optional[Dict[str, Any]]) -> None:
        if not (0 <= row < 19 and 0 <= col < 19):
            return
        self._board[row][col] = data
        self.update()

    def set_board(self, board_data: List[List[Optional[Dict[str, Any]]]]) -> None:
        if len(board_data) != 19 or any(len(row) != 19 for row in board_data):
            raise ValueError("board_data 必须是 19x19 的列表")
        self._board = board_data
        self.update()

    def clear_board(self) -> None:
        self._board = [[None for _ in range(19)] for _ in range(19)]
        self.update()

    # ---------- 绘制 ----------
    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 填充背景
        painter.fillRect(self.rect(), self._bg_color)

        w = self.width()
        h = self.height()
        if w <= 0 or h <= 0:
            return

        # ---- 计算格子大小（严格依赖容器尺寸） ----
        coord_space = min(w, h) * 0.088  # 略微减少坐标空间，使棋盘更大
        available = min(w, h) - 2 * coord_space
        if available < 45:
            available = min(w, h) * 0.74
        cell = available / 18.0
        if cell < 2.5:
            return

        grid_width = 18 * cell
        grid_height = 18 * cell
        start_x = (w - grid_width) / 2.0
        start_y = (h - grid_height) / 2.0

        # ---- 网格线 ----
        pen = QPen(self._grid_color, 1.5)
        painter.setPen(pen)
        for i in range(19):
            y = start_y + i * cell
            painter.drawLine(int(start_x), int(y),
                             int(start_x + 18 * cell), int(y))
            x = start_x + i * cell
            painter.drawLine(int(x), int(start_y),
                             int(x), int(start_y + 18 * cell))

        # ---- 星位 ----
        star_points = [(3,3), (3,9), (3,15),
                       (9,3), (9,9), (9,15),
                       (15,3), (15,9), (15,15)]
        star_radius = max(2.0, cell * 0.055)  # 星位也更小
        painter.setBrush(QBrush(self._star_color))
        painter.setPen(Qt.PenStyle.NoPen)
        for r, c in star_points:
            cx = start_x + c * cell
            cy = start_y + r * cell
            painter.drawEllipse(QPointF(cx, cy), star_radius, star_radius)

        # ---- 坐标标签（系数降低，缩小率更大） ----
        if self._show_coords:
            coord_font_size = max(6, int(cell * 0.258))  # 原0.282 -> 0.258
            coord_font = QFont("Arial", coord_font_size)
            painter.setFont(coord_font)
            painter.setPen(self._coords_color)
            fm = QFontMetrics(coord_font)

            # 顶部数字（从左到右 1~19）
            for i in range(19):
                label = str(i + 1)
                x = start_x + i * cell
                y = start_y - 5
                painter.drawText(int(x - fm.horizontalAdvance(label)/2), int(y), label)

            # 左侧字母（从上到下 A~T，跳过 I）
            for i in range(19):
                label = self.LEFT_LETTERS[i]
                x = start_x - fm.horizontalAdvance(label) - 4
                y = start_y + i * cell + fm.height()//2
                painter.drawText(int(x), int(y), label)

        # ---- 棋子（半径和字体系数降低） ----
        stone_r = max(3, int(cell * 0.410))  # 原0.435 -> 0.410
        # 单行字体大小系数 0.265（原0.290）
        font_large_size = max(6, int(cell * 0.262))
        # 双行字体大小系数 0.218（原0.238）
        font_small_size = max(4, int(cell * 0.215))
        font_large = QFont("Arial", font_large_size)
        font_small = QFont("Arial", font_small_size)

        for r in range(19):
            for c in range(19):
                data = self._board[r][c]
                if data is None:
                    continue
                color_str = data.get('color')
                if not color_str:
                    continue

                color = QColor(color_str)
                if not color.isValid():
                    color = QColor("#FF4444")

                cx = start_x + c * cell
                cy = start_y + r * cell

                # 棋子底色
                painter.setBrush(QBrush(color))
                painter.setPen(QPen(color.darker(142), 1))
                painter.drawEllipse(QPointF(cx, cy), stone_r, stone_r)

                label = data.get('label')
                percent = data.get('percent')
                use_two_rows = (label is not None and percent is not None)

                if use_two_rows:
                    painter.setFont(font_small)
                    tri_size = stone_r * 0.310
                else:
                    painter.setFont(font_large)
                    tri_size = stone_r * 0.430

                painter.setPen(QPen(self._text_color))

                if use_two_rows:
                    half_h = stone_r * 0.590
                    offset = stone_r * 0.115
                    # 上半部分
                    top_rect = QRectF(cx - stone_r,
                                      cy - offset - half_h,
                                      2 * stone_r, half_h)
                    if label == 'A':
                        self._draw_triangle(painter, cx, cy - offset - half_h * 0.45,
                                            tri_size, QColor("#FF0000"))
                    else:
                        painter.drawText(top_rect, Qt.AlignmentFlag.AlignCenter,
                                         str(label))
                    # 下半部分
                    bot_rect = QRectF(cx - stone_r,
                                      cy + offset,
                                      2 * stone_r, half_h)
                    painter.drawText(bot_rect, Qt.AlignmentFlag.AlignCenter,
                                     f"{percent}%")
                elif label is not None:
                    rect = QRectF(cx - stone_r, cy - stone_r,
                                  2 * stone_r, 2 * stone_r)
                    if label == 'A':
                        self._draw_triangle(painter, cx, cy,
                                            tri_size, QColor("#FF0000"))
                    else:
                        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter,
                                         str(label))
                elif percent is not None:
                    rect = QRectF(cx - stone_r, cy - stone_r,
                                  2 * stone_r, 2 * stone_r)
                    painter.drawText(rect, Qt.AlignmentFlag.AlignCenter,
                                     f"{percent}%")

    def _draw_triangle(self, painter: QPainter, cx: float, cy: float,
                       size: float, color: QColor) -> None:
        painter.save()
        painter.setBrush(QBrush(color))
        painter.setPen(Qt.PenStyle.NoPen)
        triangle = QPolygonF([
            QPointF(cx, cy - size),
            QPointF(cx - size * 0.860, cy + size * 0.495),
            QPointF(cx + size * 0.860, cy + size * 0.495),
        ])
        painter.drawPolygon(triangle)
        painter.restore()

    def resizeEvent(self, event) -> None:
        self.update()
        super().resizeEvent(event)