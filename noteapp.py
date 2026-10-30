def toggle_hw_book():
    global show_textbook_picker, show_split_book
    if globals().get("show_textbook_picker", False):
        globals()["show_textbook_picker"] = False
        print("[HW] Бутон 3: Менюто за учебници е затворено.")
    elif globals().get("show_split_book", False):
        if "close_textbook" in globals():
            try:
                close_textbook()
            except Exception:
                globals()["show_split_book"] = False
        print("[HW] Бутон 3: Учебникът е затворен.")
    else:
        globals()["show_textbook_picker"] = True
        print("[HW] Бутон 3: Менюто за учебници е отворено.")

current_cursor_pos = (0, 0)
import os
import sys
import io
import time
import json
import sqlite3
import select
import threading
import math
import re
import socket
import subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler
import pygame
import pygame.gfxdraw
from PIL import Image, ImageDraw, ImageFilter, ImageOps, ImageChops

try:
    import fitz  # PyMuPDF
    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False

try:
    import qrcode
    HAS_QR = True
except ImportError:
    HAS_QR = False

try:
    import evdev
    HAS_EVDEV = True
except ImportError:
    HAS_EVDEV = False

try:
    from gpiozero import Button as HWButton
    HAS_GPIO = True
except ImportError:
    HAS_GPIO = False

# ----------------- ПАПКА ЗА УЧЕБНИЦИ -----------------
TEXTBOOKS_DIR = os.path.expanduser("~/textbooks")
os.makedirs(TEXTBOOKS_DIR, exist_ok=True)

def create_sample_textbook_if_empty():
    pdf_files = [f for f in os.listdir(TEXTBOOKS_DIR) if f.lower().endswith(".pdf")]
    if not pdf_files and HAS_FITZ:
        sample_path = os.path.join(TEXTBOOKS_DIR, "Примерен_Учебник.pdf")
        doc = fitz.open()
        p1 = doc.new_page()
        p1.insert_text((50, 80), "Учебник по Математика (Демо)", fontsize=22, color=(0.1, 0.2, 0.6))
        p1.insert_text((50, 130), "Глава 1: Квадратни уравнения", fontsize=16, color=(0.2, 0.2, 0.2))
        p1.insert_text((50, 170), "Общ вид: a*x^2 + b*x + c = 0", fontsize=14, color=(0.1, 0.4, 0.2))
        p1.insert_text((50, 210), "Дискриминанта: D = b^2 - 4*a*c", fontsize=14, color=(0.1, 0.4, 0.2))
        p1.insert_text((50, 250), "Задача 1: Решете уравнението x^2 - 5x + 6 = 0.", fontsize=13, color=(0, 0, 0))

        p2 = doc.new_page()
        p2.insert_text((50, 80), "Глава 2: Геометрия", fontsize=16, color=(0.2, 0.2, 0.2))
        p2.insert_text((50, 130), "Теорема на Питагор: a^2 + b^2 = c^2", fontsize=14, color=(0.1, 0.4, 0.2))
        p2.insert_text((50, 170), "Задача 2: Намерете хипотенузата при катети a=3 и b=4.", fontsize=13, color=(0, 0, 0))

        doc.save(sample_path)
        doc.close()

create_sample_textbook_if_empty()

# ----------------- ПРОФИЛИ -----------------
USERS_FILE = os.path.expanduser("~/users.json")

def load_users():
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list) and len(data) > 0:
                    for u in data:
                        if "grade" not in u:
                            u["grade"] = "10А"
                    return data
        except Exception:
            pass
    defaults = [
        {"id": "alex", "name": "Алекс", "grade": "10А"},
        {"id": "maria", "name": "Мария", "grade": "10Б"},
        {"id": "ivan", "name": "Иван", "grade": "9В"}
    ]
    save_users(defaults)
    return defaults

def save_users(users_list):
    try:
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users_list, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Грешка профили: {e}")

all_users = load_users()
current_user = all_users[0]
try:
    _state_file = os.path.expanduser("~/.current_student_id")
    if not os.path.exists(_state_file) and os.path.exists("/tmp/current_student_id"):
        _state_file = "/tmp/current_student_id"
    if os.path.exists(_state_file):
        with open(_state_file, "r", encoding="utf-8") as _f:
            _saved_id = _f.read().strip()
        if _saved_id:
            for _u in all_users:
                if str(_u.get("id")) == _saved_id or str(_u.get("student_id")) == _saved_id or _u.get("name") == _saved_id:
                    current_user = _u
                    break
except Exception as _e:
    print(f"[USER RESTORE ERROR]: {_e}")

def get_user_db_path(user_id):
    return os.path.expanduser(f"~/notes_{user_id}.db")

# ----------------- GEMINI CONFIG -----------------
GEMINI_API_KEY = ""

CANDIDATE_MODELS = [
    "gemini-3.5-flash-lite",
    "gemini-3.8-flash"
]

_GENAI_CLIENT = None

def get_client():
    global _GENAI_CLIENT
    if _GENAI_CLIENT is None:
        from google import genai
        _GENAI_CLIENT = genai.Client(api_key=GEMINI_API_KEY)
    return _GENAI_CLIENT

def clean_math_text(text):
    if not text:
        return ""
    text = text.replace("$$", "").replace("$", "")
    text = re.sub(r'\\sqrt\[([0-9]+)\]\{([^}]+)\}', r'^\1√(\2)', text)
    text = re.sub(r'\\sqrt\{([^}]+)\}', r'√(\1)', text)
    text = re.sub(r'\\sqrt\b', '√', text)
    text = re.sub(r'\\frac\{([^}]+)\}\{([^}]+)\}', r'(\1)/(\2)', text)
    text = re.sub(r'\\text\{([^}]+)\}', r'\1', text)

    replacements = {
        r'\pm': '±', r'\mp': '∓', r'\times': '×', r'\cdot': '·',
        r'\ast': '*', r'\div': '÷', r'\neq': '≠', r'\approx': '≈',
        r'\leq': '≤', r'\le': '≤', r'\geq': '≥', r'\ge': '≥',
        r'\pi': 'π', r'\infty': '∞', r'\Delta': 'Δ', r'\alpha': 'α',
        r'\beta': 'β', r'\theta': 'θ', r'\lambda': 'λ', r'\mu': 'μ',
        r'\sigma': 'σ', r'\omega': 'ω', r'\Omega': 'Ω', r'\sum': '∑',
        r'\prod': '∏', r'\int': '∫', r'\left(': '(', r'\right)': ')',
        r'\left[': '[', r'\right]': ']', r'\left\{': '{', r'\right\}': '}',
        r'\{': '{', r'\}': '}'
    }
    for k, v in replacements.items():
        text = text.replace(k, v)

    superscripts = {
        '^0': '⁰', '^1': '¹', '^2': '²', '^3': '³', '^4': '⁴',
        '^5': '⁵', '^6': '⁶', '^7': '⁷', '^8': '⁸', '^9': '⁹',
        '^+': '⁺', '^-': '⁻', '^=': '⁼', '^(': '⁽', '^)': '⁾',
        '^n': 'ⁿ', '^x': 'ˣ', '^y': 'ʸ'
    }
    for k, v in superscripts.items():
        text = text.replace(k, v)

    subscripts = {
        '_0': '₀', '_1': '₁', '_2': '₂', '_3': '₃', '_4': '₄',
        '_5': '₅', '_6': '₆', '_7': '₇', '_8': '₈', '_9': '₉',
        '_x': 'ₓ', '_y': 'ᵧ'
    }
    for k, v in subscripts.items():
        text = text.replace(k, v)

    text = re.sub(r'\\([a-zA-Z]+)', r'\1', text)
    return text

def call_gemini_assistant_api(img_bytes):
    from google.genai import types
    client = get_client()

    prompt = (
        "Ти си интелигентен асистент към дигитален учебен чин.\n"
        "Разгледай ръкописа от листа и говори САМО на чист български език (на кирилица):\n"
        "1. Ако има задача, сметка или уравнение -> Реши я подробно и структурирано в раздел '## Решение'.\n"
        "2. Ако има въпрос или команда -> Отговори директно, изчерпателно и точно.\n"
        "3. Ако са лекции, записки или текст -> Направи прегледно обобщение с точки (•).\n"
        "СТРОГО СЕ ЗАБРАНЯВА LaTeX и $! Математическите формули записвай само с чисти символи: √, ², ³, ±, ×, /."
    )
    image_part = types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg")

    for model_name in CANDIDATE_MODELS:
        try:
            resp = client.models.generate_content(
                model=model_name,
                contents=[image_part, prompt],
                config=types.GenerateContentConfig(temperature=0.1, max_output_tokens=1500)
            )
            if resp and resp.text:
                return clean_math_text(resp.text.strip())
        except Exception as e:
            print(f"[Gemini Assistant Error {model_name}]: {e}")
    return "Не успях да се свържа с Gemini. Проверете интернет връзката си."

def call_gemini_beautify_page(img_bytes, existing_context=""):
    from google.genai import types
    client = get_client()

    prompt = (
        "Ти си интелигентен академичен редактор на учебни записки за смарт тетрадка.\n"
        "Оформи новия ръкопис на чист български език (кирилица).\n"
    )
    if existing_context.strip():
        prompt += (
            f"ВЕЧЕ СЪЩЕСТВУВА СЛЕДНИЯТ КОНСПЕКТ НА СТРАНИЦАТА:\n{existing_context}\n\n"
            "ТВОЯТА ЗАДАЧА:\n"
            "1. Анализирай дали новият ръкопис е логическо продължение/допълнение на съществуващия конспект.\n"
            "2. АКО Е ПО СЪЩАТА ТЕМА: Върни ОБЕДИНЕН конспект под същото заглавие, като органично и логично вградиш новите дефиниции, точки или формули.\n"
            "3. АКО Е НОВА ТЕМА ИЛИ РАЗЛИЧЕН ПРЕДМЕТ: Запази първия конспект непокътнат и добави НОВА секция със свое заглавие отдолу.\n"
        )
    else:
        prompt += (
            "Оформи ръкописа в подреден, логичен конспект с ясно заглавие.\n"
        )

    prompt += (
        "СТРОГО БЕЗ LaTeX и БЕЗ знаци за долар ($)! Математическите символи пиши само с Unicode: √, ², ³, ±, ×, /.\n"
        "Върни СТРОГО чист JSON обект без ограждащи форматиращи кавички или markdown кодови блокове:\n"
        '{"sections": [{"title": "Заглавие", "items": [{"type": "header"|"text"|"math", "text": "...", "indent": 0}]}]}\n'
    )

    image_part = types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg")

    for model_name in CANDIDATE_MODELS:
        try:
            resp = client.models.generate_content(
                model=model_name,
                contents=[image_part, prompt],
                config=types.GenerateContentConfig(temperature=0.1, max_output_tokens=1800)
            )
            if resp and resp.text:
                raw = resp.text.strip()
                if raw.startswith("```"):
                    raw = re.sub(r"^```(?:json)?\s*", "", raw)
                    raw = re.sub(r"\s*```$", "", raw)
                try:
                    data = json.loads(raw)
                    if isinstance(data, dict):
                        if "sections" in data:
                            return data["sections"]
                        elif "items" in data:
                            return [data]
                except Exception:
                    pass
        except Exception as e:
            print(f"[Gemini Beautify Error {model_name}]: {e}")
    return None

