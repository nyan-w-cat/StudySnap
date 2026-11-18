import sys
import keyboard
from PIL.Image import Image
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QStyle
from PySide6.QtCore import Qt, QThread, Signal, QObject, QTimer, QSettings
from PySide6.QtGui import QAction, QActionGroup

from capture_service import CaptureService
from gemini_service import GeminiService
from answer_panel import AnswerPanel
from cache_service import CacheService 

class HotkeySignal(QObject):
    triggered = Signal()

class ApiWorker(QThread):
    finished = Signal(dict, object)
    
    def __init__(self, image: Image, gemini_service: GeminiService, cache_service: CacheService, model_name: str):
        super().__init__()
        self.image = image
        self.gemini_service = gemini_service
        self.cache_service = cache_service
        self.model_name = model_name
        self.is_cancelled = False 
        
    def run(self):
        try:
            cached_result = self.cache_service.get_cached_result(self.image, self.model_name)
            if cached_result:
                conf = cached_result.get('confidence', '')
                if "Cached ⚡" not in conf:
                    cached_result['confidence'] = f"{conf} / Cached ⚡"
                if not self.is_cancelled:
                    self.finished.emit(cached_result, self)
                return

            result = self.gemini_service.analyze_image(self.image, self.model_name)
            
            if not self.is_cancelled and result.get("answer") != "오류 발생":
                self.cache_service.save_result(self.image, result, self.model_name)
                
            if not self.is_cancelled:
                self.finished.emit(result, self)
                
        except Exception as e:
            if not self.is_cancelled:
                self.finished.emit({
                    "answer": "시스템 에러 발생",
                    "confidence": "low",
                    "reason": f"오류: {str(e)}"
                }, self)

class AnalysisController(QObject):
    def __init__(self, app_instance):
        super().__init__()
        self.app = app_instance
        self.current_worker = None
        
        self.timeout_timer = QTimer()
        self.timeout_timer.setSingleShot(True)
        self.timeout_timer.timeout.connect(self.on_timeout)

    def start_analysis(self, screenshot: Image):
        if self.current_worker is not None:
            self.current_worker.is_cancelled = True
            self.current_worker = None
            
        # 🚨 설정값에 따라 로딩 창 표시 여부 결정
        if self.app.show_loading:
            self.app.panel.show_loading(self.app.display_mode)
        else:
            self.app.panel.hide() # 꺼져있다면 이전 결과 창을 숨김
            
        self.current_worker = ApiWorker(
            screenshot, self.app.gemini_service, self.app.cache_service, self.app.current_model
        )
        self.current_worker.finished.connect(self.on_worker_finished)
        self.current_worker.start()
        
        self.timeout_timer.start(30000)

    def on_worker_finished(self, result: dict, worker: ApiWorker):
        if worker.is_cancelled or worker != self.current_worker:
            return
            
        self.timeout_timer.stop()
        self.app.panel.show_result(result, self.app.display_mode)
        self.current_worker.deleteLater()
        self.current_worker = None

    def on_timeout(self):
        if self.current_worker is not None:
            self.current_worker.is_cancelled = True
            self.current_worker = None
            self.app.panel.show_result({
                "answer": "Time Out",
                "confidence": "low",
                "reason": "API 요청이 30초를 초과하여 자동 취소되었습니다."
            }, self.app.display_mode)


class StudyAssistantApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)
        
        self.settings = QSettings("MyStudyApp", "StudyAssistant")
        self.display_mode = self.settings.value("display_mode", "full")
        self.current_model = self.settings.value("current_model", "gemini-3.5-flash-lite")
        # 부울(Boolean) 타입 안전 변환 (문자열 'true' 처리)
        self.show_loading = str(self.settings.value("show_loading", True)).lower() == 'true'
        
        self.capture_service = CaptureService()
        self.gemini_service = GeminiService()
        self.cache_service = CacheService()
        self.panel = AnswerPanel()
        
        self.panel.set_theme(self.settings.value("theme", "dark"))
        self.panel.set_opacity(float(self.settings.value("opacity", 0.75)))
        self.panel.set_auto_close_time(int(self.settings.value("auto_close", 5)))
        
        self.controller = AnalysisController(self)
        
        self.setup_tray_icon()
        
        self.hotkey_signal = HotkeySignal()
        self.hotkey_signal.triggered.connect(self.on_hotkey_pressed)
        keyboard.add_hotkey('ctrl+alt+a', lambda: self.hotkey_signal.triggered.emit())
        
    def setup_tray_icon(self):
        self.tray_icon = QSystemTrayIcon(self.app)
        icon = self.app.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
        self.tray_icon.setIcon(icon)
        menu = QMenu()
        
        # --- 0. 수동 실행 메뉴 ---
        run_action = QAction("🚀 수동 캡처 및 풀이 실행", menu)
        run_action.triggered.connect(self.trigger_manual_capture)
        menu.addAction(run_action)
        
        menu.addSeparator()
        
        # --- 1. 표시 모드 및 로딩 창 설정 ---
        display_menu = menu.addMenu("표시 설정")
        
        display_group = QActionGroup(display_menu)
        for text, val in [("정답 + 해설 표시", "full"), ("정답만 표시", "answer_only")]:
            act = QAction(text, display_menu, checkable=True, checked=(self.display_mode == val))
            act.triggered.connect(lambda checked, v=val: self.set_display_mode(v))
            display_group.addAction(act)
            display_menu.addAction(act)
            
        display_menu.addSeparator()
        
        loading_action = QAction("⏳ '분석 중...' 로딩 창 표시", display_menu, checkable=True, checked=self.show_loading)
        loading_action.triggered.connect(self.set_show_loading)
        display_menu.addAction(loading_action)
        
        # --- 2. 테마 설정 ---
        theme_menu = menu.addMenu("테마 설정")
        theme_group = QActionGroup(theme_menu)
        current_theme = self.settings.value("theme", "dark")
        for text, val in [("다크 모드", "dark"), ("라이트 모드", "light")]:
            act = QAction(text, theme_menu, checkable=True, checked=(current_theme == val))
            act.triggered.connect(lambda checked, v=val: self.set_theme(v))
            theme_group.addAction(act)
            theme_menu.addAction(act)
            
        # --- 3. 투명도 설정 ---
        opacity_menu = menu.addMenu("투명도 설정")
        op_group = QActionGroup(opacity_menu)
        current_op = float(self.settings.value("opacity", 0.75))
        for text, val in [("100% (불투명)", 1.0), ("75% (기본)", 0.75), ("50%", 0.5), ("25%", 0.25), ("0% (완전 투명)", 0.0)]:
            act = QAction(text, opacity_menu, checkable=True, checked=(current_op == val))
            act.triggered.connect(lambda checked, v=val: self.set_opacity(v))
            op_group.addAction(act)
            opacity_menu.addAction(act)
            
        # --- 4. 자동 닫기 시간 ---
        time_menu = menu.addMenu("자동 닫기 시간")
        time_group = QActionGroup(time_menu)
        current_time = int(self.settings.value("auto_close", 5))
        for text, val in [("1초", 1), ("3초", 3), ("5초", 5), ("닫을 때까지 표시", 0)]:
            act = QAction(text, time_menu, checkable=True, checked=(current_time == val))
            act.triggered.connect(lambda checked, v=val: self.set_auto_close_time(v))
            time_group.addAction(act)
            time_menu.addAction(act)
            
        # --- 5. AI 모델 ---
        model_menu = menu.addMenu("AI 모델 선택")
        model_group = QActionGroup(model_menu)
        for text, val in [("Gemini 3.5 Flash Lite", "gemini-3.5-flash-lite"), 
                          ("Gemini 3.1 Flash Lite", "gemini-3.1-flash-lite"),
                          ("Gemini 3.8 Flash", "gemini-3.8-flash"),
                         ("Gemini 4 Hydrogen", "gemini-4-hydrogen")]:
            act = QAction(text, model_menu, checkable=True, checked=(self.current_model == val))
            act.triggered.connect(lambda checked, v=val: self.set_model(v))
            model_group.addAction(act)
            model_menu.addAction(act)
            
        menu.addSeparator()
        exit_action = QAction("종료", menu)
        exit_action.triggered.connect(self.quit_app)
        menu.addAction(exit_action)
        
        self.tray_icon.setContextMenu(menu)
        self.tray_icon.show()

    def set_display_mode(self, mode: str):
        self.display_mode = mode
        self.settings.setValue("display_mode", mode)
        
    def set_show_loading(self, show: bool):
        self.show_loading = show
        self.settings.setValue("show_loading", show)
        
    def set_theme(self, theme: str):
        self.panel.set_theme(theme)
        self.settings.setValue("theme", theme)
        
    def set_opacity(self, ratio: float):
        self.panel.set_opacity(ratio)
        self.settings.setValue("opacity", ratio)
        
    def set_auto_close_time(self, seconds: int):
        self.panel.set_auto_close_time(seconds)
        self.settings.setValue("auto_close", seconds)
        
    def set_model(self, model_name: str):
        self.current_model = model_name
        self.settings.setValue("current_model", model_name)

    def quit_app(self):
        self.tray_icon.hide()
        self.app.quit()
        
    def trigger_manual_capture(self):
        # 트레이 메뉴가 닫히는 시간을 벌기 위해 300ms 대기 후 캡처 실행 (메뉴 잔상 방지)
        QTimer.singleShot(300, self.on_hotkey_pressed)

    def on_hotkey_pressed(self):
        screenshot = self.capture_service.capture_full_screen()
        self.controller.start_analysis(screenshot)
        
    def run(self):
        sys.exit(self.app.exec())

if __name__ == "__main__":
    assistant = StudyAssistantApp()
    assistant.run()
