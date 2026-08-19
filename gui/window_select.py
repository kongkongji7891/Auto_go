import sys
import tempfile
import os
from PyQt6 import QtWidgets
from PyQt6 import QtGui
from PyQt6 import QtCore
import win32gui
import win32con
import win32ui
from PIL import Image
import io

class WindowSelectDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("选择目标窗口")
        self.resize(500, 400)
        self.selected_info = None
        
        layout = QtWidgets.QVBoxLayout(self)
        
        self.list_widget = QtWidgets.QListWidget()
        self.list_widget.setIconSize(QtCore.QSize(32, 32))
        self.list_widget.itemDoubleClicked.connect(self.accept_selection)
        layout.addWidget(self.list_widget)
        
        btn_layout = QtWidgets.QHBoxLayout()
        btn_ok = QtWidgets.QPushButton("确定")
        btn_cancel = QtWidgets.QPushButton("取消")
        btn_ok.clicked.connect(self.accept_selection)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)
        
        self.populate_windows()
    
    @staticmethod
    def getWindow(parent=None):
        """静态方法，弹出窗口选择对话框，返回选中窗口信息或 None"""
        dialog = WindowSelectDialog(parent)
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            return dialog.get_selected_info()
        return None
    
    def populate_windows(self):
        def enum_callback(hwnd, lParam):
            if not win32gui.IsWindowVisible(hwnd):
                return True
            if win32gui.GetWindowText(hwnd) == "":
                return True
            class_name = win32gui.GetClassName(hwnd)
            if class_name in ("Shell_TrayWnd", "Progman", "WorkerW", "DesktopBackground"):
                return True
            
            title = win32gui.GetWindowText(hwnd)
            icon = self.get_window_icon(hwnd)
            
            item = QtWidgets.QListWidgetItem()
            item.setText(title)
            if icon:
                item.setIcon(QtGui.QIcon(icon))
            else:
                item.setIcon(self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_ComputerIcon))
            item.setData(QtCore.Qt.ItemDataRole.UserRole, hwnd)
            item.setData(QtCore.Qt.ItemDataRole.UserRole + 1, icon)
            
            self.list_widget.addItem(item)
            return True
        
        self.list_widget.clear()
        win32gui.EnumWindows(enum_callback, None)
    
    def get_window_icon(self, hwnd):
        try:
            icon_handle = win32gui.SendMessage(hwnd, win32con.WM_GETICON, win32con.ICON_BIG, 0)
            if icon_handle == 0:
                icon_handle = win32gui.SendMessage(hwnd, win32con.WM_GETICON, win32con.ICON_SMALL, 0)
            if icon_handle == 0:
                try:
                    icon_handle = win32gui.GetClassLong(hwnd, win32con.GCL_HICON)
                except AttributeError:
                    pass
            if icon_handle == 0:
                return None
            
            dc = win32ui.CreateDCFromHandle(win32gui.GetDC(0))
            mem_dc = dc.CreateCompatibleDC()
            
            bmp = win32ui.CreateBitmap()
            bmp.CreateCompatibleBitmap(dc, 32, 32)
            mem_dc.SelectObject(bmp)
            
            win32gui.DrawIconEx(mem_dc.GetSafeHdc(), 0, 0, icon_handle, 32, 32, 0, None, win32con.DI_NORMAL)
            
            bmp_info = bmp.GetInfo()
            bmp_str = bmp.GetBitmapBits(True)
            
            img = Image.frombuffer('RGBA', (bmp_info['bmWidth'], bmp_info['bmHeight']), bmp_str, 'raw', 'BGRA', 0, 1)
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            buffer.seek(0)
            pixmap = QtGui.QPixmap()
            pixmap.loadFromData(buffer.read())
            
            win32gui.DeleteObject(bmp.GetHandle())
            mem_dc.DeleteDC()
            dc.DeleteDC()
            
            return pixmap
        except Exception as e:
            print(f"获取图标失败: {e}")
            return None
    
    def accept_selection(self):
        current_item = self.list_widget.currentItem()
        if current_item is None:
            return
        hwnd = current_item.data(QtCore.Qt.ItemDataRole.UserRole)
        icon_pixmap = current_item.data(QtCore.Qt.ItemDataRole.UserRole + 1)
        title = current_item.text()
        self.selected_info = {
            'hwnd': hwnd,
            'title': title,
            'icon': icon_pixmap
        }
        self.accept()
    
    def get_selected_info(self):
        return self.selected_info