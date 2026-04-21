"""
네이버/구글 검색 자동화 앱
사용법:
  pip3 install selenium webdriver-manager PyQt6
  python3 search_bot.py
"""

import warnings
warnings.filterwarnings('ignore', message='urllib3 v2 only supports OpenSSL')

import datetime
import random
import sys
import threading
from urllib.parse import quote_plus

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QComboBox,
    QPushButton, QTextEdit, QFrame,
    QMessageBox, QCheckBox,
)
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

NAVER_URL   = "https://search.naver.com/search.naver?query={}"
GOOGLE_URL  = "https://www.google.com/search?q={}"
SEARCH_COUNT = 50


class SearchBot:
    def __init__(self, keywords: list[str], log_fn, stop_event: threading.Event):
        self.keywords   = keywords
        self.log        = log_fn
        self.stop_event = stop_event

    def _make_driver(self) -> webdriver.Chrome:
        options = webdriver.ChromeOptions()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        options.add_argument(
            "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
        options.add_argument("--window-size=1024,768")
        service = Service(ChromeDriverManager().install())
        driver  = webdriver.Chrome(service=service, options=options)
        driver.execute_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        return driver

    def _random_delay(self, min_s: float, max_s: float):
        elapsed  = 0.0
        target   = random.uniform(min_s, max_s)
        interval = 0.2
        while elapsed < target:
            if self.stop_event.is_set():
                return
            wait     = min(interval, target - elapsed)
            self.stop_event.wait(timeout=wait)
            elapsed += wait

    def _search_site(self, driver, url_template: str, keyword: str, site_name: str):
        url = url_template.format(quote_plus(keyword))
        for i in range(1, SEARCH_COUNT + 1):
            if self.stop_event.is_set():
                return
            try:
                driver.get(url)
            except Exception as e:
                self.log(f"[오류] {site_name} | {keyword} | {i}/{SEARCH_COUNT}: {e}")
            self.log(f"{site_name} | {keyword} | {i}/{SEARCH_COUNT} 완료")
            if i % 10 == 0 and i < SEARCH_COUNT:
                self.log("  → 10회 단위 추가 대기 중...")
                self._random_delay(15.0, 30.0)
            else:
                self._random_delay(3.0, 7.0)

    def run(self):
        driver = None
        try:
            self.log("Chrome 브라우저 시작 중...")
            driver = self._make_driver()
            for keyword in self.keywords:
                if self.stop_event.is_set():
                    break
                self.log(f"\n[검색어: {keyword}] 네이버 검색 시작")
                self._search_site(driver, NAVER_URL, keyword, "네이버")
                if self.stop_event.is_set():
                    break
                self.log("  → 사이트 전환 대기 중...")
                self._random_delay(10.0, 20.0)
                if self.stop_event.is_set():
                    break
                self.log(f"[검색어: {keyword}] 구글 검색 시작")
                self._search_site(driver, GOOGLE_URL, keyword, "구글")
                if self.stop_event.is_set():
                    break
                self.log(f"[검색어: {keyword}] 완료\n")
        except Exception as e:
            self.log(f"[오류] {e}")
        finally:
            if driver:
                try:
                    driver.quit()
                except Exception:
                    pass
            msg = "검색이 중지되었습니다." if self.stop_event.is_set() else "모든 검색이 완료되었습니다."
            self.log(msg)


class SearchWorker(QThread):
    log_signal  = pyqtSignal(str)
    done_signal = pyqtSignal()

    def __init__(self, keywords: list[str], target_dt: datetime.datetime,
                 stop_event: threading.Event):
        super().__init__()
        self.keywords   = keywords
        self.target_dt  = target_dt
        self.stop_event = stop_event

    def _ts(self) -> str:
        return datetime.datetime.now().strftime("%H:%M:%S")

    def run(self):
        while not self.stop_event.is_set():
            remaining = (self.target_dt - datetime.datetime.now()).total_seconds()
            if remaining <= 0:
                break
            mins, secs = int(remaining // 60), int(remaining % 60)
            self.log_signal.emit(f"[{self._ts()}] 실행까지 {mins}분 {secs}초 남음...")
            self.stop_event.wait(timeout=1.0)

        if not self.stop_event.is_set():
            def log_ts(msg: str):
                self.log_signal.emit(f"[{self._ts()}] {msg}")
            SearchBot(self.keywords, log_ts, self.stop_event).run()

        self.done_signal.emit()


class SearchApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.stop_event: threading.Event       = threading.Event()
        self.worker:     SearchWorker | None   = None
        self._build_ui()

    @staticmethod
    def _sep() -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        return line

    def _build_ui(self):
        self.setWindowTitle("네이버/구글 검색 자동화")
        self.setFixedSize(520, 600)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(10)

        # 제목
        title = QLabel("네이버 / 구글 검색 자동화")
        title.setFont(QFont("Apple SD Gothic Neo, Malgun Gothic", 17, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(title)
        root.addWidget(self._sep())

        # 검색어
        root.addWidget(self._hdr("검색어"))
        self.keyword_entries: list[QLineEdit] = []
        for i in range(1, 4):
            row = QHBoxLayout()
            lbl = QLabel(f"검색어 {i}:")
            lbl.setFixedWidth(72)
            row.addWidget(lbl)
            entry = QLineEdit()
            entry.setPlaceholderText(f"검색어 {i} 입력")
            row.addWidget(entry)
            root.addLayout(row)
            self.keyword_entries.append(entry)

        root.addWidget(self._sep())

        # 실행 시간
        root.addWidget(self._hdr("실행 시간"))
        time_row = QHBoxLayout()
        time_row.addWidget(QLabel("시각:"))

        now = datetime.datetime.now()
        self.hour_combo = QComboBox()
        self.hour_combo.addItems([str(h) for h in range(24)])
        self.hour_combo.setCurrentIndex(now.hour)
        self.hour_combo.setFixedWidth(80)
        time_row.addWidget(self.hour_combo)
        time_row.addWidget(QLabel("시"))

        self.minute_combo = QComboBox()
        self.minute_combo.addItems([str(m) for m in range(0, 60, 5)])
        self.minute_combo.setCurrentText(str((now.minute // 5) * 5))
        self.minute_combo.setFixedWidth(80)
        time_row.addWidget(self.minute_combo)
        time_row.addWidget(QLabel("분"))
        time_row.addStretch()
        root.addLayout(time_row)

        self.daily_check = QCheckBox("매일 자동실행")
        root.addWidget(self.daily_check)

        root.addWidget(self._sep())

        # 버튼
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.start_btn = self._btn("시  작", "#4CAF50", "#388E3C")
        self.start_btn.clicked.connect(self._on_start)
        btn_row.addWidget(self.start_btn)
        btn_row.addSpacing(24)
        self.stop_btn = self._btn("중  지", "#e53935", "#b71c1c")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._on_stop)
        btn_row.addWidget(self.stop_btn)
        btn_row.addStretch()
        root.addLayout(btn_row)

        root.addWidget(self._sep())

        # 로그
        root.addWidget(self._hdr("로그"))
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Courier", 11))
        root.addWidget(self.log_text)

    def _hdr(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setFont(QFont("Apple SD Gothic Neo, Malgun Gothic", 11, QFont.Weight.Bold))
        return lbl

    def _btn(self, text: str, color: str, hover: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setFixedSize(130, 40)
        btn.setFont(QFont("Apple SD Gothic Neo, Malgun Gothic", 13, QFont.Weight.Bold))
        btn.setStyleSheet(
            f"QPushButton {{ background-color:{color}; color:white; border-radius:8px; }}"
            f"QPushButton:hover {{ background-color:{hover}; }}"
            f"QPushButton:disabled {{ background-color:#aaaaaa; }}"
        )
        return btn

    def _get_keywords(self) -> list[str]:
        return [e.text().strip() for e in self.keyword_entries if e.text().strip()]

    def _get_schedule_dt(self) -> datetime.datetime:
        now    = datetime.datetime.now()
        h      = int(self.hour_combo.currentText())
        m      = int(self.minute_combo.currentText())
        target = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if target <= now:
            target += datetime.timedelta(days=1)
        return target

    def _on_start(self):
        keywords = self._get_keywords()
        if not keywords:
            QMessageBox.warning(self, "입력 오류", "검색어를 최소 1개 입력해주세요.")
            return

        self.stop_event = threading.Event()
        target_dt = self._get_schedule_dt()

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

        ts = datetime.datetime.now().strftime("%H:%M:%S")
        for line in ["=" * 34,
                     f"검색어: {', '.join(keywords)}",
                     f"실행 예정: {target_dt.strftime('%Y-%m-%d %H:%M:00')}",
                     "=" * 34]:
            self.log_text.append(f"[{ts}] {line}")

        self.worker = SearchWorker(keywords, target_dt, self.stop_event)
        self.worker.log_signal.connect(self.log_text.append)
        self.worker.done_signal.connect(self._on_done)
        self.worker.start()

    def _on_stop(self):
        self.stop_event.set()
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{ts}] 중지 신호를 보냈습니다...")
        self.stop_btn.setEnabled(False)

    def _on_done(self):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        if self.daily_check.isChecked() and not self.stop_event.is_set():
            ts = datetime.datetime.now().strftime("%H:%M:%S")
            self.log_text.append(f"[{ts}] 내일 같은 시간에 자동 재실행 예약 중...")
            self._on_start()

    def closeEvent(self, event):
        self.stop_event.set()
        if self.worker:
            self.worker.wait(2000)
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SearchApp()
    window.show()
    sys.exit(app.exec())
