import sys
import json
import os
import markdown
from pathlib import Path
from openai import OpenAI
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QTextEdit, QPushButton, QSlider, QLabel, QSizeGrip, QLineEdit, QDialog
)
from PyQt6.QtCore import Qt, QPoint, QThread, pyqtSignal, QSize, QEvent
from PyQt6.QtGui import QColor, QPalette, QTextCursor, QIcon

# --- 配置文件管理 ---
CONFIG_FILE = "deepseek_hud_config.json"

def load_config():
    """从本地 JSON 文件加载用户配置"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {"api_key": "", "opacity": 0.9, "geometry": None}

def save_config(config):
    """将 API Key、透明度和窗口位置保存到本地"""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f)

# --- API 工作线程 ---
class DeepSeekWorker(QThread):
    """
    处理 API 网络请求的子线程，防止界面卡死。
    """
    token_received = pyqtSignal(str) # 收到新 token 时触发
    finished = pyqtSignal(str)       # 回复生成完毕时触发，传递完整文本
    error_occurred = pyqtSignal(str) # 发生错误时触发

    def __init__(self, api_key, chat_history): 
        super().__init__()
        self.api_key = api_key
        self.chat_history = chat_history 
        self.client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        self.full_content = ""

    def run(self):
        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=self.chat_history,
                stream=True
            )
            for chunk in response:
                if chunk.choices[0].delta.content:
                    token = chunk.choices[0].delta.content
                    self.full_content += token
                    self.token_received.emit(token)
            
            # 发送完整内容用于 Markdown 最终渲染
            self.finished.emit(self.full_content)
            
        except Exception as e:
            self.error_occurred.emit(str(e))

# --- API Key 输入对话框 ---
class APIKeyDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DeepSeek 初始配置")
        self.setFixedSize(350, 150)
        
        layout = QVBoxLayout()
        self.label = QLabel("请输入您的 DeepSeek API Key:")
        self.input = QLineEdit()
        self.input.setEchoMode(QLineEdit.EchoMode.Password)
        self.input.setPlaceholderText("sk-...")
        
        self.btn = QPushButton("保存并启动")
        self.btn.clicked.connect(self.accept)
        
        layout.addWidget(self.label)
        layout.addWidget(self.input)
        layout.addWidget(self.btn)
        self.setLayout(layout)

# --- 主 HUD 窗口 ---
class DeepSeekHUD(QMainWindow):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.old_pos = None 
        self.history = [{"role": "system", "content": "You are a helpful assistant."}] 
        self.current_worker = None
        self.temp_response_buffer = "" # 用于暂存流式输出的纯文本

        # 1. 窗口样式设置
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |      
            Qt.WindowType.WindowStaysOnTopHint |     
            Qt.WindowType.Tool                        
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.init_ui()
        self.apply_styles()
        self.restore_settings()

    def init_ui(self):
        # 主容器
        self.container = QWidget()
        self.container.setObjectName("MainContainer")
        self.setCentralWidget(self.container)
        
        main_layout = QVBoxLayout(self.container)
        main_layout.setContentsMargins(15, 10, 15, 10)
        main_layout.setSpacing(5)

        # 顶部栏
        header = QHBoxLayout()
        self.title_label = QLabel("DEEPSEEK HUD")
        self.title_label.setObjectName("TitleLabel")
        
        # 透明度滑块
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(20, 100)
        self.opacity_slider.setValue(int(self.config.get("opacity", 0.9) * 100))
        self.opacity_slider.setFixedWidth(80)
        self.opacity_slider.valueChanged.connect(self.update_opacity)
        
        self.close_btn = QPushButton("×")
        self.close_btn.setFixedSize(25, 25)
        self.close_btn.clicked.connect(self.close_app) # 使用自定义关闭方法
        self.close_btn.setObjectName("CloseBtn")

        header.addWidget(self.title_label)
        header.addStretch()
        header.addWidget(QLabel("◐"))
        header.addWidget(self.opacity_slider)
        header.addWidget(self.close_btn)
        
        # [修改] 对话显示区域
        self.display = QTextEdit()
        self.display.setReadOnly(True)
        self.display.setPlaceholderText("Ready...")
        self.display.setObjectName("ChatDisplay")
        
        # 输入区域
        self.input_field = QTextEdit()
        self.input_field.setPlaceholderText("Enter发送, Shift+Enter换行...")
        self.input_field.setMaximumHeight(80)
        self.input_field.setObjectName("InputField")
        self.input_field.installEventFilter(self) # 必须安装过滤器才能捕捉 Enter

        main_layout.addLayout(header)
        main_layout.addWidget(self.display, stretch=4)
        main_layout.addWidget(self.input_field, stretch=1)

        # 调整大小的手柄
        self.grip = QSizeGrip(self)
        self.grip.setStyleSheet("background: transparent;")
        # 将 Grip 放置在右下角 (布局外绝对定位)
        self.grip.resize(20, 20) 

    def resizeEvent(self, event):
        # 保持 Grip 始终在右下角
        rect = self.rect()
        self.grip.move(rect.right() - 20, rect.bottom() - 20)
        super().resizeEvent(event)

    def apply_styles(self):
        """设置 QSS 样式表"""
        self.setStyleSheet("""
            #MainContainer {
                background-color: rgba(20, 20, 20, 220); 
                border: 1px solid rgba(255, 255, 255, 30);
                border-radius: 12px;
            }
            #TitleLabel {
                color: #00ffcc;
                font-weight: bold;
                font-family: 'Segoe UI', sans-serif;
            }
            #ChatDisplay {
                background: transparent;
                border: none;
                color: #e0e0e0;
                font-family: 'Segoe UI', sans-serif;
                font-size: 13px;
                padding: 5px;
            }
            #InputField {
                background: rgba(255, 255, 255, 20);
                border: 1px solid rgba(255, 255, 255, 30);
                border-radius: 8px;
                color: white;
                padding: 5px;
                font-family: 'Segoe UI';
            }
            #CloseBtn {
                background: transparent;
                color: #aaa;
                border: none;
                font-size: 18px;
                font-weight: bold;
            }
            #CloseBtn:hover { color: #ff5555; }
            
            /* [修改] 滚动条优化：暗轨亮块 */
            QScrollBar:vertical {
                border: none;
                background: transparent; /* 轨道完全透明 */
                width: 6px;              /* 稍微加宽一点方便点击 */
                margin: 0px 0px 0px 0px;
            }
            QScrollBar::handle:vertical {
                background: rgba(255, 255, 255, 120); /* 滑块高亮半透明 */
                min-height: 20px;
                border-radius: 3px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
        """)

    # --- 逻辑处理 ---
    def update_opacity(self, value):
        alpha = value / 100.0
        self.setWindowOpacity(alpha)
        self.config["opacity"] = alpha

    def eventFilter(self, obj, event):
        if obj is self.input_field and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Return:
                if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    # Shift+Enter: 允许换行，不拦截
                    return False
                else:
                    # Enter: 发送消息
                    self.send_message()
                    return True # 拦截事件，不让 TextEdit 换行
        return super().eventFilter(obj, event)

    def send_message(self):
        text = self.input_field.toPlainText().strip()
        if not text:
            return

        # 显示用户消息（气泡样式）
        self.append_user_message(text)
        self.input_field.clear()

        # 更新历史
        self.history.append({"role": "user", "content": text})
        # 简单的历史截断，防止 token 溢出
        if len(self.history) > 10:
             # 保留 system prompt (index 0) 和最近的 9 条
            self.history = [self.history[0]] + self.history[-9:]

        # 准备接收 AI 回复
        self.temp_response_buffer = "" # 清空缓冲区
        # 预先插入一个空的 AI 回复容器，稍后流式填充
        self.start_ai_message_block()

        # 启动线程
        self.current_worker = DeepSeekWorker(self.config["api_key"], self.history)
        self.current_worker.token_received.connect(self.update_chat_stream)
        self.current_worker.finished.connect(self.render_final_message)
        self.current_worker.error_occurred.connect(self.handle_error)
        self.current_worker.start()

    def append_user_message(self, text):
        """[修改] 用户消息：标签和内容都在同一个绿色气泡内，整体右对齐"""
        safe_text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
        
        html = f"""
        <div align="right" style="margin-bottom: 10px;">
            <div style="background-color: rgba(0, 200, 150, 60); 
                        color: white; 
                        padding: 10px 12px; 
                        border-radius: 12px; 
                        text-align: left;">
                <div style="color: rgba(255, 255, 255, 0.7); font-size: 10px; font-weight: bold; margin-bottom: 4px;">用户:</div>
                <div style="font-size: 13px; line-height: 1.4;">{safe_text}</div>
            </div>
        </div>
        """
        self.display.append(html)
        self.scroll_to_bottom()

    def start_ai_message_block(self):
        """AI 开始：DeepSeek 标签独立，正文无背景"""
        self.display.append("") # 空行增加间距

        self.display.insertHtml("""
            <div>
                DeepSeek:
            </div>
        """)
        
        # 正文容器：移除了 style 中的 color 设置，让其继承全局，且不设背景
        self.display.insertHtml("<div>")

    def update_chat_stream(self, token):
        """流式追加纯文本"""
        self.temp_response_buffer += token
        
        cursor = self.display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(token)
        self.display.setTextCursor(cursor)
        self.scroll_to_bottom()

    def render_final_message(self, full_content):
        """对话结束，将刚才的纯文本替换为 Markdown 渲染后的 HTML"""
        html_content = markdown.markdown(full_content, extensions=['fenced_code', 'nl2br'])
        
        # 获取当前的 Cursor
        cursor = self.display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        
        self.history.append({"role": "assistant", "content": full_content})
        
        cursor = self.display.textCursor()
        
        self.refresh_display_with_markdown()

    def refresh_display_with_markdown(self):
        """最终渲染：用户有绿框，DeepSeek 无背景框"""
        self.display.clear()
        for msg in self.history:
            if msg["role"] == "system": continue
            
            content = msg["content"]
            
            if msg["role"] == "user":
                # 复用上面的用户气泡逻辑
                self.append_user_message(content)
            else:
                # AI 回复：Markdown 渲染
                html_body = markdown.markdown(content, extensions=['fenced_code', 'nl2br'])
                
                # 结构：DeepSeek 标签 + 无背景的正文
                wrapper = f"""
                <div style="margin-bottom: 20px;">
                    <div style="margin-bottom: 5px;">
                        <span font-size: 14px; font-weight: bold;">DeepSeek:</span>
                    </div>
                    
                    <div style="color: #e0e0e0; 
                                padding-left: 2px;
                                line-height: 1.5;">
                        {html_body}
                    </div>
                </div>
                """
                self.display.append(wrapper)
        
        self.scroll_to_bottom()

    def handle_error(self, error_msg):
        self.display.append(f"<div style='color:#ff5555; text-align:center; margin:10px;'>⚠️ {error_msg}</div>")

    def scroll_to_bottom(self):
        vertical_bar = self.display.verticalScrollBar()
        vertical_bar.setValue(vertical_bar.maximum())

    # --- 窗口拖拽与关闭 ---
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # 只有点在背景上才拖动，避免影响 TextEdit 选择
            if self.childAt(event.position().toPoint()) is None or \
               self.childAt(event.position().toPoint()) is self.container:
                self.old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self.old_pos is not None:
            delta = QPoint(event.globalPosition().toPoint() - self.old_pos)
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self.old_pos = None

    def restore_settings(self):
        self.setWindowOpacity(self.config.get("opacity", 0.9))
        if self.config.get("geometry"):
            self.setGeometry(*self.config["geometry"])
        else:
            self.resize(400, 600)

    def close_app(self):
        geom = self.geometry()
        self.config["geometry"] = [geom.x(), geom.y(), geom.width(), geom.height()]
        save_config(self.config)
        
        if self.current_worker and self.current_worker.isRunning():
            self.current_worker.terminate()
            self.current_worker.wait()
        
        QApplication.quit()
        sys.exit(0)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    current_config = load_config()
    
    if not current_config.get("api_key"):
        dialog = APIKeyDialog()
        if dialog.exec() == QDialog.DialogCode.Accepted:
            current_config["api_key"] = dialog.input.text().strip()
            save_config(current_config)
        else:
            sys.exit()

    hud = DeepSeekHUD(current_config)
    hud.show()
    sys.exit(app.exec())