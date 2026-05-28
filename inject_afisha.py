"""
inject_afisha.py — Парсер афиши + вшивание данных в HTML
=========================================================
Запуск:  python inject_afisha.py

Скрипт должен лежать в той же папке, что и kmv_guide.html

Зависимости:  pip install requests beautifulsoup4
Расписание:
  Windows:    Планировщик задач → еженедельно → python inject_afisha.py
  Mac/Linux:  0 9 * * 1  python3 /путь/inject_afisha.py
"""

import json, os, re
from datetime import datetime
import requests
from bs4 import BeautifulSoup

BASE_URL   = "https://www.pyatigorsk.online"
POSTER_URL = f"{BASE_URL}/poster/"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HTML_FILE  = os.path.join(SCRIPT_DIR, "kmv_guide.html")

MARKER_START = "/* AFISHA_DATA_START */"
MARKER_END   = "/* AFISHA_DATA_END */"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "ru-RU,ru;q=0.9",
}


def fetch_page(url):
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    r.encoding = "utf-8"
    return BeautifulSoup(r.text, "html.parser")


def parse_events(soup):
    events = []
    seen = set()
    date_re = re.compile(r"\d{2}\.\d{2}\.\d{2,4}")

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/poster/" not in href:
            continue
        if not href.startswith("http"):
            href = BASE_URL + href
        if href in (POSTER_URL, BASE_URL + "/poster/") or href in seen:
            continue

        card = a.find_parent(["div", "article", "li"])
        if not card:
            continue
        seen.add(href)

        h = card.find(["h3", "h2"])
        title = h.get_text(strip=True) if h else a.get_text(strip=True)
        if not title or title.lower() in ("подробнее", ""):
            continue

        img_tag = card.find("img")
        image = ""
        if img_tag:
            src = img_tag.get("src") or img_tag.get("data-src") or ""
            image = src if src.startswith("http") else BASE_URL + src

        date_raw = ""
        for node in card.find_all(string=date_re):
            c = node.strip()
            if len(c) < 40:
                date_raw = c
                break

        venue = ""
        full_text = card.get_text(" ", strip=True)
        m = re.search(r"Место проведения[:\s]*(.+?)(?:Сохраняйте|Подробнее|$)", full_text, re.IGNORECASE)
        if m:
            venue = m.group(1).strip()[:120]

        desc = ""
        for p in card.find_all("p"):
            t = p.get_text(strip=True)
            if t and "Место проведения" not in t and "Подробнее" not in t and len(t) > 20:
                desc = t[:280]
                break

        events.append({
            "title": title,
            "url": href,
            "image": image,
            "date_raw": date_raw,
            "venue": venue,
            "description": desc,
        })

    return events


def inject_into_html(events, html_path):
    with open(html_path, encoding="utf-8") as f:
        html = f.read()

    if MARKER_START not in html or MARKER_END not in html:
        print(f"  [!] Маркеры не найдены в {os.path.basename(html_path)}")
        print(f"       Используйте актуальную версию kmv_guide.html")
        return False

    payload = {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "source": POSTER_URL,
        "count": len(events),
        "events": events,
    }

    json_str = json.dumps(payload, ensure_ascii=False, indent=2)
    new_block = f"{MARKER_START}\nwindow.AFISHA_DATA = {json_str};\n{MARKER_END}"

    pattern = re.compile(
        re.escape(MARKER_START) + r".*?" + re.escape(MARKER_END),
        re.DOTALL,
    )
    html_new = pattern.sub(new_block, html)

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_new)

    return True


def main():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] Обновление афиши...")
    print(f"  HTML: {HTML_FILE}")

    if not os.path.exists(HTML_FILE):
        print(f"  [!] Файл kmv_guide.html не найден рядом со скриптом!")
        return

    print(f"  Загрузка {POSTER_URL}...")
    try:
        soup = fetch_page(POSTER_URL)
    except requests.RequestException as e:
        print(f"  [!] Ошибка загрузки: {e}")
        return

    events = parse_events(soup)
    print(f"  Найдено событий: {len(events)}")

    if not events:
        print("  [!] Событий не найдено, HTML не изменён")
        return

    ok = inject_into_html(events, HTML_FILE)
    if ok:
        print(f"  Готово! Обновите страницу в браузере (Ctrl+R)")

    for i, ev in enumerate(events[:3], 1):
        print(f"\n  [{i}] {ev['title']}")
        print(f"       {ev['date_raw'] or '—'}  |  {(ev['venue'] or '—')[:55]}")


if __name__ == "__main__":
    main()