# ----------------- БАЗА ДАННИ -----------------
def init_db(user_id):
    db_f = get_user_db_path(user_id)
    conn = sqlite3.connect(db_f)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS pages (
            page_num INTEGER PRIMARY KEY,
            ink_data BLOB,
            plan_json TEXT DEFAULT '',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    try:
        c.execute("ALTER TABLE pages ADD COLUMN plan_json TEXT DEFAULT ''")
    except Exception:
        pass
    conn.commit()
    conn.close()

def db_save_page(user_id, page_num, canvas_surf, plan_items=None):
    try:
        db_f = get_user_db_path(user_id)
        raw_png = pygame.image.tostring(canvas_surf, "RGBA")
        pil_img = Image.frombytes("RGBA", canvas_surf.get_size(), raw_png)
        buf = io.BytesIO()
        pil_img.save(buf, format="PNG", optimize=False)
        ink_bytes = buf.getvalue()

        plan_str = json.dumps(plan_items, ensure_ascii=False) if plan_items else ""

        conn = sqlite3.connect(db_f)
        c = conn.cursor()
        c.execute("""
            INSERT INTO pages (page_num, ink_data, plan_json, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(page_num) DO UPDATE SET
                ink_data = excluded.ink_data,
                plan_json = CASE WHEN excluded.plan_json != '' THEN excluded.plan_json ELSE pages.plan_json END,
                updated_at = CURRENT_TIMESTAMP
        """, (page_num, ink_bytes, plan_str))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Грешка запис: {e}")

def db_load_page(user_id, page_num, canvas_w, canvas_h):
    try:
        db_f = get_user_db_path(user_id)
        conn = sqlite3.connect(db_f)
        c = conn.cursor()
        try:
            c.execute("SELECT ink_data, plan_json FROM pages WHERE page_num = ?", (page_num,))
            row = c.fetchone()
        except Exception:
            c.execute("SELECT ink_data, '' FROM pages WHERE page_num = ?", (page_num,))
            row = c.fetchone()
        conn.close()

        plan_items = []
        if row and len(row) > 1 and row[1]:
            try:
                plan_items = json.loads(row[1])
            except Exception:
                plan_items = []

        if row and row[0]:
            surf = pygame.Surface((canvas_w, canvas_h), pygame.SRCALPHA)
            buf = io.BytesIO(row[0])
            pil_img = Image.open(buf)
            raw = pil_img.tobytes("raw", "RGBA")
            s = pygame.image.fromstring(raw, pil_img.size, "RGBA")
            surf.blit(s, (0, 0))
            return surf, plan_items
    except Exception as e:
        print(f"Грешка четене: {e}")
    return None, []

def db_get_all_page_nums(user_id):
    try:
        db_f = get_user_db_path(user_id)
        conn = sqlite3.connect(db_f)
        c = conn.cursor()
        c.execute("SELECT page_num FROM pages ORDER BY page_num ASC")
        rows = c.fetchall()
        conn.close()
        return [r[0] for r in rows]
    except Exception:
        return []

def db_resave_all_pages(user_id, pages_list):
    try:
        db_f = get_user_db_path(user_id)
        conn = sqlite3.connect(db_f)
        c = conn.cursor()
        c.execute("DELETE FROM pages")
        for idx, p in enumerate(pages_list):
            raw_png = pygame.image.tostring(p.canvas, "RGBA")
            pil_img = Image.frombytes("RGBA", p.canvas.get_size(), raw_png)
            buf = io.BytesIO()
            pil_img.save(buf, format="PNG", optimize=False)
            ink_bytes = buf.getvalue()
            c.execute("INSERT INTO pages (page_num, ink_data) VALUES (?, ?)", (idx + 1, ink_bytes))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Грешка преномериране: {e}")

init_db(current_user["id"])
pygame.init()

# ----------------- ЕКРАН И ДИЗАЙН -----------------
screen_w, screen_h = 1920, 1080
screen = pygame.display.set_mode((screen_w, screen_h), pygame.FULLSCREEN | pygame.DOUBLEBUF | pygame.HWSURFACE, 32)
pygame.display.set_caption("Смарт Тетрадка")
pygame.mouse.set_visible(True)

C_CANVAS_BG     = (250, 252, 255)

COLOR_BLACK     = (18, 24, 38, 255)
COLOR_BLUE      = (37, 99, 235, 255)
COLOR_RED       = (225, 29, 72, 255)
COLOR_GREEN     = (16, 185, 129, 255)

AVAILABLE_COLORS = [
    ("Черно", COLOR_BLACK),
    ("Синьо", COLOR_BLUE),
    ("Червено", COLOR_RED),
    ("Зелено", COLOR_GREEN)
]
current_ink_color = COLOR_BLACK

C_NAV_BORDER    = (48, 48, 56)
C_BLUE_ACCENT   = (59, 130, 246)
C_ICON_MUTED    = (140, 144, 156)
C_TEXT_LIGHT    = (248, 248, 252)

CANVAS_W, CANVAS_H = 3840, 2400

font_btn     = pygame.font.SysFont("DejaVu Sans", 13, bold=True)
font_title   = pygame.font.SysFont("DejaVu Sans", 26, bold=True)
font_head    = pygame.font.SysFont("DejaVu Sans", 20, bold=True)
font_body    = pygame.font.SysFont("DejaVu Sans", 17)
font_math    = pygame.font.SysFont("DejaVu Sans", 20, bold=True)
font_pill    = pygame.font.SysFont("DejaVu Sans", 13, bold=True)
font_ai_h    = pygame.font.SysFont("DejaVu Sans", 18, bold=True)
font_ai_body = pygame.font.SysFont("DejaVu Sans", 15)
font_modal   = pygame.font.SysFont("DejaVu Sans", 15, bold=True)
font_input   = pygame.font.SysFont("DejaVu Sans", 16)

# ----------------- ВЕКТОРНИ ИКОНКИ С 4x RETINA СУПЕРСЕМПЛИРАНЕ -----------------
ICONS_CACHE = {}

def get_crisp_icon(name, color_rgba, size=20):
    key = (name, color_rgba, size)
    if key in ICONS_CACHE:
        return ICONS_CACHE[key]

    scale = 4
    s = size * scale
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx, cy = s // 2, s // 2

    if name == "notes":
        w, h = int(s * 0.65), int(s * 0.82)
        r = [cx - w//2, cy - h//2, cx + w//2, cy + h//2]
        draw.rounded_rectangle(r, radius=int(s*0.12), outline=color_rgba, width=int(s*0.08))
        line_w = int(w * 0.55)
        for dy in [-int(h*0.16), 0, int(h*0.16)]:
            draw.line([cx - line_w//2, cy + dy, cx + line_w//2, cy + dy], fill=color_rgba, width=int(s*0.07))

    elif name == "book":
        w, h = int(s * 0.82), int(s * 0.62)
        draw.line([cx, cy + h//2, cx - w//2, cy + h//2 - int(s*0.06)], fill=color_rgba, width=int(s*0.08))
        draw.line([cx - w//2, cy + h//2 - int(s*0.06), cx - w//2, cy - h//2], fill=color_rgba, width=int(s*0.08))
        draw.line([cx - w//2, cy - h//2, cx, cy - h//2 + int(s*0.08)], fill=color_rgba, width=int(s*0.08))
        draw.line([cx, cy + h//2, cx + w//2, cy + h//2 - int(s*0.06)], fill=color_rgba, width=int(s*0.08))
        draw.line([cx + w//2, cy + h//2 - int(s*0.06), cx + w//2, cy - h//2], fill=color_rgba, width=int(s*0.08))
        draw.line([cx + w//2, cy - h//2, cx, cy - h//2 + int(s*0.08)], fill=color_rgba, width=int(s*0.08))
        draw.line([cx, cy - h//2 + int(s*0.08), cx, cy + h//2], fill=color_rgba, width=int(s*0.08))

    elif name == "pdf":
        w, h = int(s * 0.65), int(s * 0.82)
        r = [cx - w//2, cy - h//2, cx + w//2, cy + h//2]
        draw.rounded_rectangle(r, radius=int(s*0.12), outline=color_rgba, width=int(s*0.08))
        ay = cy + int(s * 0.04)
        draw.line([cx, ay - int(s*0.22), cx, ay + int(s*0.14)], fill=color_rgba, width=int(s*0.08))
        draw.line([cx - int(s*0.13), ay + int(s*0.01), cx, ay + int(s*0.14)], fill=color_rgba, width=int(s*0.08))
        draw.line([cx + int(s*0.13), ay + int(s*0.01), cx, ay + int(s*0.14)], fill=color_rgba, width=int(s*0.08))

    elif name == "beautify":
        r = int(s * 0.44)
        pts = [
            (cx, cy - r), (cx + int(r*0.22), cy - int(r*0.22)),
            (cx + r, cy), (cx + int(r*0.22), cy + int(r*0.22)),
            (cx, cy + r), (cx - int(r*0.22), cy + int(r*0.22)),
            (cx - r, cy), (cx - int(r*0.22), cy - int(r*0.22))
        ]
        draw.polygon(pts, fill=color_rgba)
        sx, sy = cx + int(s*0.26), cy - int(s*0.26)
        sr = int(r * 0.42)
        spts = [(sx, sy - sr), (sx + int(sr*0.24), sy), (sx, sy + sr), (sx - int(sr*0.24), sy)]
        draw.polygon(spts, fill=color_rgba)

    elif name == "gemini":
        r = int(s * 0.46)
        pts = [
            (cx, cy - r), (cx + int(r*0.20), cy - int(r*0.20)),
            (cx + r, cy), (cx + int(r*0.20), cy + int(r*0.20)),
            (cx, cy + r), (cx - int(r*0.20), cy + int(r*0.20)),
            (cx - r, cy), (cx - int(r*0.20), cy - int(r*0.20))
        ]
        draw.polygon(pts, fill=color_rgba)

    elif name == "trash":
        w, h = int(s * 0.54), int(s * 0.62)
        r = [cx - w//2, cy - h//2 + int(s*0.10), cx + w//2, cy + h//2]
        draw.rounded_rectangle(r, radius=int(s*0.08), outline=color_rgba, width=int(s*0.08))
        draw.line([cx - w//2 - int(s*0.06), cy - h//2 + int(s*0.08), cx + w//2 + int(s*0.06), cy - h//2 + int(s*0.08)], fill=color_rgba, width=int(s*0.08))
        draw.line([cx - int(s*0.1), cy - h//2 + int(s*0.01), cx + int(s*0.1), cy - h//2 + int(s*0.01)], fill=color_rgba, width=int(s*0.08))

    elif name == "user":
        hr = int(s * 0.22)
        hcy = cy - int(s * 0.18)
        draw.ellipse([cx - hr, hcy - hr, cx + hr, hcy + hr], outline=color_rgba, width=int(s*0.08))
        bw = int(s * 0.65)
        bh = int(s * 0.42)
        draw.arc([cx - bw//2, cy + int(s*0.02), cx + bw//2, cy + int(s*0.02) + bh], start=180, end=360, fill=color_rgba, width=int(s*0.08))

    down = img.resize((size, size), Image.Resampling.LANCZOS)
    surf = pygame.image.frombytes(down.tobytes(), (size, size), "RGBA")
    ICONS_CACHE[key] = surf
    return surf

# ----------------- DOCK КЕШИРАНЕ -----------------
dock_surface_cache = {}
base_dock_cache = {}
hole_cutter_surf = None

def get_hole_cutter(radius=27):
    global hole_cutter_surf
    if hole_cutter_surf is not None:
        return hole_cutter_surf

    scale = 4
    s = (radius * 2) * scale
    pad = 2 * scale
    total_s = s + pad * 2
    img = Image.new("RGBA", (total_s, total_s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([pad, pad, pad + s, pad + s], fill=(255, 255, 255, 255))
    down = img.resize((radius * 2, radius * 2), Image.Resampling.LANCZOS)

    surf = pygame.image.frombytes(down.tobytes(), (radius * 2, radius * 2), "RGBA")
    hole_cutter_surf = surf
    return hole_cutter_surf

def get_static_base_dock(w, h, pad=14, radius=24):
    key = (w, h, pad, radius)
    if key in base_dock_cache:
        return base_dock_cache[key]

    scale = 4
    full_w = w + pad * 2
    full_h = h + pad * 2
    sw = full_w * scale
    sh = full_h * scale
    spad = pad * scale

    base_img = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
    b_draw = ImageDraw.Draw(base_img)
    bar_box = [spad, spad, spad + w * scale, spad + h * scale]
    b_draw.rounded_rectangle(bar_box, radius=radius * scale, fill=(20, 20, 24, 255), outline=(48, 48, 58, 255), width=int(1.2 * scale))

    shadow = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
    s_alpha = base_img.getchannel("A")
    shadow_color = Image.new("RGBA", (sw, sh), (10, 10, 14, 85))
    shadow = ImageChops.composite(shadow_color, shadow, s_alpha)
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=2.5 * scale))
    shadow_offset = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
    shadow_offset.paste(shadow, (0, int(2.5 * scale)))

    canvas = Image.alpha_composite(shadow_offset, base_img)
    down = canvas.resize((full_w, full_h), Image.Resampling.LANCZOS)
    surf = pygame.image.frombytes(down.tobytes(), (full_w, full_h), "RGBA")

    base_dock_cache[key] = surf
    return surf

def render_smooth_dock_curve(w, h, ibx, pad=14, notch_w=76, notch_d=24, radius=24):
    base_surf = get_static_base_dock(w, h, pad, radius)
    dock_surf = base_surf.copy()

    cutter = get_hole_cutter(radius=27)
    cut_x = int(pad + ibx - 27)
    cut_y = int(pad - 7 - 27)

    dock_surf.blit(cutter, (cut_x, cut_y), special_flags=pygame.BLEND_RGBA_SUB)
    return dock_surf

bubble_surface_cache = None

def get_crisp_bubble(size=48):
    global bubble_surface_cache
    if bubble_surface_cache is not None:
        return bubble_surface_cache

    scale = 4
    pad = 4 * scale
    canvas_s = size * scale + pad * 2
    img = Image.new("RGBA", (canvas_s, canvas_s), (0, 0, 0, 0))

    shadow = Image.new("RGBA", (canvas_s, canvas_s), (0, 0, 0, 0))
    s_draw = ImageDraw.Draw(shadow)
    s_box = [pad, pad + 2 * scale, canvas_s - pad, canvas_s - pad + 2 * scale]
    s_draw.ellipse(s_box, fill=(0, 0, 0, 100))
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=2 * scale))

    circle = Image.new("RGBA", (canvas_s, canvas_s), (0, 0, 0, 0))
    c_draw = ImageDraw.Draw(circle)
    c_box = [pad, pad, canvas_s - pad, canvas_s - pad]
    c_draw.ellipse(c_box, fill=(30, 31, 38, 255), outline=(98, 104, 122, 255), width=int(2.2 * scale))

    composite = Image.alpha_composite(shadow, circle)
    final_size = size + 8
    down = composite.resize((final_size, final_size), Image.Resampling.LANCZOS)
    bubble_surface_cache = pygame.image.frombytes(down.tobytes(), (final_size, final_size), "RGBA")
    return bubble_surface_cache

modal_card_cache = {}

def get_crisp_modal_card(w, h, radius=20, border_color=(226, 232, 240, 255), fill_color=(255, 255, 255, 255), pad=20):
    key = (w, h, radius, border_color, fill_color, pad)
    if key in modal_card_cache:
        return modal_card_cache[key]

    scale = 4
    pw, ph = w + pad * 2, h + pad * 2
    sw, sh = pw * scale, ph * scale
    spad = pad * scale

    shadow = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
    s_draw = ImageDraw.Draw(shadow)
    s_box = [spad, spad + int(4 * scale), spad + w * scale, spad + (h + 4) * scale]
    s_draw.rounded_rectangle(s_box, radius=radius * scale, fill=(15, 23, 42, 60))
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=3.5 * scale))

    card = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
    c_draw = ImageDraw.Draw(card)
    c_box = [spad, spad, spad + w * scale, spad + h * scale]
    c_draw.rounded_rectangle(
        c_box,
        radius=radius * scale,
        fill=fill_color,
        outline=border_color,
        width=int(1.2 * scale)
    )

    comp = Image.alpha_composite(shadow, card)
    down = comp.resize((pw, ph), Image.Resampling.LANCZOS)
    surf = pygame.image.frombytes(down.tobytes(), (pw, ph), "RGBA")
    modal_card_cache[key] = (surf, pad)
    return modal_card_cache[key]

def generate_dot_grid():
    bg = pygame.Surface((CANVAS_W, CANVAS_H), depth=24)
    bg.fill(C_CANVAS_BG)
    step = 28
    dot_color = (205, 212, 224)
    for x in range(step, CANVAS_W, step):
        for y in range(step, CANVAS_H, step):
            pygame.gfxdraw.filled_circle(bg, x, y, 1, dot_color)
            pygame.gfxdraw.aacircle(bg, x, y, 1, dot_color)
    return bg

PAGE_BACKGROUND = generate_dot_grid()

STATIC_OVERLAY = pygame.Surface((1920, 1080), pygame.SRCALPHA)
STATIC_OVERLAY.fill((15, 23, 42, 140))

class Page:
    __slots__ = ['canvas', 'history', 'ink_bounds', 'has_ink', 'has_unprocessed_ink', 'content_bottom_y', 'formatted_items']
    def __init__(self, user_id=None, page_num=None, canvas_surf=None):
        if canvas_surf:
            self.canvas = canvas_surf
            self.has_ink = True
        elif user_id and page_num is not None:
            res = db_load_page(user_id, page_num, CANVAS_W, CANVAS_H)
            if isinstance(res, tuple):
                loaded_surf, loaded_plan = res
            else:
                loaded_surf, loaded_plan = res, []

            if loaded_surf:
                self.canvas = loaded_surf
                self.has_ink = True
            else:
                self.canvas = pygame.Surface((CANVAS_W, CANVAS_H), pygame.SRCALPHA)
                self.has_ink = False
            self.formatted_items = loaded_plan if loaded_plan else []

        self.has_unprocessed_ink = False
        self.history = [self.canvas.copy()]
        self.ink_bounds = [CANVAS_W, CANVAS_H, 0, 0]
        self.content_bottom_y = 100
        if not hasattr(self, 'formatted_items'):
            self.formatted_items = []

    def track_point(self, x, y):
        self.has_ink = True
        self.has_unprocessed_ink = True
        if x < self.ink_bounds[0]: self.ink_bounds[0] = x
        if y < self.ink_bounds[1]: self.ink_bounds[1] = y
        if x > self.ink_bounds[2]: self.ink_bounds[2] = x
        if y > self.ink_bounds[3]: self.ink_bounds[3] = y

def load_user_pages(user_id):
    init_db(user_id)
    p_nums = db_get_all_page_nums(user_id)
    if p_nums:
        loaded = []
        for num in p_nums:
            loaded.append(Page(user_id=user_id, page_num=num))
        return loaded
    return [Page(user_id=user_id, page_num=1)]

pages = load_user_pages(current_user["id"])
curr_idx = 0
is_beautifying = False

show_ai_drawer = False
drawer_width = 460
drawer_scroll_y = 0
drawer_max_scroll = 0
drawer_is_dragging = False
drawer_drag_start_y = 0
is_analyzing = False
ai_analysis_text = ""

# PDF Export & QR предварително кеширани
show_pdf_modal = False
http_server_running = False

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

CACHED_LOCAL_IP = get_local_ip()
pdf_download_url = f"http://{CACHED_LOCAL_IP}:8080/notes.pdf"

class PDFDownloadHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        pdf_file = os.path.expanduser("~/notes.pdf")
        if os.path.exists(pdf_file):
            with open(pdf_file, 'rb') as f:
                data = f.read()
            self.send_response(200)
            self.send_header('Content-Type', 'application/pdf')
            self.send_header('Content-Disposition', 'attachment; filename="notes.pdf"')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        else:
            self.send_error(404, "File not found")

    def log_message(self, format, *args):
        pass

def start_pdf_server():
    global http_server_running
    if http_server_running:
        return
    ip = CACHED_LOCAL_IP
    port = 8080
    try:
        server = HTTPServer((ip, port), PDFDownloadHandler)
        http_server_running = True
        threading.Thread(target=server.serve_forever, daemon=True).start()
    except Exception as e:
        print(f"[PDF Server error]: {e}")

start_pdf_server()

if HAS_QR:
    try:
        _qr = qrcode.QRCode(box_size=6, border=2)
        _qr.add_data(pdf_download_url)
        _qr.make(fit=True)
        _qr_pil = _qr.make_image(fill_color="black", back_color="white").convert("RGB")
        pdf_qr_surf = pygame.image.fromstring(_qr_pil.tobytes(), _qr_pil.size, "RGB")
    except Exception:
        pdf_qr_surf = None
else:
    pdf_qr_surf = None

def export_all_to_pdf_and_show_qr():
    global show_pdf_modal
    show_pdf_modal = True

    def _worker():
        try:
            save_current_page()
            pil_pages = []
            for p in list(pages):
                time.sleep(0.01)
                raw_bg = pygame.image.tostring(PAGE_BACKGROUND, "RGB")
                raw_ink = pygame.image.tostring(p.canvas, "RGBA")

                bg_img = Image.frombytes("RGB", (CANVAS_W, CANVAS_H), raw_bg)
                ink_img = Image.frombytes("RGBA", (CANVAS_W, CANVAS_H), raw_ink)

                bg_img.paste(ink_img, (0, 0), ink_img)
                downscaled = bg_img.resize((1920, 1200), Image.Resampling.BILINEAR)
                pil_pages.append(downscaled)

            pdf_path = os.path.expanduser("~/notes.pdf")
            if pil_pages:
                pil_pages[0].save(pdf_path, "PDF", resolution=96.0, save_all=True, append_images=pil_pages[1:])
        except Exception as e:
            print(f"[PDF Export Error]: {e}")

    threading.Thread(target=_worker, daemon=True).start()

# Модали за потребители
show_user_modal = False
show_new_user_modal = False
input_new_name = ""
input_new_grade = ""
input_focus = "name"

# Учебници
show_textbook_picker = False
show_split_book = False
current_book_doc = None
current_book_filename = ""
book_page_idx = 0
book_page_surf = None

def get_textbook_files():
    if not os.path.exists(TEXTBOOKS_DIR):
        return []
    all_pdfs = [f for f in os.listdir(TEXTBOOKS_DIR) if f.lower().endswith(".pdf")]

    # Взимаме класа на текущия ученик
    u_grade = ""
    if "current_user" in globals() and isinstance(current_user, dict):
        u_grade = str(current_user.get("grade", "")).strip().upper()

    meta_path = os.path.join(TEXTBOOKS_DIR, "metadata.json")
    if os.path.exists(meta_path) and u_grade:
        try:
            import json
            with open(meta_path, "r", encoding="utf-8") as mf:
                meta = json.load(mf)
            # Филтрираме само тези, които съвпадат по клас
            filtered = [f for f in all_pdfs if meta.get(f, {}).get("grade", "").strip().upper() == u_grade]
            return sorted(filtered)
        except Exception:
            pass
    return sorted(all_pdfs)

def open_textbook(filename):
    global current_book_doc, current_book_filename, book_page_idx, show_split_book, show_textbook_picker
    if not HAS_FITZ:
        show_toast("Инсталирайте: pip install pymupdf")
        return
    path = os.path.join(TEXTBOOKS_DIR, filename)
    try:
        current_book_doc = fitz.open(path)
        current_book_filename = filename
        book_page_idx = 0
        show_split_book = True
        show_textbook_picker = False
        render_book_page()
        show_toast(f"Отворен: {filename[:16]}")
    except Exception as e:
        show_toast(f"Грешка PDF: {e}")

def close_textbook():
    global current_book_doc, show_split_book, book_page_surf
    if current_book_doc:
        try:
            current_book_doc.close()
        except Exception:
            pass
    current_book_doc = None
    book_page_surf = None
    show_split_book = False

def render_book_page():
    global book_page_surf
    if not current_book_doc or not HAS_FITZ:
        return
    try:
        sw, sh = screen.get_size()
        book_panel_w = int(sw * 0.40)
        avail_w = max(100, book_panel_w - 24)
        avail_h = max(100, sh - 76)

        page = current_book_doc.load_page(book_page_idx)
        rect = page.rect
        scale = min(avail_w / max(1, rect.width), avail_h / max(1, rect.height))
        mat = fitz.Matrix(scale, scale)
        pix = page.get_pixmap(matrix=mat, alpha=False)

        raw = pix.samples
        book_page_surf = pygame.image.fromstring(raw, (pix.width, pix.height), "RGB")
    except Exception as e:
        print(f"Грешка рендер учебник: {e}")

def book_next_page():
    global book_page_idx
    if current_book_doc and book_page_idx < len(current_book_doc) - 1:
        book_page_idx += 1
        render_book_page()

def book_prev_page():
    global book_page_idx
    if current_book_doc and book_page_idx > 0:
        book_page_idx -= 1
        render_book_page()

toast_msg = ""
toast_time = 0.0

def show_toast(msg):
    global toast_msg, toast_time
    toast_msg = msg
    toast_time = time.time() + 2.5

# ----------------- ИНСТРУМЕНТИ И МАСТИЛО -----------------
offset_x, offset_y = 0, 0
active_tool = "pen"
is_holding_pan = False
is_holding_eraser = False

is_drawing = False
current_action = None
pan_start_mouse = (0, 0)
pan_start_offset = (0, 0)

current_pressure = 0.5
last_canvas_pt = None
mouse_x, mouse_y = 0, 0

anim_bubble_x = None
anim_island_x = None

def get_effective_tool():
    if is_holding_pan:
        return "pan"
    if is_holding_eraser:
        return "eraser"
    return active_tool

def push_undo():
    p = pages[curr_idx]
    if len(p.history) >= 15:
        p.history.pop(0)
    p.history.append(p.canvas.copy())

def undo():
    p = pages[curr_idx]
    if len(p.history) > 1:
        p.history.pop()
        p.canvas.fill((0, 0, 0, 0))
        p.canvas.blit(p.history[-1], (0, 0))

def clear_current_page():
    p = pages[curr_idx]
    push_undo()
    p.canvas.fill((0, 0, 0, 0))
    p.has_ink = False
    p.has_unprocessed_ink = False
    p.ink_bounds = [CANVAS_W, CANVAS_H, 0, 0]
    p.formatted_items = []
    p.content_bottom_y = 100
    save_current_page()

def delete_current_page():
    global curr_idx, pages, offset_x, offset_y
    if len(pages) > 1:
        pages.pop(curr_idx)
        if curr_idx >= len(pages):
            curr_idx = len(pages) - 1
        offset_x, offset_y = 0, 0
        threading.Thread(target=lambda: db_resave_all_pages(current_user["id"], pages), daemon=True).start()
        show_toast("Страницата е изтрита")
    else:
        clear_current_page()
        show_toast("Страницата е изчистена")

def save_current_page():
    p = pages[curr_idx]
    db_save_page(current_user["id"], curr_idx + 1, p.canvas, getattr(p, 'formatted_items', []))

def next_page():
    global curr_idx, offset_x, offset_y
    save_current_page()
    if curr_idx < len(pages) - 1:
        curr_idx += 1
        offset_x, offset_y = 0, 0

def prev_page():
    global curr_idx, offset_x, offset_y
    if curr_idx > 0:
        save_current_page()
        curr_idx -= 1
        offset_x, offset_y = 0, 0

def add_blank_page():
    global curr_idx, offset_x, offset_y
    save_current_page()
    new_p = Page(user_id=current_user["id"], page_num=None)
    insert_pos = curr_idx + 1
    pages.insert(insert_pos, new_p)
    curr_idx = insert_pos
    offset_x, offset_y = 0, 0
    save_current_page()
    threading.Thread(target=lambda: db_resave_all_pages(current_user["id"], pages), daemon=True).start()

def wrap_text(text, font, max_w):
    words = text.split(" ")
    lines = []
    curr = ""
    for w in words:
        test = (curr + " " + w).strip()
        if font.size(test)[0] <= max_w:
            curr = test
        else:
            if curr: lines.append(curr)
            curr = w
    if curr: lines.append(curr)
    return lines

def trigger_gemini_analysis():
    global show_ai_drawer, is_analyzing, ai_analysis_text, drawer_scroll_y
    source_p = pages[curr_idx]

    if is_analyzing:
        show_ai_drawer = True
        return

    bbox = source_p.canvas.get_bounding_rect()
    has_content = (
        source_p.has_ink or
        getattr(source_p, "has_unprocessed_ink", False) or
        (hasattr(source_p, "formatted_items") and bool(source_p.formatted_items)) or
        (bbox.w > 10 and bbox.h > 10)
    )

    if not has_content:
        show_ai_drawer = not show_ai_drawer
        if show_ai_drawer:
            ai_analysis_text = "Листът е празен. Напишете задача на страницата и натиснете отново Gemini."
        return

    show_ai_drawer = True
    is_analyzing = True
    drawer_scroll_y = 0
    ai_analysis_text = "Анализиране с Gemini..."

    def _worker():
        global is_analyzing, ai_analysis_text
        try:
            min_x, min_y, max_x, max_y = source_p.ink_bounds
            if max_x < min_x or max_y < min_y:
                if bbox.w > 10 and bbox.h > 10:
                    min_x, min_y, max_x, max_y = bbox.left, bbox.top, bbox.right, bbox.bottom
                else:
                    min_x, min_y = 0, 0
                    max_x, max_y = screen.get_size()

            pad = 50
            cx = max(0, min_x - pad)
            cy = max(0, min_y - pad)
            cw = max(64, min(CANVAS_W - cx, (max_x - min_x) + pad * 2))
            ch = max(64, min(CANVAS_H - cy, (max_y - min_y) + pad * 2))

            crop_rect = pygame.Rect(cx, cy, cw, ch)
            crop_surf = pygame.Surface((cw, ch), depth=24)
            crop_surf.blit(PAGE_BACKGROUND, (0, 0), area=crop_rect)
            crop_surf.blit(source_p.canvas, (0, 0), area=crop_rect)

            raw = pygame.image.tostring(crop_surf, "RGB")
            pil_img = Image.frombytes("RGB", (cw, ch), raw)
            if pil_img.width > 1024 or pil_img.height > 1024:
                pil_img.thumbnail((1024, 1024), Image.Resampling.BILINEAR)

            buf = io.BytesIO()
            pil_img.save(buf, format="JPEG", quality=85)
            img_bytes = buf.getvalue()

            res = call_gemini_assistant_api(img_bytes)
            ai_analysis_text = res
        except Exception as e:
            ai_analysis_text = f"Грешка: {e}"
        finally:
            is_analyzing = False

    threading.Thread(target=_worker, daemon=True).start()

def trigger_beautify_to_new_page():
    global is_beautifying, curr_idx, offset_x, offset_y
    source_p = pages[curr_idx]
    if is_beautifying:
        return

    if not getattr(source_p, "has_unprocessed_ink", False):
        show_toast("Листът няма нов ръкопис за оформяне!")
        return

    source_p.has_unprocessed_ink = False
    is_beautifying = True
    show_toast("Оформяне с Gemini...")

    def _worker():
        global is_beautifying, curr_idx, offset_x, offset_y
        try:
            min_x, min_y, max_x, max_y = source_p.ink_bounds
            if max_x < min_x or max_y < min_y:
                min_x, min_y = 0, 0
                max_x, max_y = screen.get_size()

            pad = 50
            cx = max(0, min_x - pad)
            cy = max(0, min_y - pad)
            cw = max(64, min(CANVAS_W - cx, (max_x - min_x) + pad * 2))
            ch = max(64, min(CANVAS_H - cy, (max_y - min_y) + pad * 2))

            crop_rect = pygame.Rect(cx, cy, cw, ch)
            crop_surf = pygame.Surface((cw, ch), depth=24)
            crop_surf.blit(PAGE_BACKGROUND, (0, 0), area=crop_rect)
            crop_surf.blit(source_p.canvas, (0, 0), area=crop_rect)

            raw = pygame.image.tostring(crop_surf, "RGB")
            pil_img = Image.frombytes("RGB", (cw, ch), raw)
            if pil_img.width > 1024 or pil_img.height > 1024:
                pil_img.thumbnail((1024, 1024), Image.Resampling.BILINEAR)

            buf = io.BytesIO()
            pil_img.save(buf, format="JPEG", quality=85)
            img_bytes = buf.getvalue()

            existing_ctx = ""
            if hasattr(source_p, "formatted_items") and source_p.formatted_items:
                for sec in source_p.formatted_items:
                    existing_ctx += f"Тема: {sec.get('title', '')}\n"
                    for item in sec.get("items", []):
                        existing_ctx += f" - {item.get('text', '')}\n"

            print('[DEBUG BEAUTIFY] Дължина на existing_ctx:', len(existing_ctx))
            if existing_ctx:
                print('[DEBUG BEAUTIFY] Контекст:', repr(existing_ctx[:120]))
            else:
                print('[DEBUG BEAUTIFY] ВНИМАНИЕ: Няма подаден съществуващ контекст!')
            sections = call_gemini_beautify_page(img_bytes, existing_context=existing_ctx)
            print('[DEBUG BEAUTIFY] Върнати секции:', len(sections) if sections else 0)

            if sections and isinstance(sections, list):
                push_undo()
                target_p = source_p
                target_p.formatted_items = sections
                target_p.canvas.fill((0, 0, 0, 0))

                cur_y = 100
                base_x = 90

                for s_idx, sec in enumerate(target_p.formatted_items):
                    s_title = sec.get("title", "").strip()
                    if s_title:
                        if s_idx > 0:
                            cur_y += 30
                            pygame.draw.line(target_p.canvas, (203, 213, 225), (base_x, cur_y), (base_x + 920, cur_y), 2)
                            cur_y += 35
                        t_surf = font_title.render(s_title, True, C_BLUE_ACCENT)
                        target_p.canvas.blit(t_surf, (base_x, cur_y))
                        cur_y += t_surf.get_height() + 10
                        pygame.draw.line(target_p.canvas, (219, 234, 254), (base_x, cur_y), (base_x + 550, cur_y), 3)
                        cur_y += 32

                    for item in sec.get("items", []):
                        i_type = item.get("type", "text")
                        txt = item.get("text", "").strip()
                        if not txt:
                            continue
                        indent = item.get("indent", 0)
                        item_x = base_x + indent * 36

                        if i_type == "header":
                            cur_y += 16
                            h_surf = font_head.render(txt, True, (30, 41, 59))
                            target_p.canvas.blit(h_surf, (item_x, cur_y))
                            cur_y += 38
                        elif i_type == "math":
                            txt_math = clean_math_text(txt)
                            m_surf = font_math.render(txt_math, True, C_BLUE_ACCENT)
                            target_p.canvas.blit(m_surf, (item_x + 10, cur_y))
                            cur_y += 38
                        else:
                            wrapped = wrap_text(txt, font_body, 1200)
                            for l_idx, w_line in enumerate(wrapped):
                                bullet = "• " if (l_idx == 0 and indent > 0) else ""
                                b_surf = font_body.render(f"{bullet}{w_line}", True, (51, 65, 85))
                                target_p.canvas.blit(b_surf, (item_x, cur_y))
                                cur_y += 30

                target_p.content_bottom_y = cur_y + 30
                target_p.has_ink = False
                target_p.has_unprocessed_ink = False
                target_p.ink_bounds = [CANVAS_W, CANVAS_H, 0, 0]
                save_current_page()
                print(f"[BEAUTIFY] Готово! Натрупани {len(target_p.formatted_items)} секции.")
        except Exception as e:
            print(f"[Beautify error]: {e}")
            show_toast(f"Грешка: {e}")
        finally:
            is_beautifying = False

    threading.Thread(target=_worker, daemon=True).start()

# ----------------- ПРОФИЛИ -----------------
def switch_user(user_obj):
    global current_user, pages, curr_idx, offset_x, offset_y, show_user_modal, show_new_user_modal
    if user_obj["id"] == current_user["id"]:
        show_user_modal = False
        show_new_user_modal = False
        return

    save_current_page()
    current_user = user_obj
    try:
        _u_val = str(current_user.get("id") or current_user.get("name", ""))
        with open(os.path.expanduser("~/.current_student_id"), "w", encoding="utf-8") as _sf:
            _sf.write(_u_val)
        with open("/tmp/current_student_id", "w", encoding="utf-8") as _sf:
            _sf.write(_u_val)
    except Exception as _e:
        print(f"[USER SAVE ERROR]: {_e}")
    pages = load_user_pages(current_user["id"])
    curr_idx = 0
    offset_x, offset_y = 0, 0
    show_user_modal = False
    show_new_user_modal = False
    show_toast(f"Вход: {current_user['name']} • {current_user.get('grade', '')}")

def submit_new_user():
    global all_users, input_new_name, input_new_grade, show_new_user_modal
    name_clean = input_new_name.strip()
    grade_clean = input_new_grade.strip()

    if not name_clean:
        name_clean = f"Ученик {len(all_users) + 1}"
    if not grade_clean:
        grade_clean = "10А"

    new_id = f"student_{int(time.time())}"
    new_u = {"id": new_id, "name": name_clean, "grade": grade_clean}
    all_users.append(new_u)
    save_users(all_users)
    switch_user(new_u)

# ----------------- EVDEV DRIVER (WACOM PEN & BUTTONS) -----------------
def start_wacom_thread():
    if not HAS_EVDEV:
        return

    pen_dev = None
    pad_dev = None

    for p in evdev.list_devices():
        try:
            d = evdev.InputDevice(p)
            name = d.name.lower()
            if "wacom" in name:
                if "pen" in name:
                    pen_dev = d
                elif "pad" in name:
                    pad_dev = d
        except Exception:
            pass

    if not pen_dev:
        return

    abs_caps = dict(pen_dev.capabilities().get(evdev.ecodes.EV_ABS, []))
    info_x = abs_caps.get(evdev.ecodes.ABS_X)
    info_y = abs_caps.get(evdev.ecodes.ABS_Y)
    info_p = abs_caps.get(evdev.ecodes.ABS_PRESSURE)

    min_x, max_x = (info_x.min, info_x.max) if info_x else (0, 15200)
    min_y, max_y = (info_y.min, info_y.max) if info_y else (0, 9500)
    max_p = info_p.max if info_p else 2047

    devices = [pen_dev]
    if pad_dev:
        devices.append(pad_dev)

    def _loop():
        global current_pressure, is_holding_eraser, is_holding_pan
        global offset_x, offset_y

        cur_x = (min_x + max_x) // 2
        cur_y = (min_y + max_y) // 2
        is_touching = False
        btn_eraser_down = False
        btn_pan_down = False
        last_motion_pos = None

        dev_map = {d.fd: d for d in devices}

        while True:
            try:
                r, _, _ = select.select(dev_map.keys(), [], [], 0.5)
                for fd in r:
                    dev = dev_map[fd]
                    for ev in dev.read():
                        if ev.type == evdev.ecodes.EV_ABS:
                            if ev.code == evdev.ecodes.ABS_X:
                                cur_x = ev.value
                            elif ev.code == evdev.ecodes.ABS_Y:
                                cur_y = ev.value
                            elif ev.code == evdev.ecodes.ABS_PRESSURE:
                                current_pressure = max(0.0, min(1.0, ev.value / max(1, max_p)))

                        elif ev.type == evdev.ecodes.EV_KEY:
                            sw, sh = screen.get_size()
                            sx = int((cur_x - min_x) / max(1, (max_x - min_x)) * sw)
                            sy = int((cur_y - min_y) / max(1, (max_y - min_y)) * sh)
                            pos = (max(0, min(sw - 1, sx)), max(0, min(sh - 1, sy)))

                            if ev.code in (evdev.ecodes.BTN_STYLUS, 331):
                                btn_eraser_down = (ev.value == 1)
                                is_holding_eraser = btn_eraser_down
                                if is_touching:
                                    b = 3 if btn_eraser_down else 1
                                    pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN, {'pos': pos, 'button': b}))

                            elif ev.code in (evdev.ecodes.BTN_STYLUS2, 332):
                                btn_pan_down = (ev.value == 1)
                                is_holding_pan = btn_pan_down
                                if not btn_pan_down:
                                    last_motion_pos = None

                            elif ev.code in (evdev.ecodes.BTN_TOUCH, 330):
                                is_touching = (ev.value == 1)
                                if not btn_pan_down:
                                    target_btn = 3 if btn_eraser_down else 1
                                    t = pygame.MOUSEBUTTONDOWN if is_touching else pygame.MOUSEBUTTONUP
                                    pygame.event.post(pygame.event.Event(t, {'pos': pos, 'button': target_btn}))

                            elif ev.value == 1:
                                if ev.code in (evdev.ecodes.BTN_0, 256, 273):
                                    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, {'key': pygame.K_LEFT}))
                                elif ev.code in (evdev.ecodes.BTN_1, 257, 277):
                                    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, {'key': pygame.K_RIGHT}))
                                elif ev.code in (evdev.ecodes.BTN_2, 258, 272):
                                    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, {'key': pygame.K_z}))
                                elif ev.code in (evdev.ecodes.BTN_3, 259, 278):
                                    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, {'key': pygame.K_n}))

                        elif ev.type == evdev.ecodes.EV_SYN and ev.code == evdev.ecodes.SYN_REPORT:
                            sw, sh = screen.get_size()
                            sx = int((cur_x - min_x) / max(1, (max_x - min_x)) * sw)
                            sy = int((cur_y - min_y) / max(1, (max_y - min_y)) * sh)
                            pos = (max(0, min(sw - 1, sx)), max(0, min(sh - 1, sy)))

                            if btn_pan_down:
                                if last_motion_pos is not None:
                                    dx = pos[0] - last_motion_pos[0]
                                    dy = pos[1] - last_motion_pos[1]
                                    max_off_x = max(0, CANVAS_W - max(100, sw - globals().get("book_w", 0)))
                                    max_off_y = max(0, CANVAS_H - sh)
                                    offset_x = max(0, min(max_off_x, offset_x - dx))
                                    offset_y = max(0, min(max_off_y, offset_y - dy))
                                last_motion_pos = pos
                            else:
                                last_motion_pos = pos

                            btn_code = 3 if btn_eraser_down else (1 if is_touching else 0)
                            pygame.event.post(pygame.event.Event(pygame.MOUSEMOTION, {
                                'pos': pos,
                                'rel': (0, 0),
                                'buttons': (1 if is_touching else 0, 0, 1 if btn_eraser_down else 0)
                            }))

            except Exception:
                time.sleep(0.05)

    threading.Thread(target=_loop, daemon=True).start()

start_wacom_thread()

# ----------------- TCP СЛУШАТЕЛ ЗА УЧИТЕЛСКО БЮРО (PORT 5005) -----------------
def start_remote_control_listener():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server_socket.bind(('0.0.0.0', 5005))
        server_socket.listen(5)
        print("[REMOTE] Слушане за команди от учителско бюро на порт 5005...")
    except Exception as e:
        print(f"[REMOTE] Грешка при стартиране на порт 5005: {e}")
        return

    def _listen_loop():
        while True:
            try:
                client_sock, _ = server_socket.accept()
                data = client_sock.recv(4096)
                if not data:
                    client_sock.close()
                    continue

                payload = json.loads(data.decode('utf-8'))
                print(f"[REMOTE] Получена команда: {payload}")

                action = payload.get("action")
                if action == "login":
                    user_data = payload.get("student", {})
                    u_id = user_data.get("id") or user_data.get("name", "student").lower()
                    u_name = user_data.get("name", "Ученик")
                    u_grade = user_data.get("grade", "10А")
                    google_email = user_data.get("email", "")

                    target_user = None
                    for u in all_users:
                        if u.get("id") == u_id or u.get("name") == u_name:
                            target_user = u
                            break

                    if not target_user:
                        target_user = {"id": u_id, "name": u_name, "grade": u_grade}
                        all_users.append(target_user)
                        save_users(all_users)

                    switch_user(target_user)

                    if google_email:
                        classroom_url = f"[https://classroom.google.com/u/?authuser=](https://classroom.google.com/u/?authuser=){google_email}"
                    else:
                        classroom_url = "[https://classroom.google.com](https://classroom.google.com)"

                    subprocess.Popen([
                        "chromium-browser",
                        "--no-first-run",
                        "--disable-restore-session-state",
                        classroom_url
                    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

                client_sock.sendall(b'{"status": "ok"}')
                client_sock.close()
            except Exception as e:
                print(f"[REMOTE ERROR]: {e}")
                time.sleep(0.5)

    threading.Thread(target=_listen_loop, daemon=True).start()

start_remote_control_listener()

# ----------------- ХАРДУЕРНИ БУТОНИ -----------------
EVENT_BTN_NOTES     = pygame.USEREVENT + 10
EVENT_BTN_CLASSROOM = pygame.USEREVENT + 11
EVENT_BTN_BOOK      = pygame.USEREVENT + 12
EVENT_BTN_AI        = pygame.USEREVENT + 13

classroom_proc = None

def open_classroom():
    print("[HW] Бутон 2: Запазване и превключване към Classroom...")
    try:
        if "save_current_page" in globals():
            save_current_page()

        u = globals().get("current_user", {})
        if not isinstance(u, dict):
            u = {}

        user_id = u.get("id") or u.get("student_id") or u.get("name") or "guest"
        user_email = (
            u.get("email") or
            u.get("google_email") or
            u.get("student_email") or
            u.get("mail") or
            ""
        )

        # Ако имейлът все още е празен, опитваме да го намерим от глобалните променливи
        if not user_email:
            for k in ["current_email", "student_email", "STUDENT_EMAIL"]:
                if k in globals() and globals()[k]:
                    user_email = str(globals()[k])
                    break

        with open("/tmp/current_student_id", "w", encoding="utf-8") as f:
            f.write(str(user_id).strip())
        with open("/tmp/current_student_email", "w", encoding="utf-8") as f:
            f.write(str(user_email).strip())

        print(f"[CLASSROOM SYNC] ID: {user_id} | Email: {user_email}")
    except Exception as e:
        print(f"[SAVE ERROR]: {e}")
    os._exit(42)

def close_classroom():
    pass

if HAS_GPIO:
    try:
        btn_hw_notes = HWButton(17, pull_up=True, bounce_time=0.08)
        btn_hw_class = HWButton(26, pull_up=True, bounce_time=0.08)
        btn_hw_book  = HWButton(22, pull_up=True, bounce_time=0.08)
        btn_hw_ai    = HWButton(16, pull_up=True, bounce_time=0.08)

        btn_hw_notes.when_pressed = close_classroom
        btn_hw_class.when_pressed = open_classroom
        btn_hw_book.when_pressed  = toggle_hw_book
        btn_hw_ai.when_pressed    = lambda: pygame.event.post(pygame.event.Event(EVENT_BTN_AI))
        print("[HW BUTTONS] Готови на GPIO 17, 26, 22, 16")
    except Exception as e:
        print(f"[HW BUTTONS ERROR]: {e}")

clock = pygame.time.Clock()
start_app_time = time.time()

_last_session_check = 0
while True:
    # Автоматично засичане на нова карта от уеб дашборда
    if time.time() - _last_session_check > 0.4:
        _last_session_check = time.time()
        try:
            _sess_file = "/tmp/current_student_id"
            if os.path.exists(_sess_file):
                with open(_sess_file, "r", encoding="utf-8") as _sf:
                    _remote_id = _sf.read().strip()
                if _remote_id and "current_user" in globals() and current_user.get("id") != _remote_id:
                    # Търсим съвпадащ потребител или зареждаме от users.json
                    all_users = load_users()
                    target_u = next((u for u in all_users if u.get("id") == _remote_id), None)
                    if not target_u:
                        # Ако не съществува в users.json, взимаме данните от current_session.json
                        if os.path.exists("/home/bobo/current_session.json"):
                            import json
                            with open("/home/bobo/current_session.json", "r", encoding="utf-8") as _csf:
                                _cdata = json.load(_csf)
                            target_u = {
                                "id": _remote_id,
                                "name": _cdata.get("name", _remote_id),
                                "grade": _cdata.get("grade", "10Г"),
                                "email": _cdata.get("email", "")
                            }
                            all_users.append(target_u)
                            save_users(all_users)
                    if target_u:
                        switch_user(target_u)
        except Exception as _e:
            pass

    if globals().get("is_in_classroom", False):
        time.sleep(0.1)
        continue
    current_time = time.time()
    anim_t = current_time - start_app_time
    page = pages[curr_idx]

    pen_stroke_width = max(3, int(3.0 + current_pressure * 4.0))
    eraser_radius = int(16 + current_pressure * 32)
    effective_tool = get_effective_tool()

    sw, sh = screen.get_size()

    # Split-Screen
    book_w = int(sw * 0.40) if show_split_book else 0
    canvas_w = sw - book_w
    canvas_rect = pygame.Rect(book_w, 0, canvas_w, sh)

    # ----------------- DOCK ГЕОМЕТРИЯ -----------------
    bar_w = 808
    target_bar_x = book_w + (canvas_w - bar_w) // 2
    if anim_island_x is None:
        anim_island_x = float(target_bar_x)
    else:
        anim_island_x += (target_bar_x - anim_island_x) * 0.22

    bar_x = int(anim_island_x)
    bar_y = 52
    bar_h = 58
    bar_rect = pygame.Rect(bar_x, bar_y, bar_w, bar_h)

    r_user = pygame.Rect(bar_x + 10, bar_y + 9, 96, 40)

    color_rects = []
    c_start_x = bar_x + 120
    for i in range(4):
        color_rects.append(pygame.Rect(c_start_x + i * 20, bar_y + 20, 14, 18))
    r_clear = pygame.Rect(c_start_x + 86, bar_y + 9, 36, 40)

    sep1_x = bar_x + 252

    r_del  = pygame.Rect(sep1_x + 6, bar_y + 11, 24, 36)
    r_prev = pygame.Rect(sep1_x + 30, bar_y + 11, 24, 36)
    r_pill = pygame.Rect(sep1_x + 56, bar_y + 11, 62, 36)
    r_next = pygame.Rect(sep1_x + 120, bar_y + 11, 24, 36)
    r_add  = pygame.Rect(sep1_x + 144, bar_y + 11, 24, 36)
    globals()["g_r_del"]  = r_del
    globals()["g_r_prev"] = r_prev
    globals()["g_r_next"] = r_next
    globals()["g_r_add"]  = r_add
    globals()["g_r_clear"] = r_clear

    sep2_x = sep1_x + 172

    r_tab_notes    = pygame.Rect(sep2_x + 8,   bar_y + 6, 66, 46)
    r_tab_book     = pygame.Rect(sep2_x + 86,  bar_y + 6, 68, 46)
    r_tab_pdf      = pygame.Rect(sep2_x + 162, bar_y + 6, 56, 46)
    r_tab_beautify = pygame.Rect(sep2_x + 226, bar_y + 6, 68, 46)
    r_tab_gemini   = pygame.Rect(sep2_x + 302, bar_y + 6, 68, 46)
    globals()["g_r_tab_notes"]    = r_tab_notes
    globals()["g_r_tab_book"]     = r_tab_book
    globals()["g_r_tab_pdf"]      = r_tab_pdf
    globals()["g_r_tab_beautify"] = r_tab_beautify
    globals()["g_r_tab_gemini"]   = r_tab_gemini

    if show_ai_drawer:
        target_bubble_cx = r_tab_gemini.centerx
        active_tab_name = "gemini"
    elif is_beautifying:
        target_bubble_cx = r_tab_beautify.centerx
        active_tab_name = "beautify"
    elif show_split_book:
        target_bubble_cx = r_tab_book.centerx
        active_tab_name = "book"
    elif show_pdf_modal:
        target_bubble_cx = r_tab_pdf.centerx
        active_tab_name = "pdf"
    else:
        target_bubble_cx = r_tab_notes.centerx
        active_tab_name = "notes"

    if anim_bubble_x is None:
        anim_bubble_x = float(target_bubble_cx)
    else:
        anim_bubble_x += (target_bubble_cx - anim_bubble_x) * 0.24

    r_book_prev  = pygame.Rect(12, 10, 34, 34)
    r_book_pill  = pygame.Rect(50, 10, 100, 34)
    r_book_next  = pygame.Rect(154, 10, 34, 34)
    r_book_close = pygame.Rect(book_w - 42, 10, 32, 32) if show_split_book else pygame.Rect(0, 0, 0, 0)

    btn_close_ai = pygame.Rect(sw - 38, 16, 26, 26)

    modal_w, modal_h = 460, 420
    modal_x = (sw - modal_w) // 2
    modal_y = (sh - modal_h) // 2
    modal_rect = pygame.Rect(modal_x, modal_y, modal_w, modal_h)
    btn_close_modal = pygame.Rect(modal_x + modal_w - 42, modal_y + 14, 28, 28)

    u_modal_w = 400
    u_modal_h = min(sh - 100, 80 + len(all_users) * 52 + 56)
    u_modal_x = (sw - u_modal_w) // 2
    u_modal_y = (sh - u_modal_h) // 2
    u_modal_rect = pygame.Rect(u_modal_x, u_modal_y, u_modal_w, u_modal_h)
    btn_close_u_modal = pygame.Rect(u_modal_x + u_modal_w - 42, u_modal_y + 14, 28, 28)

    user_btn_rects = []
    for idx, u in enumerate(all_users):
        user_btn_rects.append((pygame.Rect(u_modal_x + 24, u_modal_y + 68 + idx * 52, u_modal_w - 48, 42), u))
    r_add_user_btn = pygame.Rect(u_modal_x + 24, u_modal_y + 68 + len(all_users) * 52, u_modal_w - 48, 42)

    nu_w, nu_h = 420, 320
    nu_x = (sw - nu_w) // 2
    nu_y = (sh - nu_h) // 2
    nu_rect = pygame.Rect(nu_x, nu_y, nu_w, nu_h)
    btn_close_nu = pygame.Rect(nu_x + nu_w - 42, nu_y + 14, 28, 28)

    r_inp_name  = pygame.Rect(nu_x + 30, nu_y + 90, nu_w - 60, 42)
    r_inp_grade = pygame.Rect(nu_x + 30, nu_y + 168, nu_w - 60, 42)
    r_btn_save_nu = pygame.Rect(nu_x + 30, nu_y + 240, nu_w - 60, 44)

    tb_files = get_textbook_files()
    tb_w, tb_h = 460, min(sh - 100, 90 + max(1, len(tb_files)) * 50)
    tb_x = (sw - tb_w) // 2
    tb_y = (sh - tb_h) // 2
    tb_rect = pygame.Rect(tb_x, tb_y, tb_w, tb_h)
    btn_close_tb = pygame.Rect(tb_x + tb_w - 42, tb_y + 14, 28, 28)

    tb_btn_rects = []
    for idx, f_name in enumerate(tb_files):
        tb_btn_rects.append((pygame.Rect(tb_x + 24, tb_y + 70 + idx * 50, tb_w - 48, 40), f_name))
    globals()["g_btn_close_ai"] = btn_close_ai
    globals()["g_btn_close_tb"] = btn_close_tb
    globals()["g_tb_btn_rects"] = tb_btn_rects
    globals()["g_btn_close_modal"] = btn_close_modal
    globals()["g_btn_close_u_modal"] = btn_close_u_modal
    globals()["g_btn_close_nu"] = btn_close_nu
    globals()["g_r_book_close"] = r_book_close

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            save_current_page()
            close_textbook()
            pygame.quit()
            sys.exit()

        elif event.type == EVENT_BTN_NOTES:
            print("[BTN] Бутон 1: Връщане към активна тетрадка")
            if show_split_book:
                close_textbook()
            if show_ai_drawer:
                show_ai_drawer = False
            active_tool = "pen"
            show_toast("Тетрадка")
        elif event.type == EVENT_BTN_CLASSROOM:
            pass
        elif event.type == EVENT_BTN_BOOK:
            print("[BTN] Учебници")
            if show_split_book:
                close_textbook()
            else:
                tb_list = get_textbook_files()
                if tb_list:
                    open_textbook(tb_list[0])
                else:
                    show_textbook_picker = True

        elif event.type == EVENT_BTN_AI:
            print("[BTN] Gemini AI")
            trigger_gemini_analysis()

        elif event.type == pygame.VIDEORESIZE:
            screen = pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE | pygame.DOUBLEBUF)
            if show_split_book:
                render_book_page()

        elif event.type == pygame.TEXTINPUT:
            if show_new_user_modal:
                if input_focus == "name":
                    if len(input_new_name) < 26:
                        input_new_name += event.text
                elif input_focus == "grade":
                    if len(input_new_grade) < 8:
                        input_new_grade += event.text

        elif event.type == pygame.MOUSEWHEEL:
            if show_ai_drawer and mouse_x >= sw - drawer_width:
                drawer_scroll_y = max(0, min(drawer_max_scroll, drawer_scroll_y - event.y * 36))
            elif show_split_book and mouse_x < book_w:
                if event.y < 0:
                    book_next_page()
                elif event.y > 0:
                    book_prev_page()

        elif event.type == pygame.MOUSEBUTTONDOWN:
            curr_pos = event.pos
            last_pos = curr_pos
            last_canvas_pt = curr_pos

            if event.button == 1:
                if globals().get("show_ai_drawer"):
                    b_c_ai = globals().get("g_btn_close_ai")
                    if b_c_ai and b_c_ai.inflate(14, 14).collidepoint(curr_pos):
                        globals()["show_ai_drawer"] = False
                        is_drawing = False
                        continue
                    if curr_pos[0] >= screen.get_width() - 50 and curr_pos[1] <= 55:
                        globals()["show_ai_drawer"] = False
                        is_drawing = False
                        continue

                if globals().get("show_split_book"):
                    b_c_bk = globals().get("g_r_book_close")
                    if b_c_bk and b_c_bk.inflate(14, 14).collidepoint(curr_pos):
                        if callable(globals().get("close_textbook")):
                            close_textbook()
                        is_drawing = False
                        continue

                if globals().get("show_textbook_picker"):
                    b_c_tb = globals().get("g_btn_close_tb")
                    if b_c_tb and b_c_tb.inflate(14, 14).collidepoint(curr_pos):
                        globals()["show_textbook_picker"] = False
                        is_drawing = False
                        continue
                    for r_file, fname in globals().get("g_tb_btn_rects", []):
                        if r_file.inflate(4, 4).collidepoint(curr_pos):
                            if callable(globals().get("open_textbook")):
                                open_textbook(fname)
                            globals()["show_textbook_picker"] = False
                            break
                    is_drawing = False
                    continue

                if globals().get("show_user_modal"):
                    b_c_u = globals().get("g_btn_close_u_modal")
                    if b_c_u and b_c_u.inflate(14, 14).collidepoint(curr_pos):
                        globals()["show_user_modal"] = False
                        is_drawing = False
                        continue
                    for u_rect, u_obj in globals().get("user_btn_rects", []):
                        if u_rect.collidepoint(curr_pos):
                            switch_user(u_obj)
                            break
                    if globals().get("r_add_user_btn") and globals()["r_add_user_btn"].collidepoint(curr_pos):
                        globals()["show_user_modal"] = False
                        globals()["show_new_user_modal"] = True
                        globals()["input_new_name"] = ""
                        globals()["input_new_grade"] = ""
                        globals()["input_focus"] = "name"
                        pygame.key.start_text_input()
                    is_drawing = False
                    continue

                if globals().get("show_new_user_modal"):
                    b_c_nu = globals().get("g_btn_close_nu")
                    if b_c_nu and b_c_nu.inflate(14, 14).collidepoint(curr_pos):
                        globals()["show_new_user_modal"] = False
                        pygame.key.stop_text_input()
                        is_drawing = False
                        continue
                    if globals().get("r_inp_name") and globals()["r_inp_name"].collidepoint(curr_pos):
                        input_focus = "name"
                        continue
                    if globals().get("r_inp_grade") and globals()["r_inp_grade"].collidepoint(curr_pos):
                        input_focus = "grade"
                        continue
                    if globals().get("r_btn_save_nu") and globals()["r_btn_save_nu"].collidepoint(curr_pos):
                        submit_new_user()
                        pygame.key.stop_text_input()
                        continue
                    is_drawing = False
                    continue

                if globals().get("show_pdf_modal"):
                    b_c_m = globals().get("g_btn_close_modal")
                    if b_c_m and b_c_m.inflate(14, 14).collidepoint(curr_pos):
                        globals()["show_pdf_modal"] = False
                        is_drawing = False
                        continue

            if event.button == 1 and r_user.inflate(6, 6).collidepoint(curr_pos):
                show_user_modal = True
                is_drawing = False
                continue

            color_clicked = False
            if "color_rects" in globals() and event.button == 1:
                for idx, c_rect in enumerate(color_rects):
                    hit_rect = c_rect.inflate(12, 12)
                    if hit_rect.collidepoint(curr_pos):
                        new_col = AVAILABLE_COLORS[idx][1]
                        globals()["current_ink_color"] = new_col
                        globals()["current_color"] = new_col
                        globals()["active_tool"] = "pen"
                        current_ink_color = new_col
                        color_clicked = True
                        break

            if color_clicked:
                is_drawing = False
                continue

            if event.button == 1:
                g_clr = globals().get("g_r_clear")
                if g_clr and g_clr.inflate(12, 12).collidepoint(curr_pos):
                    if callable(globals().get("clear_current_page")):
                        clear_current_page()
                    else:
                        show_toast("Страницата е изчистена")
                    is_drawing = False
                    continue

                g_del = globals().get("g_r_del")
                if g_del and g_del.inflate(12, 12).collidepoint(curr_pos):
                    if callable(globals().get("delete_current_page")):
                        delete_current_page()
                    is_drawing = False
                    continue

                g_prv = globals().get("g_r_prev")
                if g_prv and g_prv.inflate(12, 12).collidepoint(curr_pos):
                    if callable(globals().get("prev_page")):
                        prev_page()
                    is_drawing = False
                    continue

                g_nxt = globals().get("g_r_next")
                if g_nxt and g_nxt.inflate(12, 12).collidepoint(curr_pos):
                    if callable(globals().get("next_page")):
                        next_page()
                    is_drawing = False
                    continue

                g_ad = globals().get("g_r_add")
                if g_ad and g_ad.inflate(12, 12).collidepoint(curr_pos):
                    if callable(globals().get("add_blank_page")):
                        add_blank_page()
                    is_drawing = False
                    continue

                # Таб Тетрадка
                g_t_notes = globals().get("g_r_tab_notes")
                if g_t_notes and g_t_notes.inflate(10, 10).collidepoint(curr_pos):
                    if callable(globals().get("close_textbook")):
                        close_textbook()
                    globals()["show_ai_drawer"] = False
                    globals()["active_tool"] = "pen"
                    if callable(globals().get("show_toast")):
                        show_toast("Тетрадка")
                    is_drawing = False
                    continue

                # Таб Учебник
                g_t_book = globals().get("g_r_tab_book")
                if g_t_book and g_t_book.inflate(10, 10).collidepoint(curr_pos):
                    if globals().get("show_split_book"):
                        if callable(globals().get("close_textbook")):
                            close_textbook()
                    else:
                        tb_list = get_textbook_files() if callable(globals().get("get_textbook_files")) else []
                        if tb_list and callable(globals().get("open_textbook")):
                            open_textbook(tb_list[0])
                        else:
                            globals()["show_textbook_picker"] = True
                    is_drawing = False
                    continue

                # Таб PDF
                g_t_pdf = globals().get("g_r_tab_pdf")
                if g_t_pdf and g_t_pdf.inflate(10, 10).collidepoint(curr_pos):
                    if callable(globals().get("export_all_to_pdf_and_show_qr")):
                        export_all_to_pdf_and_show_qr()
                    is_drawing = False
                    continue

                # Таб Оформи
                g_t_beau = globals().get("g_r_tab_beautify")
                if g_t_beau and g_t_beau.inflate(10, 10).collidepoint(curr_pos):
                    if callable(globals().get("trigger_beautify_to_new_page")):
                        trigger_beautify_to_new_page()
                    is_drawing = False
                    continue

                # Таб Gemini
                g_t_gem = globals().get("g_r_tab_gemini")
                if g_t_gem and g_t_gem.inflate(10, 10).collidepoint(curr_pos):
                    if callable(globals().get("trigger_gemini_analysis")):
                        trigger_gemini_analysis()
                    is_drawing = False
                    continue

            if event.button == 1:
                current_action = globals().get("active_tool", "pen")
                is_drawing = True
            elif event.button == 3:
                current_action = "eraser"
                is_drawing = True
            elif event.button == 2:
                current_action = "pan"
                is_drawing = True

        elif event.type == pygame.MOUSEMOTION:
            current_cursor_pos = event.pos
            curr_pos = event.pos
            mouse_x, mouse_y = curr_pos

            b_left, b_mid, b_right = pygame.mouse.get_pressed()

            if b_mid or current_action == "pan":
                if last_pos is not None:
                    dx = curr_pos[0] - last_pos[0]
                    dy = curr_pos[1] - last_pos[1]
                    max_off_x = max(0, CANVAS_W - max(100, screen.get_width() - globals().get("book_w", 0)))
                    max_off_y = max(0, CANVAS_H - screen.get_height())
                    offset_x = max(0, min(max_off_x, offset_x - dx))
                    offset_y = max(0, min(max_off_y, offset_y - dy))
                last_pos = curr_pos

            elif (b_left or b_right or is_drawing) and not b_mid and not globals().get('is_holding_pan', False) and current_action != 'pan' and last_pos is not None:
                p1 = (last_pos[0] - book_w + offset_x, last_pos[1] + offset_y)
                p2 = (curr_pos[0] - book_w + offset_x, curr_pos[1] + offset_y)

                target_canvas = getattr(globals().get("page"), "canvas", None)
                if target_canvas is not None:
                    if b_right or current_action == "eraser":
                        w = 32
                        pygame.draw.line(target_canvas, (0, 0, 0, 0), p1, p2, w)
                        pygame.draw.circle(target_canvas, (0, 0, 0, 0), p2, w // 2)
                    elif b_left or current_action == "pen":
                        c = globals().get("current_ink_color") or globals().get("current_color") or (20, 20, 20)
                        w = 3
                        pygame.draw.line(target_canvas, c, p1, p2, w)
                        pygame.draw.circle(target_canvas, c, p2, max(1, w // 2))
                        p_obj = globals().get("page")
                        if p_obj is not None:
                            p_obj.track_point(p1[0], p1[1])
                            p_obj.track_point(p2[0], p2[1])

                last_pos = curr_pos
            else:
                last_pos = curr_pos

        elif event.type == pygame.MOUSEBUTTONUP:
            drawer_is_dragging = False
            if globals().get("is_drawing", False):
                if current_action in ("pen", "eraser"):
                    if "push_undo" in globals():
                        try:
                            push_undo()
                        except Exception:
                            pass
            is_drawing = False
            current_action = None
            last_pos = None
            last_canvas_pt = None

        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_e:
                active_tool = "eraser" if globals().get("active_tool") != "eraser" else "pen"
            elif event.key == pygame.K_z:
                if "push_undo" in globals() or "undo" in globals():
                    try:
                        undo()
                    except Exception:
                        pass
            if show_new_user_modal:
                if event.key == pygame.K_BACKSPACE:
                    if input_focus == "name":
                        input_new_name = input_new_name[:-1]
                    elif input_focus == "grade":
                        input_new_grade = input_new_grade[:-1]
                elif event.key == pygame.K_TAB:
                    input_focus = "grade" if input_focus == "name" else "name"
                elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    submit_new_user()
                    pygame.key.stop_text_input()
                elif event.key == pygame.K_ESCAPE:
                    show_new_user_modal = False
                    pygame.key.stop_text_input()
                continue

            if event.key == pygame.K_LEFT:
                if show_split_book and pygame.key.get_mods() & pygame.KMOD_SHIFT:
                    book_prev_page()
                else:
                    prev_page()
            elif event.key == pygame.K_RIGHT:
                if show_split_book and pygame.key.get_mods() & pygame.KMOD_SHIFT:
                    book_next_page()
                else:
                    next_page()
            elif event.key == pygame.K_z: undo()
            elif event.key == pygame.K_g: trigger_gemini_analysis()
            elif event.key == pygame.K_n: trigger_beautify_to_new_page()
            elif event.key == pygame.K_b:
                if show_split_book: close_textbook()
                else: show_textbook_picker = True
            elif event.key == pygame.K_u: show_user_modal = True
            elif event.key == pygame.K_ESCAPE:
                if show_textbook_picker: show_textbook_picker = False
                elif show_new_user_modal: show_new_user_modal = False
                elif show_user_modal: show_user_modal = False
                elif show_pdf_modal: show_pdf_modal = False
                elif show_ai_drawer: show_ai_drawer = False
                elif show_split_book: close_textbook()
                else:
                    save_current_page()
                    close_textbook()
                    pygame.quit()
                    sys.exit()

    # ----------------- РЕНДЕРИРАНЕ -----------------
    visible_rect = pygame.Rect(offset_x, offset_y, canvas_rect.w, sh)
    screen.blit(PAGE_BACKGROUND, (book_w, 0), area=visible_rect)
    screen.blit(page.canvas, (book_w, 0), area=visible_rect)

    # Учебник (Split Screen)
    if show_split_book:
        b_panel_rect = pygame.Rect(0, 0, book_w, sh)
        pygame.draw.rect(screen, (241, 245, 249), b_panel_rect)
        pygame.draw.line(screen, (226, 232, 240), (book_w, 0), (book_w, sh), 2)

        head_book_r = pygame.Rect(0, 0, book_w, 54)
        pygame.draw.rect(screen, (255, 255, 255), head_book_r)
        pygame.draw.line(screen, (226, 232, 240), (0, 54), (book_w, 54), 1)

        for btn_r, symb in [(r_book_prev, "<"), (r_book_next, ">"), (r_book_close, "✕")]:
            bh = btn_r.collidepoint((mouse_x, mouse_y))
            pygame.draw.rect(screen, (241, 245, 249) if bh else (255, 255, 255), btn_r, border_radius=8)
            s_ts = font_btn.render(symb, True, (15, 23, 42))
            screen.blit(s_ts, (btn_r.centerx - s_ts.get_width() // 2, btn_r.centery - s_ts.get_height() // 2))

        pygame.draw.rect(screen, (248, 250, 252), r_book_pill, border_radius=8)
        tot_pages = len(current_book_doc) if current_book_doc else 1
        bp_txt = font_pill.render(f"Стр. {book_page_idx + 1}/{tot_pages}", True, (15, 23, 42))
        screen.blit(bp_txt, (r_book_pill.centerx - bp_txt.get_width() // 2, r_book_pill.centery - bp_txt.get_height() // 2))

        trunc_name = current_book_filename
        if len(trunc_name) > 18:
            trunc_name = trunc_name[:16] + "..."
        t_title = font_pill.render(trunc_name, True, (100, 116, 139))
        screen.blit(t_title, (194, 20))

        if book_page_surf:
            page_pos_x = 12 + (book_w - 24 - book_page_surf.get_width()) // 2
            page_pos_y = 66 + (sh - 76 - book_page_surf.get_height()) // 2
            pygame.draw.rect(screen, (203, 213, 225), pygame.Rect(page_pos_x, page_pos_y, book_page_surf.get_width(), book_page_surf.get_height()).inflate(6, 6), border_radius=4)
            screen.blit(book_page_surf, (page_pos_x, page_pos_y))

    # ----------------- DOCK -----------------
    bx = int(anim_bubble_x)
    local_notch_x = bx - bar_x
    pad = 12

    dock_surf = render_smooth_dock_curve(bar_w, bar_h, local_notch_x, pad=pad, notch_w=76, notch_d=24, radius=24)
    screen.blit(dock_surf, (bar_x - pad, bar_y - pad))

    bubble_cy = bar_y - 7
    bubble_surf = get_crisp_bubble(size=48)
    screen.blit(bubble_surf, (bx - bubble_surf.get_width() // 2, bubble_cy - bubble_surf.get_height() // 2 + 1))

    active_icon = get_crisp_icon(active_tab_name, (255, 255, 255, 255), size=20)
    screen.blit(active_icon, (bx - active_icon.get_width() // 2, bubble_cy - active_icon.get_height() // 2 - 1))

    u_h = r_user.collidepoint((mouse_x, mouse_y))
    u_col_rgba = (245, 245, 250, 255) if u_h else (140, 144, 156, 255)
    u_icon_surf = get_crisp_icon("user", u_col_rgba, size=18)
    screen.blit(u_icon_surf, (r_user.x + 3, r_user.centery - u_icon_surf.get_height() // 2))

    global _cached_user_id, _cached_name_surf, _cached_sub_surf
    try:
        _cached_user_id
    except NameError:
        _cached_user_id = None
        _cached_name_surf = None
        _cached_sub_surf = None

    _cur_id = current_user.get('id') or current_user.get('name')
    if _cached_user_id != _cur_id or _cached_name_surf is None:
        _raw_name = str(current_user.get('name', 'Ученик')).strip()
        _parts = _raw_name.split()
        if len(_parts) >= 2:
            _d_name = f"{_parts[0]} {_parts[1][0]}."
        else:
            _d_name = _raw_name

        if font_btn.size(_d_name)[0] > 70:
            while len(_d_name) > 3 and font_btn.size(_d_name + "..")[0] > 70:
                _d_name = _d_name[:-1]
            _d_name += ".."

        _cached_name_surf = font_btn.render(_d_name, True, (245, 245, 250))
        _cached_sub_surf = font_btn.render(current_user.get('grade', ''), True, (120, 125, 138))
        _cached_user_id = _cur_id

    u_name_s = _cached_name_surf
    u_sub_s  = font_btn.render(current_user.get('grade', ''), True, (120, 125, 138))
    screen.blit(u_name_s, (r_user.x + 25, r_user.y + 6))
    screen.blit(u_sub_s,  (r_user.x + 25, r_user.y + 22))

    pygame.draw.line(screen, C_NAV_BORDER, (bar_x + 112, bar_y + 14), (bar_x + 112, bar_y + bar_h - 14), 1)

    for idx, c_rect in enumerate(color_rects):
        col = AVAILABLE_COLORS[idx][1]
        is_sel = (current_ink_color == col and effective_tool == "pen")
        center_x = c_rect.centerx
        center_y = c_rect.centery
        if is_sel:
            pygame.gfxdraw.filled_circle(screen, center_x, center_y, 8, (255, 255, 255))
            pygame.gfxdraw.filled_circle(screen, center_x, center_y, 6, col[:3])
            pygame.gfxdraw.aacircle(screen, center_x, center_y, 8, (255, 255, 255))
        else:
            pygame.gfxdraw.filled_circle(screen, center_x, center_y, 5, col[:3])
            pygame.gfxdraw.aacircle(screen, center_x, center_y, 5, col[:3])

    cl_h = r_clear.collidepoint((mouse_x, mouse_y))
    cl_col = (245, 245, 250, 255) if cl_h else (140, 144, 156, 255)
    trash_icon = get_crisp_icon("trash", cl_col, size=18)
    screen.blit(trash_icon, (r_clear.centerx - trash_icon.get_width() // 2, r_clear.centery - trash_icon.get_height() // 2))

    pygame.draw.line(screen, C_NAV_BORDER, (sep1_x, bar_y + 14), (sep1_x, bar_y + bar_h - 14), 1)

    for br, txt in [(r_del, "-"), (r_prev, "‹"), (r_next, "›"), (r_add, "+")]:
        bh = br.collidepoint((mouse_x, mouse_y))
        ts = font_head.render(txt, True, C_TEXT_LIGHT if bh else C_ICON_MUTED)
        screen.blit(ts, (br.centerx - ts.get_width() // 2, br.centery - ts.get_height() // 2))

    pygame.draw.rect(screen, (34, 34, 40), r_pill, border_radius=8)
    p_num_txt = font_pill.render(f"{curr_idx + 1} / {len(pages)}", True, (240, 240, 245))
    screen.blit(p_num_txt, (r_pill.centerx - p_num_txt.get_width() // 2, r_pill.centery - p_num_txt.get_height() // 2))

    pygame.draw.line(screen, C_NAV_BORDER, (sep2_x, bar_y + 14), (sep2_x, bar_y + bar_h - 14), 1)

    tabs_data = [
        (r_tab_notes, "notes", "Тетрадка"),
        (r_tab_book, "book", "Учебник"),
        (r_tab_pdf, "pdf", "PDF"),
        (r_tab_beautify, "beautify", "Оформи"),
        (r_tab_gemini, "gemini", "Gemini")
    ]

    for rect, t_name, label_str in tabs_data:
        is_active = (active_tab_name == t_name)
        th = rect.collidepoint((mouse_x, mouse_y))
        col_rgba = (245, 245, 250, 255) if th else (140, 144, 156, 255)

        if not is_active:
            ico_surf = get_crisp_icon(t_name, col_rgba, size=18)
            screen.blit(ico_surf, (rect.centerx - ico_surf.get_width() // 2, bar_y + 15))

        lbl_col = C_TEXT_LIGHT if is_active else C_ICON_MUTED
        lbl_s = font_btn.render(label_str, True, lbl_col)
        screen.blit(lbl_s, (rect.centerx - lbl_s.get_width() // 2, bar_rect.bottom - 24))

    # Toast нотификация
    if time.time() < toast_time:
        t_surf = font_pill.render(toast_msg, True, (255, 255, 255))
        tw = t_surf.get_width() + 32
        tr = pygame.Rect(sw // 2 - tw // 2, bar_y + bar_h + 12, tw, 32)
        pygame.draw.rect(screen, (15, 23, 42), tr, border_radius=16)
        screen.blit(t_surf, (tr.centerx - t_surf.get_width() // 2, tr.centery - t_surf.get_height() // 2 - 3))
    elif is_beautifying:
        b_w, b_h = 300, 32
        b_rect = pygame.Rect(sw // 2 - b_w // 2, bar_y + bar_h + 12, b_w, b_h)
        pygame.draw.rect(screen, (15, 23, 42), b_rect, border_radius=16)
        c_txt = font_pill.render("✨ Оформяне и надграждане...", True, (255, 255, 255))
        screen.blit(c_txt, (b_rect.centerx - c_txt.get_width() // 2, b_rect.centery - c_txt.get_height() // 2))

    # ----------------- GEMINI DRAWER -----------------
    if show_ai_drawer:
        dx_start = sw - drawer_width
        drawer_rect = pygame.Rect(dx_start, 0, drawer_width, sh)

        pygame.draw.rect(screen, (255, 255, 255), drawer_rect)
        pygame.draw.line(screen, (226, 232, 240), (dx_start, 0), (dx_start, sh), 1)

        head_rect = pygame.Rect(dx_start, 0, drawer_width, 60)
        pygame.draw.rect(screen, (248, 250, 252), head_rect)
        pygame.draw.line(screen, (226, 232, 240), (dx_start, 60), (sw, 60), 1)

        title_surf = font_head.render("Gemini Асистент", True, (15, 23, 42))
        screen.blit(title_surf, (dx_start + 20, 20))

        c_hover = btn_close_ai.collidepoint((mouse_x, mouse_y))
        pygame.draw.rect(screen, (241, 245, 249) if c_hover else (248, 250, 252), btn_close_ai, border_radius=6)
        c_sym = font_btn.render("✕", True, (15, 23, 42) if c_hover else (100, 116, 139))
        screen.blit(c_sym, (btn_close_ai.centerx - c_sym.get_width() // 2, btn_close_ai.centery - c_sym.get_height() // 2))

        content_area_h = sh - 70
        max_content_w = drawer_width - 40
        clip_rect = pygame.Rect(dx_start, 60, drawer_width, content_area_h)
        old_clip = screen.get_clip()
        screen.set_clip(clip_rect)

        cur_draw_y = 75 - drawer_scroll_y

        if is_analyzing:
            pulsing_dot_y = cur_draw_y + 30
            for i in range(3):
                dy_off = math.sin(anim_t * 6 + i * 0.9) * 5
                pygame.draw.circle(screen, C_BLUE_ACCENT, (dx_start + 40 + i * 22, int(pulsing_dot_y + dy_off)), 5)
            s_txt = font_ai_h.render("Gemini анализира страницата...", True, C_BLUE_ACCENT)
            screen.blit(s_txt, (dx_start + 120, pulsing_dot_y - 8))
            total_content_h = 100
        else:
            raw_lines = ai_analysis_text.split("\n")
            for line in raw_lines:
                sline = line.strip()
                if not sline:
                    cur_draw_y += 10
                    continue

                if sline.startswith("## "):
                    h_text = sline.replace("## ", "").strip()
                    hs = font_ai_h.render(h_text, True, (29, 78, 216))
                    screen.blit(hs, (dx_start + 20, cur_draw_y))
                    cur_draw_y += 28
                    pygame.draw.line(screen, (226, 232, 240), (dx_start + 20, cur_draw_y - 4), (sw - 20, cur_draw_y - 4), 1)
                elif sline.startswith("•") or sline.startswith("- "):
                    b_text = sline.lstrip("•- ").strip()
                    wrapped = wrap_text(b_text, font_ai_body, max_content_w - 24)
                    pygame.draw.circle(screen, C_BLUE_ACCENT, (dx_start + 26, cur_draw_y + 9), 3)
                    for idx, wl in enumerate(wrapped):
                        ts = font_ai_body.render(wl, True, (15, 23, 42))
                        screen.blit(ts, (dx_start + 38, cur_draw_y))
                        cur_draw_y += 22
                else:
                    wrapped = wrap_text(sline, font_ai_body, max_content_w)
                    for wl in wrapped:
                        ts = font_ai_body.render(wl, True, (15, 23, 42))
                        screen.blit(ts, (dx_start + 20, cur_draw_y))
                        cur_draw_y += 22

            total_content_h = (cur_draw_y + drawer_scroll_y) - 60

        screen.set_clip(old_clip)

        drawer_max_scroll = max(0, total_content_h - content_area_h)
        if drawer_max_scroll > 0:
            sb_h = max(30, int(content_area_h * (content_area_h / max(1, total_content_h))))
            sb_y = 65 + int((drawer_scroll_y / max(1, drawer_max_scroll)) * (content_area_h - sb_h))
            pygame.draw.rect(screen, (203, 213, 225), (sw - 5, sb_y, 3, sb_h), border_radius=2)

    # ----------------- MODAL: UCHEBNIK -----------------
    if show_textbook_picker:
        screen.blit(STATIC_OVERLAY, (0, 0))

        card_surf, pad = get_crisp_modal_card(tb_rect.w, tb_rect.h, radius=20)
        screen.blit(card_surf, (tb_rect.x - pad, tb_rect.y - pad))

        tbm_title = font_head.render("Избери учебник", True, (15, 23, 42))
        screen.blit(tbm_title, (tb_x + 24, tb_y + 20))

        cl_hover = btn_close_tb.collidepoint((mouse_x, mouse_y))
        pygame.draw.rect(screen, (241, 245, 249) if cl_hover else (255, 255, 255), btn_close_tb, border_radius=6)
        cl_txt = font_btn.render("✕", True, (15, 23, 42) if cl_hover else (100, 116, 139))
        screen.blit(cl_txt, (btn_close_tb.centerx - cl_txt.get_width() // 2, btn_close_tb.centery - cl_txt.get_height() // 2))

        if not tb_files:
            empty_t = font_pill.render("Няма открити PDF файлове в ~/textbooks/", True, (100, 116, 139))
            screen.blit(empty_t, (tb_x + 30, tb_y + 80))
        else:
            for b_rect, b_fname in tb_btn_rects:
                bh = b_rect.collidepoint((mouse_x, mouse_y))
                pygame.draw.rect(screen, (241, 245, 249) if bh else (248, 250, 252), b_rect, border_radius=8)
                pygame.draw.rect(screen, (226, 232, 240), b_rect, 1, border_radius=8)

                disp_fname = b_fname if len(b_fname) < 36 else b_fname[:34] + "..."
                b_ico = get_crisp_icon("book", (37, 99, 235, 255) if bh else (15, 23, 42, 255), size=18)
                screen.blit(b_ico, (b_rect.x + 14, b_rect.centery - b_ico.get_height() // 2))
                f_ts = font_modal.render(disp_fname, True, C_BLUE_ACCENT if bh else (15, 23, 42))
                screen.blit(f_ts, (b_rect.x + 40, b_rect.centery - f_ts.get_height() // 2))

    # ----------------- MODAL: PROFILI -----------------
    if show_user_modal:
        screen.blit(STATIC_OVERLAY, (0, 0))

        card_surf, pad = get_crisp_modal_card(u_modal_rect.w, u_modal_rect.h, radius=20)
        screen.blit(card_surf, (u_modal_rect.x - pad, u_modal_rect.y - pad))

        um_title = font_head.render("Избери профил", True, (15, 23, 42))
        screen.blit(um_title, (u_modal_x + 24, u_modal_y + 20))

        cl_hover = btn_close_u_modal.collidepoint((mouse_x, mouse_y))
        pygame.draw.rect(screen, (241, 245, 249) if cl_hover else (255, 255, 255), btn_close_u_modal, border_radius=6)
        cl_txt = font_btn.render("✕", True, (15, 23, 42) if cl_hover else (100, 116, 139))
        screen.blit(cl_txt, (btn_close_u_modal.centerx - cl_txt.get_width() // 2, btn_close_u_modal.centery - cl_txt.get_height() // 2))

        for u_rect, u_obj in user_btn_rects:
            is_active_u = (u_obj["id"] == current_user["id"])
            u_hover = u_rect.collidepoint((mouse_x, mouse_y))
            if is_active_u:
                btn_bg = C_BLUE_ACCENT
                t_col = (255, 255, 255)
            elif u_hover:
                btn_bg = (241, 245, 249)
                t_col = C_BLUE_ACCENT
            else:
                btn_bg = (248, 250, 252)
                t_col = (15, 23, 42)

            pygame.draw.rect(screen, btn_bg, u_rect, border_radius=10)
            pygame.draw.rect(screen, (226, 232, 240), u_rect, 1, border_radius=10)

            prefix = "✓ " if is_active_u else ""
            u_display_text = f"{prefix}{u_obj['name']} • {u_obj.get('grade', '')} клас"
            u_ts = font_modal.render(u_display_text, True, t_col)
            screen.blit(u_ts, (u_rect.centerx - u_ts.get_width() // 2, u_rect.centery - u_ts.get_height() // 2))

        add_u_hover = r_add_user_btn.collidepoint((mouse_x, mouse_y))
        pygame.draw.rect(screen, (241, 245, 249) if add_u_hover else (255, 255, 255), r_add_user_btn, border_radius=10)
        pygame.draw.rect(screen, C_BLUE_ACCENT, r_add_user_btn, 1, border_radius=10)
        add_u_ts = font_modal.render("+ Добави нов ученик", True, C_BLUE_ACCENT)
        screen.blit(add_u_ts, (r_add_user_btn.centerx - add_u_ts.get_width() // 2, r_add_user_btn.centery - add_u_ts.get_height() // 2))

    # ----------------- MODAL: NOV UCHENIK -----------------
    if show_new_user_modal:
        screen.blit(STATIC_OVERLAY, (0, 0))

        card_surf, pad = get_crisp_modal_card(nu_rect.w, nu_rect.h, radius=20)
        screen.blit(card_surf, (nu_rect.x - pad, nu_rect.y - pad))

        nu_title = font_head.render("Нов ученик", True, (15, 23, 42))
        screen.blit(nu_title, (nu_x + 24, nu_y + 20))

        cl_hover = btn_close_nu.collidepoint((mouse_x, mouse_y))
        pygame.draw.rect(screen, (241, 245, 249) if cl_hover else (255, 255, 255), btn_close_nu, border_radius=6)
        cl_txt = font_btn.render("✕", True, (15, 23, 42) if cl_hover else (100, 116, 139))
        screen.blit(cl_txt, (btn_close_nu.centerx - cl_txt.get_width() // 2, btn_close_nu.centery - cl_txt.get_height() // 2))

        lbl_name = font_pill.render("Име на ученика:", True, (100, 116, 139))
        screen.blit(lbl_name, (nu_x + 32, nu_y + 68))

        is_focused_name = (input_focus == "name")
        pygame.draw.rect(screen, (255, 255, 255), r_inp_name, border_radius=8)
        pygame.draw.rect(screen, C_BLUE_ACCENT if is_focused_name else (226, 232, 240), r_inp_name, 2 if is_focused_name else 1, border_radius=8)

        cursor_name = " |" if (is_focused_name and int(anim_t * 2) % 2 == 0) else ""
        txt_name_s = font_input.render((input_new_name or "") + cursor_name, True, (15, 23, 42) if input_new_name else (100, 116, 139))
        screen.blit(txt_name_s, (r_inp_name.x + 12, r_inp_name.centery - txt_name_s.get_height() // 2))

        lbl_grade = font_pill.render("Клас (напр. 10А, 9В):", True, (100, 116, 139))
        screen.blit(lbl_grade, (nu_x + 32, nu_y + 146))

        is_focused_grade = (input_focus == "grade")
        pygame.draw.rect(screen, (255, 255, 255), r_inp_grade, border_radius=8)
        pygame.draw.rect(screen, C_BLUE_ACCENT if is_focused_grade else (226, 232, 240), r_inp_grade, 2 if is_focused_grade else 1, border_radius=8)

        cursor_grade = " |" if (is_focused_grade and int(anim_t * 2) % 2 == 0) else ""
        txt_grade_s = font_input.render((input_new_grade or "") + cursor_grade, True, (15, 23, 42) if input_new_grade else (100, 116, 139))
        screen.blit(txt_grade_s, (r_inp_grade.x + 12, r_inp_grade.centery - txt_grade_s.get_height() // 2))

        save_hover = r_btn_save_nu.collidepoint((mouse_x, mouse_y))
        pygame.draw.rect(screen, (29, 78, 216) if save_hover else C_BLUE_ACCENT, r_btn_save_nu, border_radius=10)
        s_txt = font_modal.render("✓ Запази профила", True, (255, 255, 255))
        screen.blit(s_txt, (r_btn_save_nu.centerx - s_txt.get_width() // 2, r_btn_save_nu.centery - s_txt.get_height() // 2))

    # ----------------- MODAL: PDF & QR -----------------
    if show_pdf_modal:
        screen.blit(STATIC_OVERLAY, (0, 0))

        card_surf, pad = get_crisp_modal_card(modal_rect.w, modal_rect.h, radius=20)
        screen.blit(card_surf, (modal_rect.x - pad, modal_rect.y - pad))

        m_title = font_head.render("Свали като PDF", True, (15, 23, 42))
        screen.blit(m_title, (modal_x + 24, modal_y + 20))

        cl_hover = btn_close_modal.collidepoint((mouse_x, mouse_y))
        pygame.draw.rect(screen, (241, 245, 249) if cl_hover else (255, 255, 255), btn_close_modal, border_radius=6)
        cl_txt = font_btn.render("✕", True, (15, 23, 42) if cl_hover else (100, 116, 139))
        screen.blit(cl_txt, (btn_close_modal.centerx - cl_txt.get_width() // 2, btn_close_modal.centery - cl_txt.get_height() // 2))

        pygame.draw.line(screen, (226, 232, 240), (modal_x + 24, modal_y + 58), (modal_x + modal_w - 24, modal_y + 58), 1)

        if pdf_qr_surf:
            qr_rect = pdf_qr_surf.get_rect(center=(modal_rect.centerx, modal_y + 175))
            card_box = qr_rect.inflate(16, 16)
            pygame.draw.rect(screen, (248, 250, 252), card_box, border_radius=12)
            pygame.draw.rect(screen, (226, 232, 240), card_box, 1, border_radius=12)
            screen.blit(pdf_qr_surf, qr_rect)
        else:
            no_qr_txt = font_modal.render("Генериране на QR код...", True, (100, 116, 139))
            screen.blit(no_qr_txt, (modal_rect.centerx - no_qr_txt.get_width() // 2, modal_y + 160))

        info1 = font_pill.render("Сканирайте с телефон в същата мрежа:", True, (100, 116, 139))
        screen.blit(info1, (modal_rect.centerx - info1.get_width() // 2, modal_y + 305))

        link_bg_r = pygame.Rect(modal_x + 24, modal_y + 335, modal_w - 48, 38)
        pygame.draw.rect(screen, (248, 250, 252), link_bg_r, border_radius=8)
        pygame.draw.rect(screen, (226, 232, 240), link_bg_r, 1, border_radius=8)

        link_s = font_modal.render(pdf_download_url, True, C_BLUE_ACCENT)
        screen.blit(link_s, (link_bg_r.centerx - link_s.get_width() // 2, link_bg_r.centery - link_s.get_height() // 2))

    # ----------------- КУРСОР -----------------
    bubble_hit_r = pygame.Rect(int(anim_bubble_x) - 24, bar_y - 24, 48, 48)
    is_over_ui = (bar_rect.collidepoint((mouse_x, mouse_y)) or
                  bubble_hit_r.collidepoint((mouse_x, mouse_y)) or
                  (show_ai_drawer and mouse_x >= sw - drawer_width) or
                  (show_split_book and mouse_x < book_w) or
                  show_pdf_modal or show_user_modal or show_new_user_modal or show_textbook_picker)

    cx, cy = current_cursor_pos if ("current_cursor_pos" in globals() and current_cursor_pos) else (mouse_x, mouse_y)

    if is_over_ui:
        pygame.draw.circle(screen, (255, 255, 255), (cx, cy), 5)
        pygame.draw.circle(screen, C_BLUE_ACCENT, (cx, cy), 4)
        pygame.draw.circle(screen, (15, 23, 42), (cx, cy), 5, 1)
    else:
        if effective_tool == "eraser":
            eraser_r = 16
            pygame.draw.circle(screen, (255, 255, 255), (cx, cy), eraser_r + 1, 1)
            pygame.draw.circle(screen, (60, 60, 60), (cx, cy), eraser_r, 2)
            pygame.draw.circle(screen, (220, 38, 38), (cx, cy), 2)
        elif effective_tool == "pan":
            pygame.draw.circle(screen, C_BLUE_ACCENT, (cx, cy), 8, 2)
            pygame.draw.circle(screen, (255, 255, 255), (cx, cy), 2)
        else:
            pygame.draw.circle(screen, current_ink_color, (cx, cy), 3)
            pygame.draw.circle(screen, (255, 255, 255), (cx, cy), 4, 1)

    pygame.display.flip()
    clock.tick(120)
