import sys
import time
import json
import wave
import pyaudio
import requests
import os
import platform
from PyQt5 import QtWidgets, QtGui, QtCore
from openai import OpenAI
import pygame  # 用于音频播放
from urllib.parse import urlencode
# 在导入部分添加
from urllib.parse import quote_plus
from urllib.request import Request, urlopen
import traceback

# 获取桌面路径并创建专用文件夹
def get_desktop_path():
    system = platform.system()
    if system == "Windows":
        return os.path.join(os.environ['USERPROFILE'], 'Desktop')
    else:  # macOS/Linux
        return os.path.join(os.path.expanduser("~"), 'Desktop')

DESKTOP_PATH = get_desktop_path()
RECORD_FOLDER = os.path.join(DESKTOP_PATH, "AI_Doctor_Records")

# 创建文件夹（如果不存在）
os.makedirs(RECORD_FOLDER, exist_ok=True)

# 在API密钥下方添加
BAIDU_TTS_URL = 'https://tsn.baidu.com/text2audio'
# API key should be configured properly in production
API_KEY = "Your DeepSeek API key"  # Replace with actual API key
BAIDU_API_KEY = 'Your Baidu API key'       # 百度云应用的 API Key
BAIDU_SECRET_KEY = 'Your Baidu Secret key' # 百度云应用的 Secret Key

class VoiceInputThread(QtCore.QThread):
    recognized = QtCore.pyqtSignal(str)
    error = QtCore.pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.audio = pyaudio.PyAudio()
        self.format = pyaudio.paInt16
        self.channels = 1
        self.rate = 16000
        self.chunk = 1024
        self.frames = []
        self.is_recording = False  # Flag to control recording

    def run(self):
        try:
            # 开始录音
            stream = self.audio.open(format=self.format, channels=self.channels,
                                     rate=self.rate, input=True,
                                     frames_per_buffer=self.chunk)
            self.frames = []
            print("录音中...")
            self.is_recording = True  # Set recording flag to True

            while self.is_recording: # Loop until recording is stopped externally
                data = stream.read(self.chunk)
                self.frames.append(data)

            stream.stop_stream()
            stream.close()

            # 保存临时文件
            temp_wav_path = os.path.join(RECORD_FOLDER, "temp.wav")
            with wave.open(temp_wav_path, 'wb') as wf:
                wf.setnchannels(self.channels)
                wf.setsampwidth(self.audio.get_sample_size(self.format))
                wf.setframerate(self.rate)
                wf.writeframes(b''.join(self.frames))

            # 调用百度API识别
            text = self.recognize()
            self.recognized.emit(text)

        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.is_recording = False # Ensure flag is reset even if error occurs

    def stop_recording(self):
        """外部调用此方法停止录音"""
        self.is_recording = False

    def recognize(self):
        url = "https://vop.baidu.com/pro_api"
        headers = {'Content-Type': 'audio/wav; rate=16000'}

        # 使用实例变量获取路径
        temp_wav_path = os.path.join(RECORD_FOLDER, "temp.wav")

        with open(temp_wav_path, 'rb') as f:  # 修改这一行
            audio_data = f.read()

        params = {
            'dev_pid': 80001,
            'cuid': 'Dr0EoRPnloi2i3y95HsDGoTFzxXCbVoS',
            'token': get_access_token()
        }

        response = requests.post(url, params=params, headers=headers, data=audio_data)
        result = response.json()

        if 'result' in result:
            return ''.join(result['result'])
        else:
            raise Exception(f"识别错误: {result.get('err_msg', '未知错误')}")

