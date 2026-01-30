# 🖥️ DeepSeek Desktop HUD（初版）

一个基于 **Python + PyQt6** 开发的 Windows 桌面悬浮对话挂件（使用DeepSeek API）。它将 DeepSeek 的强大能力无缝集成到您的桌面上，支持透明度调节、流式输出和 Markdown 渲染。

---

## 🛠️ 安装与配置指南

为了保持系统环境整洁，**强烈建议**在虚拟环境中运行本项目。

### 1. 创建虚拟环境 (Virtual Environment)
在项目根目录下，打开终端（CMD 或 PowerShell），依次执行以下命令：

**Windows:**
```powershell
# 创建名为 venv 的虚拟环境
python -m venv venv
或（如果有conda）
conda create -n venv

# 激活虚拟环境 (激活成功后，命令行前会出现 (venv) 字样)
.\venv\Scripts\activate
或
conda activate venv

# 安装依赖包（确保虚拟环境激活后）
pip install -r requirements.txt

# 运行主程序
python HUDWidget.py
```

### 2. 首次配置 (API Key)
程序首次启动时，屏幕中央会弹出 DeepSeek 初始配置 窗口。

请输入您的 API Key（格式通常为 sk- 开头）。

点击 “保存并启动”，程序将进入主界面。

### 3. 界面操作交互
发送消息：在底部输入框输入问题，按 Enter 键发送。

文本换行：按 Shift + Enter 组合键进行换行。

移动窗口：按住窗口内任意空白区域或标题栏即可拖动窗口位置。

调整大小：鼠标移动到窗口右下角，会出现缩放图标，拖动即可调整窗口尺寸。

调节透明度：拖动顶部标题栏右侧的滑块，可调节窗口的不透明度（范围 20% - 100%）。

关闭程序：点击右上角的 × 关闭（程序会自动记忆关闭时的位置和透明度设置）。

### 附录
程序运行后，会自动在同级目录下生成 deepseek_hud_config.json 配置文件，存储apiKey、对话框透明度和对话框大小，内容如下：
```json
{
    "api_key": "sk-xxxxxxxxxxxxxxxx", 
    "opacity": 0.9, 
    "geometry": [100, 100, 400, 600]
}
```