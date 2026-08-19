"""
go_dialog.py - 颜色/回合选择弹窗（线程安全版）
支持在任意线程调用 get_color_threadsafe 弹出对话框并等待结果，
底层使用 QMetaObject.invokeMethod 配合 QueuedConnection 将操作派发到主线程。
"""
from __future__ import annotations

import logging
from typing import Optional

import cv2
import numpy as np
from PyQt6.QtCore import (
    QObject, pyqtSignal, pyqtSlot, QMetaObject, Qt,
    Q_ARG, QEventLoop
)
from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QRadioButton, QButtonGroup, QPushButton
)

logger = logging.getLogger(__name__)


# ============================================================
#  辅助类：在主线程创建的 Helper，用于接收跨线程调用
# ============================================================
class _DialogHelper(QObject):
    """必须创建在主线程的辅助对象，用于安全地显示对话框"""
    finished = pyqtSignal(object)  # 携带结果 dict

    @pyqtSlot(object, object)
    def show_dialog(self, parent, image_np: np.ndarray):
        """在主线程中创建并显示对话框，完成后发射 finished 信号"""
        try:
            dialog = GoDialog(parent, image_np)
            dialog.raise_()               # 提升到Z序顶部
            dialog.activateWindow()       # 激活窗口（获得焦点）
            if dialog.exec() == QDialog.DialogCode.Accepted:
                result = dialog.result_data
            else:
                result = None
        except Exception as e:
            logger.exception("显示对话框异常")
            result = None
        self.finished.emit(result)


# ============================================================
#  主对话框类
# ============================================================
class GoDialog(QDialog):
    """
    弹窗：显示一张图片（numpy array, BGR格式），
    并提供两组单选按钮：用户颜色（黑/白）和当前轮到谁（黑/白）。
    返回 dict: {'my_color': 1/2, 'current_turn': 1/2}
    """

    # 类变量：主线程创建的 helper 实例
    _helper: Optional[_DialogHelper] = None

    def __init__(self, parent=None, image_np: np.ndarray = None):
        super().__init__(parent)
        self.setWindowTitle("设置颜色与回合")
        self.setModal(True)
        # 添加置顶标志，使弹窗位于所有窗口之上
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)

        # 存储结果
        self.result_data = {'my_color': 1, 'current_turn': 1}  # 默认黑

        # 主布局
        main_layout = QVBoxLayout(self)

        # 图片显示区域
        if image_np is not None:
            pixmap = self._np_to_pixmap(image_np)
            img_label = QLabel()
            img_label.setPixmap(pixmap.scaled(
                400, 300, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            ))
            img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            main_layout.addWidget(img_label)
        else:
            main_layout.addWidget(QLabel("未提供图片"))

        # 用户颜色选择
        color_group = QHBoxLayout()
        color_label = QLabel("我方颜色：")
        self.rb_black = QRadioButton("执黑")
        self.rb_white = QRadioButton("执白")
        self.rb_black.setChecked(True)  # 默认黑
        self.color_group_btn = QButtonGroup(self)
        self.color_group_btn.addButton(self.rb_black, 1)
        self.color_group_btn.addButton(self.rb_white, 2)
        color_group.addWidget(color_label)
        color_group.addWidget(self.rb_black)
        color_group.addWidget(self.rb_white)
        main_layout.addLayout(color_group)

        # 当前轮到谁选择
        turn_group = QHBoxLayout()
        turn_label = QLabel("当前轮到：")
        self.rb_turn_black = QRadioButton("黑棋")
        self.rb_turn_white = QRadioButton("白棋")
        self.rb_turn_black.setChecked(True)  # 默认黑
        self.turn_group_btn = QButtonGroup(self)
        self.turn_group_btn.addButton(self.rb_turn_black, 1)
        self.turn_group_btn.addButton(self.rb_turn_white, 2)
        turn_group.addWidget(turn_label)
        turn_group.addWidget(self.rb_turn_black)
        turn_group.addWidget(self.rb_turn_white)
        main_layout.addLayout(turn_group)

        # 确认按钮
        confirm_btn = QPushButton("确认")
        confirm_btn.clicked.connect(self._on_confirm)
        main_layout.addWidget(confirm_btn, alignment=Qt.AlignmentFlag.AlignCenter)

    def _np_to_pixmap(self, img: np.ndarray) -> QPixmap:
        """将 BGR numpy 数组转换为 QPixmap"""
        if img.shape[2] == 3:
            rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        else:
            rgb_img = img
        h, w, ch = rgb_img.shape
        bytes_per_line = ch * w
        qimg = QImage(rgb_img.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        return QPixmap.fromImage(qimg)

    def _on_confirm(self):
        """收集结果并关闭"""
        self.result_data['my_color'] = self.color_group_btn.checkedId()
        self.result_data['current_turn'] = self.turn_group_btn.checkedId()
        self.accept()

    # ---------- 线程安全接口 ----------

    @classmethod
    def init_threadsafe(cls):
        """
        必须在主线程（QApplication 所在线程）调用一次。
        创建 _DialogHelper 实例并保存在类变量中。
        """
        if cls._helper is None:
            cls._helper = _DialogHelper()
            logger.debug("GoDialog 线程安全辅助对象已创建")

    @staticmethod
    def get_color_threadsafe(parent, image_np: np.ndarray) -> Optional[dict]:
        """
        线程安全地获取颜色选择。
        可在任意线程（包括子线程）调用，阻塞直到用户做出选择。
        返回 {'my_color': 1/2, 'current_turn': 1/2}，如果用户取消则返回 None。
        """
        helper = GoDialog._helper
        if helper is None:
            raise RuntimeError("请先在主线程调用 GoDialog.init_threadsafe()")

        # 创建事件循环，等待对话框完成
        loop = QEventLoop()
        result_container = [None]

        def on_finished(res):
            result_container[0] = res
            loop.quit()

        helper.finished.connect(on_finished)

        # 使用 QueuedConnection 将任务投递到主线程，不阻塞当前线程
        QMetaObject.invokeMethod(
            helper,
            "show_dialog",
            Qt.ConnectionType.QueuedConnection,
            Q_ARG(object, parent),
            Q_ARG(object, image_np)
        )

        # 进入事件循环，等待 finished 信号
        loop.exec()

        # 断开连接
        try:
            helper.finished.disconnect(on_finished)
        except TypeError:
            pass

        return result_container[0]

    # ---------- 传统同步方法（仅限主线程调用） ----------

    @staticmethod
    def get_color(parent=None, image_np: np.ndarray = None) -> Optional[dict]:
        """
        传统同步方法：必须在主线程调用。
        返回 {'my_color': 1/2, 'current_turn': 1/2}，取消返回 None。
        """
        dialog = GoDialog(parent, image_np)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.result_data
        return None