class VoiceOutputThread(QtCore.QThread):
    finished = QtCore.pyqtSignal()
    error = QtCore.pyqtSignal(str)

    def __init__(self, text, parent=None):  # 添加 parent 参数
        super().__init__(parent)  # 将 parent 传递给基类
        self.text = text
        self.clock = pygame.time.Clock()  # 用于控制播放间隔

    def run(self):
        try:
            token = get_access_token()
            if not token:
                raise Exception("无法获取百度API访问令牌")

            params = {
                'tok': token,
                'tex': quote_plus(self.text),
                'cuid': 'EvjZYE1gVNRytjtoQEsXMVq2SUzu6qSi',
                'ctp': 1,
                'lan': 'zh',
                'spd': 5,
                'pit': 5,
                'vol': 7,
                'per': 1,
                'aue': 3
            }

            data = urlencode(params).encode('utf-8')
            req = Request(BAIDU_TTS_URL, data=data)
            req.add_header('Content-Type', 'application/x-www-form-urlencoded')

            with urlopen(req, timeout=10) as f:
                audio_data = f.read()
                if not audio_data:
                    raise Exception("未获取到音频数据")

                if f.headers.get('Content-Type', '').startswith('application/json'):
                    error_info = json.loads(audio_data.decode())
                    raise Exception(f"语音合成失败: {error_info.get('err_msg', '未知错误')}")

                temp_mp3_path = os.path.join(RECORD_FOLDER, "temp.mp3")
                with open(temp_mp3_path, 'wb') as f_audio:
                    f_audio.write(audio_data)

                # 使用 pygame.mixer.Sound 播放
                sound = pygame.mixer.Sound(temp_mp3_path)
                sound.play()

                # 等待播放完成 (使用 clock)
                while pygame.mixer.get_busy():
                    self.clock.tick(10)  # 每秒检查 10 次

                self.finished.emit()

        except Exception as e:
            error_message = f"语音合成错误: {e}\n{traceback.format_exc()}"  # 包含堆栈跟踪
            self.error.emit(error_message)
            print(error_message)  # 同时也打印到控制台


    def play_audio(self, filename):
        p = pyaudio.PyAudio()
        with wave.open(filename, 'rb') as wf:
            stream = p.open(format=p.get_format_from_width(wf.getsampwidth()),
                            channels=wf.getnchannels(),
                            rate=wf.getframerate(),
                            output=True)
            data = wf.readframes(1024)
            while data:
                stream.write(data)
                data = wf.readframes(1024)
            stream.stop_stream()
            stream.close()
        p.terminate()

def get_access_token():
    """获取百度API访问令牌"""
    url = "https://aip.baidubce.com/oauth/2.0/token"
    params = {
        "grant_type": "client_credentials",
        "client_id": BAIDU_API_KEY,
        "client_secret": BAIDU_SECRET_KEY
    }
    return str(requests.post(url, params=params).json().get("access_token"))

class ChatBubble(QtWidgets.QWidget):
    """
    聊天气泡控件：
      - 根据 sender 参数（"user" 或 "assistant"）决定头像、气泡排列方式和对齐方向，
    """

    def __init__(self, sender, message, parent=None):
        super().__init__(parent)
        self.sender = sender  # "user" 表示患者, "assistant" 表示机器人医生
        self.message = message
        self.setup_ui()

    def setup_ui(self):
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # 头像
        avatar_label = QtWidgets.QLabel(self)
        avatar_size = 40
        # 使用 sys._MEIPASS 获取资源路径
        if getattr(sys, 'frozen', False):
            # 应用程序已打包
            base_path = sys._MEIPASS
        else:
            # 应用程序未打包（开发模式）
            base_path = os.path.dirname(__file__)  # 或者 os.path.abspath(".")

        if self.sender == "user":
            avatar_path = os.path.join(base_path, "avatars", "user_avatar.jpg")
        else:
            avatar_path = os.path.join(base_path, "avatars", "robot_avatar.jpg")

        pixmap = QtGui.QPixmap(avatar_path)

        if pixmap.isNull():
            # 如果头像文件不存在，绘制简单圆形代替
            pixmap = QtGui.QPixmap(avatar_size, avatar_size)
            pixmap.fill(QtCore.Qt.transparent)
            painter = QtGui.QPainter(pixmap)
            painter.setRenderHint(QtGui.QPainter.Antialiasing)
            if self.sender == "user":
                painter.setBrush(QtGui.QColor("#A5D6A7"))
            else:
                painter.setBrush(QtGui.QColor("#90CAF9"))
            painter.drawEllipse(0, 0, avatar_size, avatar_size)
            painter.end()
        avatar_label.setPixmap(
            pixmap.scaled(avatar_size, avatar_size, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        )

        # 消息气泡（使用 QLabel 显示文本）
        bubble_label = QtWidgets.QLabel(self.message, self)
        bubble_label.setWordWrap(True)
        font = bubble_label.font()
        font.setPointSize(12)  # 放大字体
        bubble_label.setFont(font)
        bubble_label.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)

        # 根据发送者设置气泡样式，模拟微信风格
        if self.sender == "assistant":
            # 机器人消息：左侧显示，白色气泡，带边框
            bubble_label.setStyleSheet(
                "background-color: #ffffff; padding:10px; border: 1px solid #ddd; border-radius:10px;"
            )
        else:
            # 患者消息：右侧显示，绿色气泡
            bubble_label.setStyleSheet(
                "background-color: #dcf8c6; padding:10px; border-radius:10px;"
            )

        spacer = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)

        if self.sender == "assistant":
            # 机器人：头像在左，文本靠左
            layout.addWidget(avatar_label)
            layout.addWidget(bubble_label)
            layout.addItem(spacer)
        else:
            # 患者：文本靠右，头像在右
            layout.addItem(spacer)
            layout.addWidget(bubble_label)
            layout.addWidget(avatar_label)

        self.setLayout(layout)

