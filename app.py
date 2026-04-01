#!/usr/bin/env python3
"""
@siberhakkibot - AI Asistan & Günlük Haber Botu
Webhook tabanlı, Flask ile çalışır.
"""

import os
import json
import urllib.request
import urllib.parse
import re
from datetime import datetime
from flask import Flask, request, jsonify

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8758259886:AAHu8iOCGj6ugNfzxJC6J9IsbXI8PjM1Zlk")
OWNER_CHAT_ID = int(os.environ.get("OWNER_CHAT_ID", "70993977"))
PERPLEXITY_API_KEY = os.environ.get("PERPLEXITY_API_KEY", "")

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# ─── Telegram Yardımcı Fonksiyonlar ──────────────────────────────────────────

def send_message(chat_id, text, parse_mode="Markdown"):
    url = f"{TELEGRAM_API}/sendMessage"
    payload = json.dumps({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True
    }).encode("utf-8")
    req = urllib.request.Request(url, data=payload,
                                  headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"send_message hatası: {e}")
        return {}

def send_typing(chat_id):
    url = f"{TELEGRAM_API}/sendChatAction"
    payload = json.dumps({"chat_id": chat_id, "action": "typing"}).encode()
    req = urllib.request.Request(url, data=payload,
                                  headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5):
            pass
    except Exception:
        pass

# ─── Perplexity / Web Arama ───────────────────────────────────────────────────

def ask_perplexity(question):
    """Perplexity API ile soruyu yanıtla."""
    if not PERPLEXITY_API_KEY:
        return web_search_fallback(question)

    url = "https://api.perplexity.ai/chat/completions"
    payload = json.dumps({
        "model": "sonar",
        "messages": [
            {
                "role": "system",
                "content": (
                    "Sen @siberhakkibot adlı bir Telegram asistanısın. "
                    "Türkçe, net ve kısa yanıtlar ver. "
                    "Markdown formatını Telegram'a uygun kullan (* için bold, _ için italic). "
                    "Maksimum 3-4 paragraf yaz."
                )
            },
            {"role": "user", "content": question}
        ],
        "max_tokens": 800,
        "temperature": 0.2
    }).encode("utf-8")

    req = urllib.request.Request(
        url, data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {PERPLEXITY_API_KEY}"
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            return data["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"Perplexity hatası: {e}")
        return web_search_fallback(question)

def web_search_fallback(question):
    """Basit DuckDuckGo fallback."""
    try:
        q = urllib.parse.quote(question)
        url = f"https://api.duckduckgo.com/?q={q}&format=json&no_html=1&skip_disambig=1"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        abstract = data.get("AbstractText", "")
        if abstract:
            return abstract
        return "Bu konuda şu an bilgiye ulaşamadım, lütfen tekrar dene."
    except Exception:
        return "Şu an yanıt üretemiyorum, biraz sonra tekrar dene."

# ─── Haber Fonksiyonları ──────────────────────────────────────────────────────

RSS_SOURCES = [
    ("VentureBeat AI", "https://venturebeat.com/category/ai/feed/"),
    ("TechCrunch AI", "https://techcrunch.com/category/artificial-intelligence/feed/"),
]

def fetch_rss(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception:
        return None

def parse_rss(content, max_items=4):
    items = []
    entries = re.findall(r'<item>(.*?)</item>', content, re.DOTALL)
    for entry in entries[:max_items]:
        title_m = re.search(r'<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>', entry, re.DOTALL)
        link_m = re.search(r'<link>(https://[^<]+)</link>', entry)
        if title_m:
            title = title_m.group(1).strip()
            link = link_m.group(1).strip() if link_m else ""
            items.append({"title": title, "link": link})
    return items

def get_daily_news():
    all_items = []
    for _, rss_url in RSS_SOURCES:
        content = fetch_rss(rss_url)
        if content:
            all_items.extend(parse_rss(content, max_items=4))

    seen, unique = set(), []
    for item in all_items:
        if item["title"] not in seen:
            seen.add(item["title"])
            unique.append(item)

    today = datetime.now().strftime("%d.%m.%Y")
    msg = f"🤖 *Günün AI Haberleri — {today}*\n━━━━━━━━━━━━━━━━━━━━\n\n"
    for i, item in enumerate(unique[:8], 1):
        if item["link"]:
            msg += f"*{i}.* [{item['title']}]({item['link']})\n\n"
        else:
            msg += f"*{i}.* {item['title']}\n\n"
    msg += "━━━━━━━━━━━━━━━━━━━━\n_@siberhakkibot_"
    return msg

# ─── Komut İşleyiciler ────────────────────────────────────────────────────────

def handle_start(chat_id, first_name):
    msg = (
        f"Merhaba *{first_name}*! 👋\n\n"
        "Ben *@siberhakkibot* — yapay zeka haberleri ve sorularına yanıt veren bir asistanım.\n\n"
        "*Yapabileceklerim:*\n"
        "• Her gün öğlen 12:00'de AI haberlerini gönderirim\n"
        "• Herhangi bir konuda soru sorabilirsin\n"
        "• `/haberler` ile anlık haber listesi alabilirsin\n\n"
        "Hadi başlayalım! Bir şeyler sor 🚀"
    )
    send_message(chat_id, msg)

def handle_haberler(chat_id):
    send_typing(chat_id)
    send_message(chat_id, "Haberler toplanıyor...")
    news = get_daily_news()
    send_message(chat_id, news)

def handle_yardim(chat_id):
    msg = (
        "*Komutlar:*\n\n"
        "/start — Botu başlat\n"
        "/haberler — Güncel AI haberlerini getir\n"
        "/yardim — Bu mesajı göster\n\n"
        "Veya direkt soru sorabilirsin, sana yanıt veririm!"
    )
    send_message(chat_id, msg)

def handle_question(chat_id, text):
    send_typing(chat_id)
    answer = ask_perplexity(text)
    send_message(chat_id, answer)

# ─── Webhook ─────────────────────────────────────────────────────────────────

@app.route(f"/webhook/{BOT_TOKEN}", methods=["POST"])
def webhook():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"ok": True})

    message = data.get("message") or data.get("edited_message")
    if not message:
        return jsonify({"ok": True})

    chat_id = message["chat"]["id"]
    text = message.get("text", "").strip()
    first_name = message.get("from", {}).get("first_name", "")

    if text.startswith("/start"):
        handle_start(chat_id, first_name)
    elif text.startswith("/haberler"):
        handle_haberler(chat_id)
    elif text.startswith("/yardim") or text.startswith("/help"):
        handle_yardim(chat_id)
    elif text:
        handle_question(chat_id, text)

    return jsonify({"ok": True})

@app.route("/", methods=["GET"])
def index():
    return "siberhakkibot çalışıyor ✅"

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "bot": "@siberhakkibot"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
