#调试常量
debug = True

##########
#正片开始#
##########

# 常量
BLACK = 1
WHITE = 2
NONE = 0

# 加载日志系统
import logging
import os

log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "Auto_GO.log")

if debug:
    logging.basicConfig(
        level=logging.DEBUG,                     # 输出 INFO 及以上级别的日志
        format="[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d|%H:%M:%S",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_file),
        ]
    )
else:
    logging.basicConfig(
        level=logging.DEBUG,                     # 输出 INFO 及以上级别的日志
        format="[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d|%H:%M:%S",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_file),
        ]
    )
logger = logging.getLogger(__name__)

logger.info("正在初始化~")
#引入错误记录
import core.windows_api.global_traceback

# 导入外部模块
import sys
import os
import ctypes
import win32gui
import win32api
import time

#导入核心模块
import core.ai.go_cv as go_cv
import core.ai.katago as katago
import core.windows_api.capture_window as capture_window
import core.windows_api.v_click as v_click
import core.windows_api.uac as uac
import core.windows_api.get_accent_color as get_accent_color

#导入界面模块
from PyQt6 import QtWidgets
from PyQt6 import QtCore
import gui.go_board as go_board
import gui.go_dialog as go_dialog
from gui.window_select import WindowSelectDialog as window_select
import PyQt6_SwitchControl as SwitchControl

#请求管理
uac.request_uac()

#创建PyQt主循环
app = QtWidgets.QApplication(sys.argv)

# 创建主窗口
window = QtWidgets.QWidget()
window.setWindowTitle("Auto GO 准备")
window.setGeometry(100, 100, 450, 250)

Winmain_Layout = QtWidgets.QVBoxLayout(window)

#KataGO配置部分
katago_set_g = QtWidgets.QGroupBox(title="katago配置")
Winmain_Layout.addWidget(katago_set_g)
katago_set = QtWidgets.QVBoxLayout(katago_set_g)

#kataGO主程序设置
katago_exe_w = QtWidgets.QHBoxLayout()
katago_exe_w.setContentsMargins(10, 4, 10, 4)
katago_exe_w.setSpacing(10)
katago_set.addLayout(katago_exe_w)

katago_exe_label = QtWidgets.QLabel("KataGO可运行主程序:")
katago_exe_edit = QtWidgets.QLineEdit()
katago_exe_edit.setPlaceholderText("请输入KataGO引擎主程序...")
open_katago_exe_btn = QtWidgets.QPushButton("选择文件")

katago_exe_w.addWidget(katago_exe_label)
katago_exe_w.addWidget(katago_exe_edit)
katago_exe_w.addWidget(open_katago_exe_btn)

def on_open_katago_exe_btn_click():
    file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
        parent=window,
        caption="选择一个KataGO实例",
        directory="",
        filter="可运行的文件 (*.exe)"
    )
    katago_exe_edit.setText(file_path) 
open_katago_exe_btn.clicked.connect(on_open_katago_exe_btn_click)


#kataGO模型权重文件设置
katago_mod_w = QtWidgets.QHBoxLayout()
katago_mod_w.setContentsMargins(10, 4, 10, 4)
katago_mod_w.setSpacing(10)
katago_set.addLayout(katago_mod_w)

katago_mod_label = QtWidgets.QLabel("KataGO模型权重文件:")
katago_mod_edit = QtWidgets.QLineEdit()
katago_mod_edit.setPlaceholderText("请输入KataGO模型权重文件...")
open_katago_mod_btn = QtWidgets.QPushButton("选择文件")

katago_mod_w.addWidget(katago_mod_label)
katago_mod_w.addWidget(katago_mod_edit)
katago_mod_w.addWidget(open_katago_mod_btn)

def on_open_katago_mod_btn_click():
    file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
        parent=window,
        caption="选择一个文件作为模型",
        directory="",
        filter="kata权重文件 (*.bin.gz *.txt)"
    )
    katago_mod_edit.setText(file_path) 
open_katago_mod_btn.clicked.connect(on_open_katago_mod_btn_click)


#kataGO模型配置文件设置
katago_cfg_w = QtWidgets.QHBoxLayout()
katago_cfg_w.setContentsMargins(10, 4, 10, 4)
katago_cfg_w.setSpacing(10)
katago_set.addLayout(katago_cfg_w)

katago_cfg_label = QtWidgets.QLabel("KataGO模型配置文件:")
katago_cfg_edit = QtWidgets.QLineEdit()
katago_cfg_edit.setPlaceholderText("请输入KataGO模型配置文件...")
open_katago_cfg_btn = QtWidgets.QPushButton("选择文件")

katago_cfg_w.addWidget(katago_cfg_label)
katago_cfg_w.addWidget(katago_cfg_edit)
katago_cfg_w.addWidget(open_katago_cfg_btn)

def on_open_katago_cfg_btn_click():
    file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
        parent=window,
        caption="选择一个文件作为AI的配置",
        directory="",
        filter="cfg配置文件 (*.cfg);;所有文件 (*)"
    )
    katago_cfg_edit.setText(file_path) 
