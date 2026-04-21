"""
네이버/구글 검색 자동화 (CLI)
사용법:
  SearchBot.exe -k "키워드1,키워드2" -t 14:30
  SearchBot.exe -k "키워드1" --daily
  pip install selenium webdriver-manager
"""

import warnings
warnings.filterwarnings('ignore', message='urllib3 v2 only supports OpenSSL')

import argparse
import datetime
import random
import threading
from urllib.parse import quote_plus

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

NAVER_URL    = "https://search.naver.com/search.naver?query={}"
GOOGLE_URL   = "https://www.google.com/search?q={}"
SEARCH_COUNT = 50


def log(msg: str):
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


class SearchBot:
    def __init__(self, keywords: list[str], stop_event: threading.Event):
        self.keywords   = keywords
        self.stop_event = stop_event

    def _make_driver(self) -> webdriver.Chrome:
        options = webdriver.ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        options.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
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
                log(f"[오류] {site_name} | {keyword} | {i}/{SEARCH_COUNT}: {e}")
            log(f"{site_name} | {keyword} | {i}/{SEARCH_COUNT} 완료")
            if i % 10 == 0 and i < SEARCH_COUNT:
                log("  → 10회 단위 추가 대기 중...")
                self._random_delay(15.0, 30.0)
            else:
                self._random_delay(3.0, 7.0)

    def run(self):
        driver = None
        try:
            log("Chrome 시작 중... (백그라운드)")
            driver = self._make_driver()
            for keyword in self.keywords:
                if self.stop_event.is_set():
                    break
                log(f"\n[검색어: {keyword}] 네이버 검색 시작")
                self._search_site(driver, NAVER_URL, keyword, "네이버")
                if self.stop_event.is_set():
                    break
                log("  → 사이트 전환 대기 중...")
                self._random_delay(10.0, 20.0)
                if self.stop_event.is_set():
                    break
                log(f"[검색어: {keyword}] 구글 검색 시작")
                self._search_site(driver, GOOGLE_URL, keyword, "구글")
                if self.stop_event.is_set():
                    break
                log(f"[검색어: {keyword}] 완료\n")
        except Exception as e:
            log(f"[오류] {e}")
        finally:
            if driver:
                try:
                    driver.quit()
                except Exception:
                    pass
            log("검색이 중지되었습니다." if self.stop_event.is_set() else "모든 검색이 완료되었습니다.")


def wait_until(target_dt: datetime.datetime, stop_event: threading.Event):
    log(f"실행 예정: {target_dt.strftime('%Y-%m-%d %H:%M:00')}")
    log("중지하려면 Ctrl+C를 누르세요.\n")
    while not stop_event.is_set():
        remaining = (target_dt - datetime.datetime.now()).total_seconds()
        if remaining <= 0:
            break
        mins, secs = int(remaining // 60), int(remaining % 60)
        log(f"실행까지 {mins}분 {secs}초 남음...")
        stop_event.wait(timeout=60.0 if mins > 0 else 1.0)


def parse_time(time_str: str) -> datetime.datetime:
    try:
        h, m = map(int, time_str.split(":"))
    except ValueError:
        raise argparse.ArgumentTypeError(f"시각 형식 오류: '{time_str}' (올바른 형식: HH:MM)")
    now    = datetime.datetime.now()
    target = now.replace(hour=h, minute=m, second=0, microsecond=0)
    if target <= now:
        target += datetime.timedelta(days=1)
    return target


def main():
    parser = argparse.ArgumentParser(
        description="네이버/구글 검색 자동화",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=(
            "예시:\n"
            "  SearchBot.exe -k \"키워드1,키워드2\" -t 14:30\n"
            "  SearchBot.exe -k \"키워드1\" --daily\n"
            "  SearchBot.exe -k \"키워드1,키워드2\"  (즉시 실행)\n"
        )
    )
    parser.add_argument("-k", "--keywords", required=True,
                        help="검색어 (쉼표 구분, 예: 키워드1,키워드2)")
    parser.add_argument("-t", "--time",
                        help="실행 시각 HH:MM (생략 시 즉시 실행)")
    parser.add_argument("-d", "--daily", action="store_true",
                        help="매일 같은 시각에 자동 반복 (-t 필요)")
    args = parser.parse_args()

    keywords = [k.strip() for k in args.keywords.split(",") if k.strip()]
    if not keywords:
        parser.error("검색어를 하나 이상 입력해주세요.")

    if args.daily and not args.time:
        parser.error("--daily 옵션은 -t 시각과 함께 사용해야 합니다.")

    stop_event = threading.Event()

    print("=" * 40)
    print(" 네이버/구글 검색 자동화")
    print("=" * 40)
    log(f"검색어: {', '.join(keywords)}")

    try:
        while True:
            if args.time:
                target_dt = parse_time(args.time)
                wait_until(target_dt, stop_event)

            if not stop_event.is_set():
                SearchBot(keywords, stop_event).run()

            if not args.daily or stop_event.is_set():
                break

            log("내일 같은 시각에 재실행 예약됨.")

    except KeyboardInterrupt:
        log("Ctrl+C 감지 — 중지 중...")
        stop_event.set()


if __name__ == "__main__":
    main()
