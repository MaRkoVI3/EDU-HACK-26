import os
import sys
import io
import json
import threading
import pygame
from PIL import Image

# Inizializacia na Gemini SDK pri nalichen kliuch
try:
    from google import genai
    gemini_client = genai.Client()
except Exception:
    gemini_client = None

pygame.init()

# ----------------- DINAMICHNA REZOLUCIQ -----------------
display_info = pygame.display.Info()
screen_w, screen_h = display_info.current_w, display_info.current_h
screen = pygame.display.set_mode((screen_w, screen_h), pygame.RESIZABLE | pygame.DOUBLEBUF)
pygame.display.set_caption("Smart Notebook")

# ----------------- CVETOVE & STIL -----------------
C_PAPER = (253, 253, 254)
C_LINE = (226, 232, 240)
C_INK = (18, 18, 22)
C_TOOLBAR_BG = (245, 247, 250)
C_TOOLBAR_BORDER = (215, 220, 228)
C_DRAWER_BG = (248, 250, 252, 245)
C_TEXT = (25, 28, 35)
C_MUTED = (110, 115, 128)
C_ACCENT = (40, 110, 240)
C_BTN_BG = (235, 238, 243)
C_BTN_HOVER = (220, 225, 235)
C_BTN_ACTIVE = (40, 110, 240)
C_BTN_ACTIVE_TXT = (255, 255, 255)
C_OVERLAY_BG = (20, 20, 25, 200)

TOOLBAR_H = 46
LINE_SPACING = 38
CANVAS_W, CANVAS_H = 3840, 2400

font_ui = pygame.font.SysFont("DejaVu Sans", 13, bold=True)
font_main = pygame.font.SysFont("DejaVu Sans", 15)
font_modal = pygame.font.SysFont("DejaVu Sans", 16)

# ----------------- KEYBINDS (NASTROIKI NA KLAVISHITE) -----------------
CONFIG_FILE = "keybinds.json"
DEFAULT_BINDS = {
    "undo": pygame.K_z,
    "prev_page": pygame.K_LEFT,
    "next_page": pygame.K_RIGHT,
    "gemini": pygame.K_g,
    "hold_eraser": pygame.K_e,
    "hold_pan": pygame.K_h
}

BIND_LABELS = {
    "undo": "Отмяна (Undo)",
    "prev_page": "Предишна страница",
    "next_page": "Следваща страница",
    "gemini": "Gemini AI",
    "hold_eraser": "Гумичка (Задържане)",
    "hold_pan": "Местене (Задържане)"
}

def load_keybinds():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)
                return {k: int(v) for k, v in data.items()}
        except Exception:
            return DEFAULT_BINDS.copy()
    return DEFAULT_BINDS.copy()

def save_keybinds(binds):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(binds, f, indent=4)
    except Exception as e:
        print(f"Грешка при запис на клавишите: {e}")

KEY_BINDS = load_keybinds()
waiting_for_key = None
show_settings_modal = False

# ----------------- FON S REDOVE -----------------
def generate_background():
    bg = pygame.Surface((CANVAS_W, CANVAS_H), depth=24)
    bg.fill(C_PAPER)
    for y in range(LINE_SPACING, CANVAS_H, LINE_SPACING):
        pygame.draw.line(bg, C_LINE, (0, y), (CANVAS_W, y), 1)
    return bg

PAGE_BACKGROUND = generate_background()

class Page:
    __slots__ = ['canvas', 'history', 'ai_lines', 'is_loading', 'ink_bounds']
    def __init__(self):
        self.canvas = pygame.Surface((CANVAS_W, CANVAS_H), pygame.SRCALPHA)
        self.history = [self.canvas.copy()]
        self.ai_lines = ["Натиснете [AI] бутона за анализ на бележките."]
        self.is_loading = False
        self.ink_bounds = [CANVAS_W, CANVAS_H, 0, 0]

    def track_point(self, x, y):
        if x < self.ink_bounds[0]: self.ink_bounds[0] = max(0, x - 25)
        if y < self.ink_bounds[1]: self.ink_bounds[1] = max(0, y - 25)
        if x > self.ink_bounds[2]: self.ink_bounds[2] = min(CANVAS_W, x + 25)
        if y > self.ink_bounds[3]: self.ink_bounds[3] = min(CANVAS_H, y + 25)

pages = [Page()]
curr_idx = 0