open_katago_cfg_btn.clicked.connect(on_open_katago_cfg_btn_click)

#提醒
katago_cfg_tip_l = QtWidgets.QHBoxLayout()
katago_cfg_tip_l.setContentsMargins(10, 4, 10, 4)
katago_set.addLayout(katago_cfg_tip_l)
katago_cfg_tip = QtWidgets.QLabel("注意!如果看不懂这是干嘛的请不要修改")
katago_cfg_tip.setStyleSheet("""
    color: red;
""")
katago_cfg_tip_l.addWidget(katago_cfg_tip) 

#三种按钮
katago_cofig_btn = QtWidgets.QHBoxLayout()
katago_cofig_btn.setContentsMargins(10, 4, 10, 4)
katago_cofig_btn.setSpacing(30)
katago_set.addLayout(katago_cofig_btn)

sava_cofig_btn = QtWidgets.QPushButton("保存配置到文件")
run_katago_btn = QtWidgets.QPushButton("运行AI引擎")
stop_katago_btn = QtWidgets.QPushButton("停止AI引擎")
stop_katago_btn.setEnabled(False)

katago_cofig_btn.addWidget(sava_cofig_btn)
katago_cofig_btn.addWidget(run_katago_btn)
katago_cofig_btn.addWidget(stop_katago_btn)


#围棋软件窗口配置
app_set_g = QtWidgets.QGroupBox(title="对弈软件配置")
Winmain_Layout.addWidget(app_set_g)
app_set = QtWidgets.QVBoxLayout(app_set_g)

#选择目标窗口
set_w = QtWidgets.QHBoxLayout()
set_w.setContentsMargins(10, 4, 10, 4)
set_w.setSpacing(10)
app_set.addLayout(set_w)

app_set_label = QtWidgets.QLabel("目标窗口:")
app_set_win_title = QtWidgets.QLabel("点击这里选择窗口----->")
app_set_win_title.setStyleSheet("""
    QLabel {
        border: 2px solid #0078D4;
        border-radius: 5px;
        padding: 8px;
    }
""")
app_set_win_title.setSizePolicy(
    QtWidgets.QSizePolicy.Policy.Expanding,
    QtWidgets.QSizePolicy.Policy.Preferred
)
w_select_btn = QtWidgets.QPushButton("选择窗口")

set_w.addWidget(app_set_label)
set_w.addWidget(app_set_win_title)
set_w.addWidget(w_select_btn)




#算力设置
set_mv = QtWidgets.QHBoxLayout()
set_mv.setContentsMargins(10, 4, 10, 4)
set_mv.setSpacing(10)
app_set.addLayout(set_mv)

set_mv_label = QtWidgets.QLabel("算力(MaxVisit):")
set_mv_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
set_mv_slider.setRange(400, 100000)
set_mv_slider_label = QtWidgets.QLabel("400")
set_mv.addWidget(set_mv_label)
set_mv.addWidget(set_mv_slider)
set_mv.addWidget(set_mv_slider_label)

def set_mv_slider_change(a):
    set_mv_slider_label.setText(str(a))
set_mv_slider.valueChanged.connect(set_mv_slider_change)

#2个按钮,一个开关
app_cofig_btn = QtWidgets.QHBoxLayout()
app_cofig_btn.setContentsMargins(10, 4, 10, 4)
app_cofig_btn.setSpacing(30)
app_set.addLayout(app_cofig_btn)

run_listen_btn = QtWidgets.QPushButton("开启窗口监听")
stop_listen_btn = QtWidgets.QPushButton("关闭窗口监听")
stop_listen_btn.setEnabled(False)
auto_play_sc_w = QtWidgets.QHBoxLayout()
auto_play_sc_w.setSpacing(10)
auto_play_sc_label = QtWidgets.QLabel("自动落子:")
auto_play_sc_w.addWidget(auto_play_sc_label)
auto_play_sc = SwitchControl.SwitchControl()
auto_play_sc.set_active_color(get_accent_color.get_accent_color())
auto_play_sc_w.addWidget(auto_play_sc)

app_cofig_btn.addWidget(run_listen_btn)
app_cofig_btn.addWidget(stop_listen_btn)
app_cofig_btn.addLayout(auto_play_sc_w)

board = go_board.go_board()
Winmain_Layout.addWidget(board)

