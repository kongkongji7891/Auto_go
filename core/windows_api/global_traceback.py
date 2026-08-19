import sys
import traceback
from datetime import datetime
from pathlib import Path
from PyQt6.QtWidgets import QMessageBox, QApplication

def global_exception_handler(exc_type, exc_value, exc_traceback):
    """全局异常处理器"""
    # 获取详细堆栈信息
    tb_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
    detail = ''.join(tb_lines)
    
    # 提取关键信息
    tb_list = traceback.extract_tb(exc_traceback)
    if tb_list:
        last_frame = tb_list[-1]
        filename = last_frame.filename
        lineno = last_frame.lineno
        func_name = last_frame.name
        code_line = last_frame.line
    else:
        filename, lineno, func_name, code_line = "未知", 0, "未知", ""
    
    reason = str(exc_value)
    
    # 输出到 stderr
    print("", file=sys.stderr)
    print(f"触发崩溃! 文件: {filename}, 行号: {lineno}, 函数: {func_name}, 原因: {reason}", file=sys.stderr)
    print("请前往 Github 提交错误", file=sys.stderr)
    
    # 生成错误报告文件
    crash_report_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_crash_report.log"
    report_path = Path(__file__).resolve().parent / crash_report_name
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(detail)
        f.write("请前往 Github 提交以上到issues")
        f.write("\n项目地址: https://github.com/kongkongji7891/Auto_go/blob/main/README.md\n")
        f.close()
    
    # 检查是否已有 QApplication 实例
    app = QApplication.instance()
    if app is None:
        # 如果没有，创建一个临时的（仅用于显示消息框）
        app = QApplication(sys.argv)
    
    # 弹出错误对话框
    QMessageBox.critical(
        None,
        "致命错误",
        f"发生未捕获异常!\n\n文件: {filename}\n行号: {lineno}\n函数: {func_name}\n原因: {reason}\n\n"
        f"错误报告已保存至:\n{report_path}\n\n请前往 Github Issues 提交错误报告。"
    )
    
    # 退出程序（不要调用 app.exec()，因为已经在事件循环中或即将退出）
    sys.exit(1)

# 设置全局钩子
sys.excepthook = global_exception_handler