# Kamera i sustoqniq
offset_x, offset_y = 0, 0
active_tool = "pen"        # Osnoven instrument: vinagi "pen" po podrazbirane
key_override_tool = None   # Vremenen instrument dokato se zadurzhi klavish (naprimer E ili H)
is_holding_mouse = False
current_action = None
last_pos = None
pan_start = (0, 0)
pan_offset_start = (0, 0)

show_ai_drawer = False
drawer_width = 440

def get_effective_tool():
    """Vrushta vremenno zadurzhaniq instrument ili tekushto izbraniq"""
    if key_override_tool:
        return key_override_tool
    return active_tool

# ----------------- RISUVANE I GUMICHKA -----------------
def draw_ink(surf, p1, p2, radius=2):
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    dist = int((dx*dx + dy*dy) ** 0.5)
    if dist == 0:
        pygame.draw.circle(surf, C_INK, p1, radius)
        return
    step = max(1, radius // 2)
    for i in range(0, dist + 1, step):
        t = i / dist
        pygame.draw.circle(surf, C_INK, (int(p1[0] + dx * t), int(p1[1] + dy * t)), radius)

def erase_ink(surf, p1, p2, radius=18):
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    dist = int((dx*dx + dy*dy) ** 0.5)
    clear_c = (0, 0, 0, 0)
    if dist == 0:
        pygame.draw.circle(surf, clear_c, p1, radius)
        return
    step = max(1, radius // 2)
    for i in range(0, dist + 1, step):
        t = i / dist
        pygame.draw.circle(surf, clear_c, (int(p1[0] + dx * t), int(p1[1] + dy * t)), radius)

# ----------------- ISTORIQ I STRANICI -----------------
def push_undo():
    page = pages[curr_idx]
    if len(page.history) >= 8:
        page.history.pop(0)
    page.history.append(page.canvas.copy())

def undo():
    page = pages[curr_idx]
    if len(page.history) > 1:
        page.history.pop()
        page.canvas.fill((0, 0, 0, 0))
        page.canvas.blit(page.history[-1], (0, 0))

def next_page():
    global curr_idx, offset_x, offset_y
    if curr_idx == len(pages) - 1:
        pages.append(Page())
    curr_idx += 1
    offset_x, offset_y = 0, 0

def prev_page():
    global curr_idx, offset_x, offset_y
    if curr_idx > 0:
        curr_idx -= 1
        offset_x, offset_y = 0, 0

# ----------------- GEMINI ASYNC -----------------
def wrap_text(text, font, max_w):
    lines = []
    for par in text.split("\n"):
        if not par.strip():
            lines.append("")
            continue
        words = par.split(" ")
        cur = ""
        for w in words:
            test = (cur + " " + w).strip()
            if font.size(test)[0] <= max_w:
                cur = test
            else:
                if cur: lines.append(cur)
                cur = w
        if cur: lines.append(cur)
    return lines

def run_gemini_async(page):
    global show_ai_drawer
    show_ai_drawer = True
    page.is_loading = True
    page.ai_lines = ["Обработване на ръкописа с Gemini Flash..."]

    def _worker():
        try:
            min_x, min_y, max_x, max_y = page.ink_bounds
            if min_x >= max_x or min_y >= max_y:
                crop_rect = pygame.Rect(0, 0, min(screen_w, CANVAS_W), min(screen_h, CANVAS_H))
            else:
                crop_rect = pygame.Rect(min_x, min_y, max_x - min_x, max_y - min_y)

            crop_surf = pygame.Surface(crop_rect.size, depth=24)
            crop_surf.blit(PAGE_BACKGROUND, (0, 0), area=crop_rect)
            crop_surf.blit(page.canvas, (0, 0), area=crop_rect)

            raw = pygame.image.tostring(crop_surf, "RGB")
            pil_img = Image.frombytes("RGB", crop_rect.size, raw)

            img_buf = io.BytesIO()
            pil_img.save(img_buf, format="JPEG", quality=85)
            img_buf.seek(0)
            pil_ready = Image.open(img_buf)

            prompt = (
                "Ти си асистент за учебни бележки. Разгледай ръкописа:\n"
                "1. Транскрибирай текста и формулите точно.\n"
                "2. Направи кратко обобщение и ключови изводи.\n"
                "Отговаряй на чист български език със стегнати точки."
            )

            if gemini_client and os.environ.get("GEMINI_API_KEY"):
                resp = gemini_client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=[pil_ready, prompt]
                )
                txt = resp.text
            else:
                txt = "Демо режим (няма GEMINI_API_KEY):\n• Ръкописът е разчетен успешно.\n• Извлечени ключови понятия.\n• Готово за преговор."

            page.ai_lines = wrap_text(txt, font_main, drawer_width - 40)
        except Exception as e:
            page.ai_lines = [f"Грешка: {e}"]
        finally:
            page.is_loading = False

    threading.Thread(target=_worker, daemon=True).start()

# ----------------- UI ELEMENTI -----------------
class Button:
    def __init__(self, rect, text, action_name, is_toggle=False):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.action = action_name
        self.is_toggle = is_toggle

    def draw(self, surf, mouse_pos, is_active=False):
        hover = self.rect.collidepoint(mouse_pos)
        if is_active:
            bg = C_BTN_ACTIVE
            txt_c = C_BTN_ACTIVE_TXT
        else:
            bg = C_BTN_HOVER if hover else C_BTN_BG
            txt_c = C_TEXT

        pygame.draw.rect(surf, bg, self.rect, border_radius=5)
        pygame.draw.rect(surf, C_TOOLBAR_BORDER, self.rect, 1, border_radius=5)
        txt = font_ui.render(self.text, True, txt_c)
        surf.blit(txt, (self.rect.centerx - txt.get_width() // 2, self.rect.centery - txt.get_height() // 2))

# ----------------- OSNOVEN CIKUL -----------------
clock = pygame.time.Clock()

while True:
    page = pages[curr_idx]
    mouse_x, mouse_y = pygame.mouse.get_pos()
    current_effective = get_effective_tool()

    # Butoni v lentata
    btn_tool_pen = Button((15, 8, 80, 30), "Молив", "tool_pen", is_toggle=True)
    btn_tool_eraser = Button((100, 8, 90, 30), "Гумичка", "tool_eraser", is_toggle=True)
    btn_tool_pan = Button((195, 8, 90, 30), "Местене", "tool_pan", is_toggle=True)

    btn_prev = Button((screen_w // 2 - 95, 8, 38, 30), "<", "prev")
    btn_next = Button((screen_w // 2 + 55, 8, 38, 30), ">", "next")

    btn_ai = Button((screen_w - 210, 8, 75, 30), "AI", "ai")
    btn_cfg = Button((screen_w - 125, 8, 110, 30), "⚙ Клавиши", "settings")

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()

        elif event.type == pygame.VIDEORESIZE:
            screen_w, screen_h = event.w, event.h
            screen = pygame.display.set_mode((screen_w, screen_h), pygame.RESIZABLE | pygame.DOUBLEBUF)

        # ----------------- NATISKANE NA KLAVISH -----------------
        elif event.type == pygame.KEYDOWN:
            if waiting_for_key:
                if event.key != pygame.K_ESCAPE:
                    KEY_BINDS[waiting_for_key] = event.key
                    save_keybinds(KEY_BINDS)
                waiting_for_key = None
                continue

            if show_settings_modal:
                if event.key == pygame.K_ESCAPE:
                    show_settings_modal = False
                continue

            # Hold deistviq: aktivirat se pri natiskane
            if event.key == KEY_BINDS.get("hold_eraser"):
                key_override_tool = "eraser"
                if is_holding_mouse:
                    current_action = "eraser"
            elif event.key == KEY_BINDS.get("hold_pan"):
                key_override_tool = "pan"
                if is_holding_mouse:
                    current_action = "pan"
                    pan_start = (mouse_x, mouse_y - TOOLBAR_H)
                    pan_offset_start = (offset_x, offset_y)

            # Standartni deistviq
            elif event.key == KEY_BINDS.get("undo"):
                undo()
            elif event.key == KEY_BINDS.get("prev_page"):
                prev_page()
            elif event.key == KEY_BINDS.get("next_page"):
                next_page()
            elif event.key == KEY_BINDS.get("gemini"):
                if not show_ai_drawer:
                    run_gemini_async(page)
                else:
                    show_ai_drawer = False
            elif event.key == pygame.K_ESCAPE:
                if show_ai_drawer:
                    show_ai_drawer = False
                else:
                    pygame.quit()
                    sys.exit()

        # ----------------- PUSKANE NA KLAVISH (HOLD RELEASE) -----------------
        elif event.type == pygame.KEYUP:
            if event.key == KEY_BINDS.get("hold_eraser") and key_override_tool == "eraser":
                key_override_tool = None
                if is_holding_mouse:
                    push_undo()
                    current_action = active_tool
            elif event.key == KEY_BINDS.get("hold_pan") and key_override_tool == "pan":
                key_override_tool = None
                if is_holding_mouse:
                    current_action = active_tool

        # ----------------- MISHKA / PISALKA DOWN -----------------
        elif event.type == pygame.MOUSEBUTTONDOWN:
            mx, my = event.pos

            # 1. Nastroiki modal
            if show_settings_modal:
                modal_rect = pygame.Rect(screen_w // 2 - 240, screen_h // 2 - 210, 480, 420)
                if not modal_rect.collidepoint(mx, my):
                    show_settings_modal = False
                else:
                    start_y = screen_h // 2 - 140
                    for action in BIND_LABELS.keys():
                        row_btn = pygame.Rect(modal_rect.right - 145, start_y, 120, 30)
                        if row_btn.collidepoint(mx, my):
                            waiting_for_key = action
                            break
                        start_y += 48
                continue

            # 2. Toolbar klikove
            if my < TOOLBAR_H:
                if btn_tool_pen.rect.collidepoint(mx, my):
                    active_tool = "pen"
                elif btn_tool_eraser.rect.collidepoint(mx, my):
                    active_tool = "eraser"
                elif btn_tool_pan.rect.collidepoint(mx, my):
                    active_tool = "pan"
                elif btn_prev.rect.collidepoint(mx, my):
                    prev_page()
                elif btn_next.rect.collidepoint(mx, my):
                    next_page()
                elif btn_ai.rect.collidepoint(mx, my):
                    if not show_ai_drawer:
                        run_gemini_async(page)
                    else:
                        show_ai_drawer = False
                elif btn_cfg.rect.collidepoint(mx, my):
                    show_settings_modal = True
                continue

            # 3. Zamykane na AI panela
            if show_ai_drawer and mx < (screen_w - drawer_width):
                show_ai_drawer = False
                continue

            # 4. Risuvane v platnoto
            if not (show_ai_drawer and mx >= (screen_w - drawer_width)):
                canvas_y = my - TOOLBAR_H
                is_holding_mouse = True

                # Lqv buton: izpolzva tekushtiq instrument (ili vremenno zadurzhaniq)
                if event.button == 1:
                    current_action = get_effective_tool()
                # Desen buton / Barrel 1: Gumichka
                elif event.button == 3:
                    current_action = "eraser"
                # Sreden buton / Barrel 2: Pan
                elif event.button == 2:
                    current_action = "pan"

                last_pos = (mx + offset_x, canvas_y + offset_y)

                if current_action == "pen":
                    page.track_point(*last_pos)
                    draw_ink(page.canvas, last_pos, last_pos, 2)
                elif current_action == "eraser":
                    erase_ink(page.canvas, last_pos, last_pos, 18)
                elif current_action == "pan":
                    pan_start = (mx, canvas_y)
                    pan_offset_start = (offset_x, offset_y)

        # ----------------- MISHKA / PISALKA UP -----------------
        elif event.type == pygame.MOUSEBUTTONUP:
            if is_holding_mouse:
                if current_action in ("pen", "eraser"):
                    push_undo()
                is_holding_mouse = False
                current_action = None
                last_pos = None

        # ----------------- MOTION (DVÏZHENIE PRI ZADURZHANE) -----------------
        elif event.type == pygame.MOUSEMOTION:
            mx, my = event.pos
            canvas_y = my - TOOLBAR_H

            if is_holding_mouse and current_action:
                if current_action == "pan":
                    dx = mx - pan_start[0]
                    dy = canvas_y - pan_start[1]
                    offset_x = max(0, min(CANVAS_W - screen_w, pan_offset_start[0] - dx))
                    offset_y = max(0, min(CANVAS_H - (screen_h - TOOLBAR_H), pan_offset_start[1] - dy))

                elif current_action == "pen" and last_pos and my >= TOOLBAR_H:
                    curr = (mx + offset_x, canvas_y + offset_y)
                    page.track_point(*curr)
                    draw_ink(page.canvas, last_pos, curr, 2)
                    last_pos = curr

                elif current_action == "eraser" and last_pos and my >= TOOLBAR_H:
                    curr = (mx + offset_x, canvas_y + offset_y)
                    erase_ink(page.canvas, last_pos, curr, 18)
                    last_pos = curr

    # ----------------- RENDERING -----------------
    work_h = screen_h - TOOLBAR_H
    visible_rect = pygame.Rect(offset_x, offset_y, screen_w, work_h)
    screen.blit(PAGE_BACKGROUND, (0, TOOLBAR_H), area=visible_rect)
    screen.blit(page.canvas, (0, TOOLBAR_H), area=visible_rect)

    # Gorna lenta
    pygame.draw.rect(screen, C_TOOLBAR_BG, (0, 0, screen_w, TOOLBAR_H))
    pygame.draw.line(screen, C_TOOLBAR_BORDER, (0, TOOLBAR_H), (screen_w, TOOLBAR_H), 1)

    # Butoni za instrumenti
    btn_tool_pen.draw(screen, (mouse_x, mouse_y), is_active=(current_effective == "pen"))
    btn_tool_eraser.draw(screen, (mouse_x, mouse_y), is_active=(current_effective == "eraser"))
    btn_tool_pan.draw(screen, (mouse_x, mouse_y), is_active=(current_effective == "pan"))

    # Indikator za stranici
    page_txt = font_ui.render(f"Стр. {curr_idx + 1} / {len(pages)}", True, C_TEXT)
    screen.blit(page_txt, (screen_w // 2 - page_txt.get_width() // 2, 14))

    btn_prev.draw(screen, (mouse_x, mouse_y))
    btn_next.draw(screen, (mouse_x, mouse_y))
    btn_ai.draw(screen, (mouse_x, mouse_y))
    btn_cfg.draw(screen, (mouse_x, mouse_y))

    # AI chekmedzhe (Drawer)
    if show_ai_drawer:
        drawer_surf = pygame.Surface((drawer_width, work_h), pygame.SRCALPHA)
        drawer_surf.fill(C_DRAWER_BG)
        screen.blit(drawer_surf, (screen_w - drawer_width, TOOLBAR_H))
        pygame.draw.line(screen, C_LINE, (screen_w - drawer_width, TOOLBAR_H), (screen_w - drawer_width, screen_h), 1)

        screen.blit(font_ui.render("AI Резюме & Бележки", True, C_TEXT), (screen_w - drawer_width + 20, TOOLBAR_H + 20))
        if page.is_loading:
            pygame.draw.circle(screen, C_ACCENT, (screen_w - 30, TOOLBAR_H + 28), 6)

        y = TOOLBAR_H + 60
        for line in page.ai_lines:
            color = C_MUTED if line.startswith("•") or line.startswith("-") else C_TEXT
            txt_s = font_main.render(line, True, color)
            screen.blit(txt_s, (screen_w - drawer_width + 20, y))
            y += 24
            if y > screen_h - 30:
                break

    # Modal za klavishi
    if show_settings_modal:
        overlay = pygame.Surface((screen_w, screen_h), pygame.SRCALPHA)
        overlay.fill(C_OVERLAY_BG)
        screen.blit(overlay, (0, 0))

        mw, mh = 480, 420
        mx_pos, my_pos = screen_w // 2 - mw // 2, screen_h // 2 - mh // 2
        pygame.draw.rect(screen, C_PAPER, (mx_pos, my_pos, mw, mh), border_radius=8)
        pygame.draw.rect(screen, C_TOOLBAR_BORDER, (mx_pos, my_pos, mw, mh), 1, border_radius=8)

        title = font_modal.render("Настройка на бързи клавиши", True, C_TEXT)
        screen.blit(title, (mx_pos + 20, my_pos + 20))

        start_y = my_pos + 65
        for action, label in BIND_LABELS.items():
            lbl_surf = font_main.render(label, True, C_TEXT)
            screen.blit(lbl_surf, (mx_pos + 25, start_y + 5))

            btn_rect = pygame.Rect(mx_pos + mw - 145, start_y, 120, 30)
            btn_active = (waiting_for_key == action)
            btn_c = C_ACCENT if btn_active else C_BTN_BG
            pygame.draw.rect(screen, btn_c, btn_rect, border_radius=4)

            k_code = KEY_BINDS.get(action, pygame.K_UNKNOWN)
            k_name = "Натиснете..." if btn_active else pygame.key.name(k_code).upper()
            t_color = (255, 255, 255) if btn_active else C_TEXT
            k_surf = font_ui.render(k_name, True, t_color)
            screen.blit(k_surf, (btn_rect.centerx - k_surf.get_width() // 2, btn_rect.centery - k_surf.get_height() // 2))

            start_y += 48

        hint = font_main.render("Кликнете извън прозореца или натиснете ESC за изход.", True, C_MUTED)
        screen.blit(hint, (mx_pos + 25, my_pos + mh - 35))

    pygame.display.flip()
    clock.tick(120)

