from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QRadioButton, QButtonGroup, QPushButton, QMessageBox
)
from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtCore import Qt
import numpy as np
import cv2

class GoDialog(QDialog):
    """
    弹窗：显示一张图片（numpy array, BGR格式），
    并提供两组单选按钮：用户颜色（黑/白）和当前轮到谁（黑/白）。
    返回 dict: {'my_color': 1/2, 'current_turn': 1/2}
    """
    def __init__(self, parent=None, image_np: np.ndarray = None):
        super().__init__(parent)
        self.setWindowTitle("设置颜色与回合")
        self.setModal(True)
        
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
        # 如果是 BGR 转 RGB
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
    
    @staticmethod
    def get_color(parent=None, image_np: np.ndarray = None) -> dict:
        """
        静态方法：弹出对话框，返回选择结果。
        返回 {'my_color': 1/2, 'current_turn': 1/2}
        如果用户取消则返回 None
        """
        dialog = GoDialog(parent, image_np)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.result_data
        return None