class MedicalRecordThread(QtCore.QThread):
    recordReady = QtCore.pyqtSignal(str, str)  # filename, content
    recordError = QtCore.pyqtSignal(str)  # error message

    def __init__(self, client, conversation_history):
        super().__init__()
        self.client = client
        self.conversation_history = conversation_history

    def run(self):
        try:
            # Construct message sequence for the API
            messages = [
                {"role": "system",
                 "content": "你是一位AI医生助手，擅长生成结构化的患者病历，请按以下格式记录：1. 基本信息：包括患者的姓名、性别、年龄、民族、婚姻状况、职业、籍贯、现居住地、入院日期和记录日期。2. 主诉：简明扼要地记录患者此次就诊的主要症状、持续时间。3. 现病史：详细记录本次疾病的发生、演变和诊疗等情况。4. 既往史：既往健康状况及疾病史，包括高血压、糖尿病、心脏病、肝炎等。过敏史，预防接种史，输血史，手术外伤史，传染病史等。5. 个人史：记录患者本人的成长环境，包括生活条件、饮食、嗜好、居住与工作环境，精神状态等，其他成员的情况不应被纳入。6. 婚姻史：婚姻情况、配偶的健康状况、夫妻关系等7. 月经及生育史：如果患者为女性,应记录月经史，及月经初潮年龄、月经周期和经期天数、经血的量和色、经期症状、末次月经时间及闭经年龄，同时应记录生育史，包括妊娠与生育胎次、人工或自然流产史等。注意男性患者应删除这一内容，若患者未说明性别，可在此处记录性别不明。8. 家族史：此处应记录患者家族成员的患病情况，包括直系亲属的健康状况、疾病症状或死亡原因，有无遗传病、家族性疾病及传染病等情况。请帮我根据下列患者的叙述生成一份结构化入院记录，并且在病历的最后，给医生和患者对患者的拟诊断和建议的检查与治疗等："}
            ]

            # Add conversation history
            for role, message in self.conversation_history[:-1]:
                api_role = "assistant" if role == "assistant" else "user"
                messages.append({"role": api_role, "content": message})

            # Add final prompt
            messages.append({"role": "user", "content": "请根据以上对话生成一份结构化的患者病历。"})

            # Display the sent prompt
            print("发送请求到 DeepSeek API...")
            print("发送的Prompt 如下:", messages)

            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                temperature=0.2,
                max_tokens=4000,
                stream=False
            )

            medical_record = response.choices[0].message.content

            timestamp = time.strftime("%Y%m%d-%H%M%S")
            filename = os.path.join(RECORD_FOLDER, f"medical_record_{timestamp}.md")
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(medical_record)

            self.recordReady.emit(filename, medical_record)

        except Exception as e:
            print(f"生成病历错误: {e}")
            self.recordError.emit(str(e))

class ChatWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        pygame.init()  # 添加此行初始化pygame
        self.setWindowTitle("肺结节筛查对话Demo - DeepSeek API")
        self.resize(1280, 720)
        pygame.mixer.init()  # 初始化 pygame.mixer
        # Add a flag to track if user is in supplement mode
        self.in_supplement_mode = False
        self.is_voice_recording = False # Flag to track voice recording state
        self.voice_input_thread = None # To hold the voice input thread
        self.current_voice_thread = None  # 存储当前语音线程

        # 主布局
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # 聊天显示区域：使用 QScrollArea + 垂直布局显示每条聊天气泡
        self.scroll_area = QtWidgets.QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.chat_widget = QtWidgets.QWidget()
        self.chat_layout = QtWidgets.QVBoxLayout(self.chat_widget)
        self.chat_layout.setAlignment(QtCore.Qt.AlignTop)
        self.scroll_area.setWidget(self.chat_widget)
        main_layout.addWidget(self.scroll_area)

        # 输入区域：文本输入框和按钮
        input_layout = QtWidgets.QHBoxLayout()
        self.user_input = QtWidgets.QLineEdit(self)
        self.user_input.setFont(QtGui.QFont("", 14))
        input_layout.addWidget(self.user_input)

        # 绿色、椭圆形的发送按钮
        self.btn_send = QtWidgets.QPushButton("发送", self)
        self.btn_send.setFont(QtGui.QFont("", 14))
        self.btn_send.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 15px;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)

        # 绿色、椭圆形的语音输入按钮
        self.btn_voice = QtWidgets.QPushButton("语音输入", self)
        self.btn_voice.setFont(QtGui.QFont("", 14))
        self.btn_voice.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 15px;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)

        input_layout.addWidget(self.btn_send)
        input_layout.addWidget(self.btn_voice)
        main_layout.addLayout(input_layout)

        self.setLayout(main_layout)

        # 绑定按钮事件
        self.btn_send.clicked.connect(self.on_send_text)
        self.btn_voice.clicked.connect(self.on_voice_input)

        # 存储对话内容（列表记录每条消息）
        self.conversation_history = []

        # 医患对话逻辑：待提问问题清单（依次弹出）
        self.questions = [
            "好的，请问您是什么时候开始发现有肺结节的？做过哪些检查？",
            "您是否记得结节位于主要在肺的哪个部位？你过去随访过程中结节是否有变化，是否曾就医治疗？",
            "您过去有没有患过高血压、糖尿病这一类的慢性疾病，或者对什么药物或物质有过敏反应？是否接受过大型手术？",
            "您平时是否抽烟或者饮酒？具体频率如何？另外，您近期饮食、睡眠如何，是否有不舒服的情况？",
            "好的，感谢您的配合！最后，请问您的爱人、子女以及亲戚朋友中有没有类似情况的健康问题？",
            "好的，我已经大概搜集好您的情况，您是否有需要补充的？请您告诉我。"
        ]
        self.current_question_index = 0

        # 程序启动后，机器人先发送初始消息
        # 初始消息应分成四个气泡
        self.add_robot_message("您好，我是筛查机器人医生，负责采集您的一些信息，我将就您肺结节的情况向您咨询一些问题，请您配合我。下面，我们开始。首先，请提供您的姓名、年龄、性别以及手机联系方式。")

        try:
            print("初始化 DeepSeek API 客户端...")
            self.client = OpenAI(api_key=API_KEY, base_url="https://api.deepseek.com")
            print("API 客户端初始化完成")
        except Exception as e:
            print(f"API 客户端初始化失败: {e}")
            self.add_robot_message("API 客户端初始化失败，仅显示界面")

    def add_user_message(self, message):
        """添加患者消息"""
        bubble = ChatBubble("user", message)
        self.chat_layout.addWidget(bubble)
        self.conversation_history.append(("user", message))
        self.scroll_to_bottom()  # 自动滚动到底部

        # 回答后自动发送下一条待提问问题
        if len(self.questions) > self.current_question_index:
            next_question = self.questions[self.current_question_index]
            self.current_question_index += 1
            self.add_robot_message(next_question)
            # 当最后一个问题为补充信息时，等待用户回复触发病历生成
            if self.current_question_index == len(self.questions):
                pass

    def add_robot_message(self, message):
        """添加机器人消息, 并停止当前播放的语音"""
        bubble = ChatBubble("assistant", message)
        self.chat_layout.addWidget(bubble)
        self.conversation_history.append(("assistant", message))
        self.scroll_to_bottom()

        # 停止当前可能正在播放的语音
        if self.current_voice_thread and self.current_voice_thread.isRunning():
            pygame.mixer.stop()  # 停止播放
            self.current_voice_thread.wait() # 等待线程结束

        # 启动语音合成线程 (传递 self 作为 parent)
        self.current_voice_thread = VoiceOutputThread(message, self)
        self.current_voice_thread.finished.connect(self.on_voice_finished)
        self.current_voice_thread.error.connect(self.on_voice_error)
        self.current_voice_thread.start()


    def on_voice_finished(self):
        print("语音播放完成")
        #  可以在这里添加播放完成后需要执行的操作，例如删除临时文件（如果需要）

    def on_voice_error(self, error_message):
        print(f"语音合成错误: {error_message}")
        #  可以在这里添加错误处理逻辑，例如显示错误消息给用户

    def closeEvent(self, event):
        """窗口关闭事件，用于清理资源"""
        pygame.mixer.quit()  # 取消初始化 pygame.mixer
        super().closeEvent(event)
        # 清除临时音频文件
        temp_mp3 = os.path.join(RECORD_FOLDER, "temp.mp3")
        temp_wav = os.path.join(RECORD_FOLDER, "temp.wav")
        if os.path.exists(temp_mp3):
            os.remove(temp_mp3)
        if os.path.exists(temp_wav):
            os.remove(temp_wav)

    def scroll_to_bottom(self):
        """确保滚动区域始终保持在最新消息处"""
        QtCore.QTimer.singleShot(100, lambda: self.scroll_area.verticalScrollBar().setValue(
            self.scroll_area.verticalScrollBar().maximum()))

    def on_send_text(self):
        """用户点击发送按钮后触发"""
        user_message = self.user_input.text().strip()
        if not user_message:
            return

        self.add_user_message(user_message)
        self.user_input.clear()

        # 如果用户在补充信息模式下，立即生成新的病历
        if self.in_supplement_mode:
            self.generate_medical_record()
            return

        # 检查是否为最后一条提示补充信息的消息，触发生成病历记录
        if len(self.conversation_history) >= 2:
            last_message = self.conversation_history[-2][1]
            if "好的，我已经大概搜集好您的情况，您是否有需要补充的？请您告诉我。" in last_message:
                self.generate_medical_record()

    def generate_medical_record(self):
        """生成结构化病历"""
        try:
            self.add_robot_message("正在生成结构化入院记录，请稍候...")

            # Create a thread to handle the API call
            self.record_thread = MedicalRecordThread(self.client, self.conversation_history)
            self.record_thread.recordReady.connect(self.handle_record_result)
            self.record_thread.recordError.connect(self.handle_record_error)
            self.record_thread.start()

        except Exception as e:
            print(f"生成病历错误: {e}")
            self.add_robot_message(f"生成病历时发生错误，请重试。错误信息：{str(e)}")

    def handle_record_result(self, filename, medical_record):
        """处理生成完成的病历记录"""
        self.add_robot_message(f"病历已保存至：{filename}\n\n病历内容：\n{medical_record}")

        # Reset the supplement mode flag
        self.in_supplement_mode = False

        # 显示确认对话框
        self.show_confirmation_dialog(medical_record)

    def handle_record_error(self, error_message):
        """处理病历生成错误"""
        self.add_robot_message(f"生成病历时发生错误，请重试。错误信息：{error_message}")

    def show_confirmation_dialog(self, medical_record):
        """显示确认病历信息的对话框"""
        confirm_dialog = QtWidgets.QDialog(self)
        confirm_dialog.setWindowTitle("确认病历信息")
        confirm_dialog.setMinimumSize(600, 400)

        layout = QtWidgets.QVBoxLayout(confirm_dialog)

        # 添加标题
        title_label = QtWidgets.QLabel("请确认以下病历信息是否准确：")
        title_label.setStyleSheet("font-size: 14pt; font-weight: bold;")
        layout.addWidget(title_label)

        # 添加病历内容（可滚动）
        record_scroll = QtWidgets.QScrollArea()
        record_scroll.setWidgetResizable(True)
        record_widget = QtWidgets.QWidget()
        record_layout = QtWidgets.QVBoxLayout(record_widget)

        record_text = QtWidgets.QTextEdit()
        record_text.setReadOnly(True)
        record_text.setPlainText(medical_record)
        record_text.setStyleSheet("font-size: 12pt;")
        record_layout.addWidget(record_text)

        record_scroll.setWidget(record_widget)
        layout.addWidget(record_scroll)

        # 添加按钮
        button_layout = QtWidgets.QHBoxLayout()

        confirm_button = QtWidgets.QPushButton("确认并结束问诊")
        confirm_button.setStyleSheet("font-size: 12pt; padding: 8px;")
        confirm_button.clicked.connect(lambda: self.confirm_and_exit(confirm_dialog))

        return_button = QtWidgets.QPushButton("返回对话继续补充")
        return_button.setStyleSheet("font-size: 12pt; padding: 8px;")
        return_button.clicked.connect(lambda: self.return_to_conversation(confirm_dialog))

        button_layout.addWidget(return_button)
        button_layout.addWidget(confirm_button)

        layout.addLayout(button_layout)

        confirm_dialog.setLayout(layout)
        confirm_dialog.exec_()

    def return_to_conversation(self, dialog):
        """返回对话以添加更多信息"""
        self.in_supplement_mode = True
        self.add_robot_message("您可以继续补充信息，发送消息后系统会立即生成新的病历和参考诊断与治疗建议。")
        dialog.reject()

    def confirm_and_exit(self, dialog):
        """确认病历并退出程序"""
        dialog.accept()
        QtWidgets.QMessageBox.information(self, "问诊结束", "感谢您使用AI医生助手，您的病历报告和参考诊断与治疗建议已发送给您的医生！问诊已结束。")
        QtWidgets.QApplication.quit()
        # 清除临时音频文件
        temp_mp3 = os.path.join(RECORD_FOLDER, "temp.mp3")
        temp_wav = os.path.join(RECORD_FOLDER, "temp.wav")
        if os.path.exists(temp_mp3):
            os.remove(temp_mp3)
        if os.path.exists(temp_wav):
            os.remove(temp_wav)

    def on_voice_input(self):
        """处理语音输入/停止语音输入"""
        if not self.is_voice_recording:
            # Start recording
            self.add_robot_message("正在听取您的语音输入...")
            self.voice_input_thread = VoiceInputThread() # Create thread instance here
            self.voice_input_thread.recognized.connect(self.handle_voice_input)
            self.voice_input_thread.error.connect(self.handle_voice_error)
            self.voice_input_thread.start()
            self.is_voice_recording = True
            self.btn_voice.setText("停止录音")
            self.btn_send.setEnabled(False) # Disable send button during recording
        else:
            # Stop recording
            if self.voice_input_thread:
                self.voice_input_thread.stop_recording() # Stop recording thread
            self.is_voice_recording = False
            self.btn_voice.setText("语音输入")
            self.btn_send.setEnabled(True) # Enable send button after recording

    def handle_voice_input(self, text):
        """成功识别语音"""
        self.user_input.setText(text)
        self.on_send_text()
        self.is_voice_recording = False # Reset state after voice input handled
        self.btn_voice.setText("语音输入")
        self.btn_send.setEnabled(True) # Enable send button after recording

    def handle_voice_error(self, error):
        """语音识别错误处理"""
        self.add_robot_message(f"语音识别错误: {error}")
        self.is_voice_recording = False # Reset state even on error
        self.btn_voice.setText("语音输入")
        self.btn_send.setEnabled(True) # Enable send button after recording

def main():
    app = QtWidgets.QApplication(sys.argv)
    window = ChatWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
