import requests
import re
import json
import os
import time

# === 설정(환경변수에서 읽기) ===
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")  # 문자열로 두고 그대로 사용

if not BOT_TOKEN or not CHAT_ID:
    raise RuntimeError("BOT_TOKEN 또는 CHAT_ID 환경변수가 설정되지 않았습니다.")

CATEGORIES = {
    "촬영/조명": "https://www.filmmakers.co.kr/proCrewRecruiting/category/26079831",
    "스틸/메이킹": "https://www.filmmakers.co.kr/proCrewRecruiting/category/26079836",
}

STATE_FILE = "filmmakers_state.json"  # 마지막으로 본 등록 시간 기록용
INTERVAL_SECONDS = 300  # 5분마다 체크 (원하면 180=3분, 600=10분 등으로 수정)


def load_state():
    """이전에 체크했던 마지막 등록 시간을 파일에서 불러온다."""
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(state):
    """마지막 등록 시간 상태를 저장한다."""
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def fetch_registered_times(url):
    """
    카테고리 페이지에서 '등록 : YYYY-MM-DD HH:MM' 패턴을 모두 찾아서
    중복 제거 후, 페이지 상단에 가까운 순서대로 리스트를 반환.
    """
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    html = resp.text

    # '등록 : 2025-11-18 17:25' 같은 패턴 모두 찾기
    matches = re.findall(r"등록\s*:\s*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})", html)
    unique = []
    for ts in matches:
        if ts not in unique:
            unique.append(ts)

    return unique  # 페이지 상단(최신)부터 순서대로라고 가정


def send_telegram_message(text):
    """텔레그램으로 메시지를 보낸다."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    params = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
    }
    try:
        res = requests.get(url, params=params, timeout=10)
        res.raise_for_status()
        print("텔레그램 전송 성공")
    except Exception as e:
        print("텔레그램 전송 오류:", e)


def check_once():
    """한 번 전체 카테고리를 체크하는 함수."""
    state = load_state()
    overall_new_count = 0
    messages = []

    for name, url in CATEGORIES.items():
        try:
            times = fetch_registered_times(url)
        except Exception as e:
            print(f"{name} 페이지 요청 실패:", e)
            continue

        if not times:
            print(f"{name}: '등록 :' 패턴을 찾지 못함")
            continue

        latest_on_page = times[0]  # 페이지 상단의 가장 최신 등록 시간
        last_seen = state.get(name)

        # 최초 실행 시: 기준만 잡고 알림은 안 보냄
        if last_seen is None:
            state[name] = latest_on_page
            print(f"{name}: 최초 실행, 기준 등록 시간 {latest_on_page} 로 저장")
            continue

        # last_seen 이후의 신규 등록 시간 찾기
        new_times = [t for t in times if t > last_seen]

        if new_times:
            new_times_sorted = sorted(new_times)  # 오래된 것 → 최신 순
            newest = new_times_sorted[-1]
            state[name] = newest
            count = len(new_times_sorted)
            overall_new_count += count

            msg = (
                f"📢 <b>필름메이커스 새 스탭 공고 감지</b>\n"
                f"카테고리: {name}\n"
                f"새 글 수: {count}개\n"
                f"최신 등록: {newest}\n"
                f"바로 가기: {url}"
            )
            messages.append(msg)
            print(f"{name}: 새 글 {count}개 감지 (최신 {newest})")
        else:
            print(f"{name}: 새 글 없음 (마지막 기준 {last_seen})")

    # 새 글이 하나라도 있으면 텔레그램으로 알림 보내기
    if overall_new_count > 0:
        final_text = "✅ 필름메이커스 새 글 알림\n\n" + "\n\n".join(messages)
        send_telegram_message(final_text)
    else:
        print("이번 체크에서는 새 글 없음")

    save_state(state)


def main_loop():
    print("필름메이커스 텔레그램 알림 봇 시작")
    while True:
        try:
            check_once()
        except Exception as e:
            print("체크 중 에러 발생:", e)
        # INTERVAL_SECONDS 만큼 대기 후 다시 체크
        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main_loop()
