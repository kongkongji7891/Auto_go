"""
safe_dialog.py - 线程安全的 Qt 弹窗封装
支持 QMessageBox、QInputDialog、QFileDialog 等常用弹窗。
所有方法可在任意线程调用，弹窗始终在主线程显示。
"""
from PyQt6.QtCore import QObject, pyqtSignal, QThread, QEventLoop, QMutex
from PyQt6.QtWidgets import (
    QMessageBox, QInputDialog, QFileDialog, QWidget, QLineEdit
)
from typing import Optional, Any, List, Tuple

class _Request:
    """内部请求结构体"""
    def __init__(self, method_name: str, args: tuple, kwargs: dict):
        self.method_name = method_name
        self.args = args
        self.kwargs = kwargs
        self.result: Any = None
        self.event = QEventLoop()


class theard_dialog(QObject):
    """线程安全的弹窗单例"""
    _instance = None
    _mutex = QMutex()
    _request_signal = pyqtSignal(object)  # 传递 _Request 对象

    def __new__(cls):
        cls._mutex.lock()
        try:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._init()
            return cls._instance
        finally:
            cls._mutex.unlock()

    def _init(self):
        super().__init__()
        self._queue = []           # 请求队列
        self._queue_mutex = QMutex()
        self._request_signal.connect(self._on_request)

    # ---------- 公开 API ----------
    # ---- QMessageBox ----
    def information(self, parent: Optional[QWidget], title: str, text: str,
                    buttons=QMessageBox.StandardButton.Ok,
                    defaultButton=QMessageBox.StandardButton.NoButton) -> QMessageBox.StandardButton:
        return self._call('information', parent, title, text, buttons, defaultButton)

    def question(self, parent: Optional[QWidget], title: str, text: str,
                 buttons=QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                 defaultButton=QMessageBox.StandardButton.NoButton) -> QMessageBox.StandardButton:
        return self._call('question', parent, title, text, buttons, defaultButton)

    def warning(self, parent: Optional[QWidget], title: str, text: str,
                buttons=QMessageBox.StandardButton.Ok,
                defaultButton=QMessageBox.StandardButton.NoButton) -> QMessageBox.StandardButton:
        return self._call('warning', parent, title, text, buttons, defaultButton)

    def critical(self, parent: Optional[QWidget], title: str, text: str,
                 buttons=QMessageBox.StandardButton.Ok,
                 defaultButton=QMessageBox.StandardButton.NoButton) -> QMessageBox.StandardButton:
        return self._call('critical', parent, title, text, buttons, defaultButton)

    def about(self, parent: Optional[QWidget], title: str, text: str) -> None:
        return self._call('about', parent, title, text)

    # ---- QInputDialog ----
    def getText(self, parent: Optional[QWidget], title: str, label: str,
                text: str = "", echo=QLineEdit.EchoMode.Normal,
                flags=None) -> Tuple[bool, str]:
        return self._call('getText', parent, title, label, text, echo)

    def getInt(self, parent: Optional[QWidget], title: str, label: str,
               value: int = 0, min: int = -2147483647, max: int = 2147483647,
               step: int = 1) -> Tuple[bool, int]:
        return self._call('getInt', parent, title, label, value, min, max, step)

    def getDouble(self, parent: Optional[QWidget], title: str, label: str,
                  value: float = 0.0, min: float = -2147483647, max: float = 2147483647,
                  decimals: int = 1) -> Tuple[bool, float]:
        return self._call('getDouble', parent, title, label, value, min, max, decimals)

    def getItem(self, parent: Optional[QWidget], title: str, label: str,
                items: List[str], current: int = 0, editable: bool = True) -> Tuple[bool, str]:
        return self._call('getItem', parent, title, label, items, current, editable)

    # ---- QFileDialog ----
    def getOpenFileName(self, parent: Optional[QWidget], caption: str = "",
                        directory: str = "", filter: str = "",
                        initialFilter: str = "") -> Tuple[str, str]:
        return self._call('getOpenFileName', parent, caption, directory, filter, initialFilter)

    def getSaveFileName(self, parent: Optional[QWidget], caption: str = "",
                        directory: str = "", filter: str = "",
                        initialFilter: str = "") -> Tuple[str, str]:
        return self._call('getSaveFileName', parent, caption, directory, filter, initialFilter)

    def getExistingDirectory(self, parent: Optional[QWidget], caption: str = "",
                             directory: str = "",
                             options=QFileDialog.Option.ShowDirsOnly) -> str:
        return self._call('getExistingDirectory', parent, caption, directory, options)

    # ---------- 内部机制 ----------
    def _call(self, method_name: str, *args, **kwargs) -> Any:
        """在任何线程中调用，返回弹窗结果"""
        req = _Request(method_name, args, kwargs)
        # 将请求放入队列
        self._queue_mutex.lock()
        try:
            self._queue.append(req)
        finally:
            self._queue_mutex.unlock()
        # 通过信号唤醒主线程处理队列
        self._request_signal.emit(None)
        # 阻塞等待结果
        req.event.exec()
        return req.result

    def _on_request(self, _):
        """主线程槽函数：处理队列中的所有请求"""
        while True:
            self._queue_mutex.lock()
            try:
                if not self._queue:
                    break
                req = self._queue.pop(0)
            finally:
                self._queue_mutex.unlock()
            # 根据方法名调用对应的静态函数
            if req.method_name in ('information', 'question', 'warning', 'critical'):
                func = getattr(QMessageBox, req.method_name)
                req.result = func(*req.args, **req.kwargs)
            elif req.method_name == 'about':
                func = getattr(QMessageBox, req.method_name)
                func(*req.args, **req.kwargs)
                req.result = None
            elif req.method_name in ('getText', 'getInt', 'getDouble', 'getItem'):
                func = getattr(QInputDialog, req.method_name)
                req.result = func(*req.args, **req.kwargs)
            elif req.method_name in ('getOpenFileName', 'getSaveFileName', 'getExistingDirectory'):
                func = getattr(QFileDialog, req.method_name)
                req.result = func(*req.args, **req.kwargs)
            else:
                raise ValueError(f"未知弹窗方法: {req.method_name}")
            # 通知等待的线程
            req.event.quit()