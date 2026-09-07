from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QFrame, QApplication
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QScreen

class AnswerPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(420, 160)
        self.setStyleSheet("background: transparent;")
        
        self.current_alpha_ratio = 0.75 
        self.auto_close_seconds = 5 
        self.current_theme = "dark" 
        self.current_answer_text = "" # 클립보드 복사용 변수
        
        self.init_ui()
        self.position_bottom_right()
        
        self.auto_close_timer = QTimer(self)
        self.auto_close_timer.timeout.connect(self.hide)
        
    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        self.container = QFrame(self)
        
        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(15, 15, 15, 15)
        
        self.status_label = QLabel("Ready")
        self.reason_label = QLabel("대기 중...")
        self.reason_label.setWordWrap(True)
        self.reason_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        # 복사 버튼 추가
        self.copy_btn = QPushButton("Copy")
        self.copy_btn.clicked.connect(self.copy_to_clipboard)
        btn_layout.addWidget(self.copy_btn)
        
        self.close_btn = QPushButton("Close (Esc)")
        self.close_btn.clicked.connect(self.hide)
        btn_layout.addWidget(self.close_btn)
        
        layout.addWidget(self.status_label)
        layout.addWidget(self.reason_label)
        layout.addLayout(btn_layout)
        main_layout.addWidget(self.container)

    def copy_to_clipboard(self):
        if self.current_answer_text:
            QApplication.clipboard().setText(self.current_answer_text)
            self.copy_btn.setText("Copied!")
            QTimer.singleShot(1500, lambda: self.copy_btn.setText("Copy"))

    def update_container_style(self):
        alpha_int = int(255 * self.current_alpha_ratio)
        if self.current_theme == "dark":
            bg_color = f"rgba(45, 45, 48, {alpha_int})"
            border_color = f"rgba(85, 85, 85, {alpha_int})"
            text_color = "#E0E0E0"
            status_color = "#4DAAFB"
            btn_bg = "rgba(68, 68, 68, 200)"
            btn_hover = "rgba(100, 100, 100, 200)"
            btn_text = "#FFFFFF"
        else: 
            bg_color = f"rgba(245, 245, 247, {alpha_int})"
            border_color = f"rgba(200, 200, 204, {alpha_int})"
            text_color = "#333333" 
            status_color = "#0066CC"
            btn_bg = "rgba(220, 220, 224, 200)"
            btn_hover = "rgba(200, 200, 204, 200)"
            btn_text = "#222222"

        self.container.setStyleSheet(f"QFrame {{ background-color: {bg_color}; border-radius: 10px; border: 1px solid {border_color}; }}")
        self.status_label.setStyleSheet(f"font-weight: bold; font-size: 15px; color: {status_color}; background: transparent;")
        self.reason_label.setStyleSheet(f"color: {text_color}; background: transparent;")
        
        btn_style = f"QPushButton {{ background-color: {btn_bg}; color: {btn_text}; padding: 4px 10px; border-radius: 4px; border: none; }} QPushButton:hover {{ background-color: {btn_hover}; }}"
        self.copy_btn.setStyleSheet(btn_style)
        self.close_btn.setStyleSheet(btn_style)
        
        self.container.style().unpolish(self.container)
        self.container.style().polish(self.container)

    def set_opacity(self, ratio: float):
        self.current_alpha_ratio = ratio
        self.update_container_style()

    def set_theme(self, theme_name: str):
        self.current_theme = theme_name
        self.update_container_style()

    def set_auto_close_time(self, seconds: int):
        self.auto_close_seconds = seconds

    def position_bottom_right(self):
        screen = QScreen.availableGeometry(self.screen())
        self.move(screen.width() - self.width() - 20, screen.height() - self.height() - 20)

    def show_result(self, result: dict, mode: str):
        self.current_answer_text = str(result.get('answer', 'N/A'))
        self.copy_btn.setText("Copy")
        
        self.status_label.setText(f"정답: {self.current_answer_text} ({result.get('confidence', '')})")
        
        if mode == "full":
            self.reason_label.setText(result.get('reason', ''))
            self.reason_label.show()
        else:
            self.reason_label.hide()
            
        self.show()
        if self.auto_close_seconds > 0:
            self.auto_close_timer.start(self.auto_close_seconds * 1000)
        else:
            self.auto_close_timer.stop()

    def show_loading(self, mode: str):
        self.status_label.setText("분석 중...")
        if mode == "full":
            self.reason_label.setText("API 요청 및 수학적 추론을 진행하고 있습니다.")
            self.reason_label.show()
        else:
            self.reason_label.hide()
            
        self.show()
        self.auto_close_timer.stop()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.hide()