#逻辑部分
class Main(QtCore.QThread):
    msgbox_warning = QtCore.pyqtSignal(object,str,str)
    msgbox_get_color = QtCore.pyqtSignal(object,object)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.go_engine = None
        self.board = []
        self.w_hwnd = None
        for i in range(0,20):
            self.board.append([])
            for j in range(0,20):
                self.board[i].append(0)
        self.capture = None
        self.gb_cv = go_cv.GoBoardCV()
        self.has_board = False
        self.user_color = WHITE

    def start_gtp(self):
        if not (os.path.exists(katago_exe_edit.text()) and os.path.exists(katago_mod_edit.text()) and os.path.exists(katago_cfg_edit.text())):
            self.msgbox_warning.emit(window,"错误","错误的文件路\n径!")
            return
        run_katago_btn.setEnabled(False)
        run_katago_btn.setText("启动中....")
        window.setWindowTitle("AutoGO - 启动引擎中...")
        QtWidgets.QApplication.processEvents()
        self.go_engine = engine = katago.KataGoGTP(
            katago_path=katago_exe_edit.text(),
            model_path=katago_mod_edit.text(),
            config_path=katago_cfg_edit.text(),
            board_size=19,
            komi=7.5,
            rules="chinese",
            auto_restart=True,
            crash_callback=self.gtp_crash
        )
        run_katago_btn.setText("运行AI引擎")
        stop_katago_btn.setEnabled(True)
        run_listen_btn.setEnabled(True)
        
    def stop_gtp(self):
        if self.capture != None:
            if QtWidgets.QMessageBox.question(window, "确认", "AI引擎停止,监听也将停止,是否确认?",QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No) == QtWidgets.QMessageBox.StandardButton.No:
                return
            else:
                self.stop_listen()
        stop_katago_btn.setEnabled(False)
        run_listen_btn.setEnabled(False)
        self.go_engine.close()
        self.go_engine = None
        run_katago_btn.setEnabled(True)        

    def start_listen(self):
        run_listen_btn.setEnabled(False)
        if self.w_hwnd == None:
            QtWidgets.QMessageBox.information(window, "提示", "请选择一个窗\n口!")
            return
        self.capture = capture_window.CaptureWindow(hwnd = self.w_hwnd)
        stop_listen_btn.setEnabled(True)
    def stop_listen(self):
        stop_listen_btn.setEnabled(False)
        self.capture = None
        self.has_board = False
        run_listen_btn.setEnabled(True)
    def run(self):
        while True:
            time.sleep(0.30)
            if self.go_engine == None:
                continue
            if self.capture == None:
                continue
            w_img = self.capture.capture()
            if w_img is None:
                self.msgbox_warning.emit(window,"错误","监听的窗口消失或最小化了,以自动关闭监听")
                self.stop_listen()
                continue
            if not self.gb_cv.update_board(w_img):
                continue
            if not self.has_board:
                self.has_board = True
                self.msgbox_get_color.emit(window,w_img)
            a,_ = self.gb_cv.recognize()
            change = False
            for i in range(0,19):
                for j in range(0,19):
                    if a[i][j] != self.board[i][j]:
                        self.board[i][j] = a[i][j]
                        change = True
            if not change:
                continue
            
            self.go_engine.set_board_from_array(self.board)
            
            for i in range(0,19):
                for j in range(0,19):
                    if a[i][j] == BLACK:
                        board.set_stone(i,j,{"color":"#000000","label":""})
                    elif a[i][j] == WHITE:
                        board.set_stone(i,j,{"color":"#FFFFFF","label":""})
            #v_click.
    def gtp_crash(self):
        if self.capture == None:
            return
        if QtWidgets.QMessageBox.question(window, "确认", "KataGO崩溃了,是否重启?",QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No) == QtWidgets.QMessageBox.StandardButton.No:
            stop_katago_btn.setEnabled(False)
            self.stop_listen()
            self.go_engine.close()
            self.go_engine = None
            run_katago_btn.setEnabled(True)
            return
        a = self.board
        for i in range(0,19):
            for j in range(0,19):
                if a[i][j] == BLACK:
                    self.go_engine.play_move(i,j,"black")
                elif a[i][j] == WHITE:
                   self.go_engine.play_move(i,j,"white")

    def on_w_select_btn_click(self):
        tmp = window_select.getWindow()
        if tmp is None:
            return
        hwnd = tmp["hwnd"]
        title = tmp["title"]
        if debug:
            title += "[hwnd:"+str(hwnd)+"]"
        if len(title) >= 19:
            title = title[:16:]+"..."
        self.w_hwnd = hwnd
        app_set_win_title.setText(title)

def msgbox_warning(parent,title,text):
    QtWidgets.QMessageBox.warning(parent,title,text)

window.setWindowTitle("AutoGO - 准备中......")
window.show()

run_listen_btn.setEnabled(False)

main = Main()
main.msgbox_warning.connect(msgbox_warning)
main.msgbox_get_color.connect(go_dialog.GoDialog.get_color)
main.start()
w_select_btn.clicked.connect(main.on_w_select_btn_click)
run_katago_btn.clicked.connect(main.start_gtp)
stop_katago_btn.clicked.connect(main.stop_gtp)
run_listen_btn.clicked.connect(main.start_listen)
stop_listen_btn.clicked.connect(main.stop_listen)

window.setWindowTitle("AutoGO - 准备完成!")

#程序退出
sys.exit(app.exec())
