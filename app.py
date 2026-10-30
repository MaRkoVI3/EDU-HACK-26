
import os
import sqlite3
import socket
import json
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "school.db")
TEXTBOOKS_DIR = os.path.join(BASE_DIR, "textbooks")
os.makedirs(TEXTBOOKS_DIR, exist_ok=True)

# ⚠️ Проверете с "hostname -I" на Raspberry Pi чина дали това е точният адрес
PI_IP = "192.168.1.177" 
PI_PORT = 5005

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS students (
            nfc_uid TEXT PRIMARY KEY,
            student_id TEXT,
            name TEXT,
            grade TEXT,
            google_email TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS textbooks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            subject TEXT,
            grade TEXT,
            filename TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS desk_status (
            desk_id INTEGER PRIMARY KEY,
            current_student_id TEXT,
            last_ping TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("INSERT OR IGNORE INTO desk_status (desk_id, current_student_id) VALUES (1, NULL)")
    conn.commit()
    conn.close()

init_db()

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def send_signal_to_desk(payload, target_ip=None):
    ip = target_ip or PI_IP
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(3.0)
        s.connect((ip, PI_PORT))
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        s.sendall(raw)
        s.close()
        return True, "Успех"
    except Exception as e:
        return False, str(e)

HTML_PAGE = """
<!DOCTYPE html>
<html lang="bg">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Контролен панел | Учителска станция</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #090d14;
            --surface: #101726;
            --surface-elevated: #162033;
            --border: rgba(255, 255, 255, 0.08);
            --border-hover: rgba(255, 255, 255, 0.16);
            --border-accent: #3b82f6;
            --primary: #2563eb;
            --primary-hover: #1d4ed8;
            --emerald: #10b981;
            --emerald-hover: #059669;
            --rose: #f43f5e;
            --rose-hover: #e11d48;
            --text: #f8fafc;
            --text-muted: #94a3b8;
            --text-sub: #64748b;
        }

        * { box-sizing: border-box; }
        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background-color: var(--bg);
            color: var(--text);
            padding: 28px 40px;
            margin: 0;
            min-height: 100vh;
            -webkit-font-smoothing: antialiased;
        }

        .container {
            width: 100%;
            max-width: 1600px;
            margin: 0 auto;
        }

        /* HEADER */
        header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 28px;
            padding-bottom: 18px;
            border-bottom: 1px solid var(--border);
        }

        .brand {
            display: flex;
            align-items: center;
            gap: 14px;
        }

        .brand-badge {
            width: 40px;
            height: 40px;
            background: #1e293b;
            border: 1px solid var(--border);
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #60a5fa;
        }

        h1 {
            font-size: 19px;
            font-weight: 700;
            letter-spacing: -0.01em;
            margin: 0;
            color: #fff;
        }

        p.subtitle {
            margin: 3px 0 0 0;
            font-size: 13px;
            color: var(--text-muted);
        }

        .ip-bar {
            display: flex;
            align-items: center;
            gap: 10px;
            background: var(--surface);
            padding: 6px 12px;
            border-radius: 8px;
            border: 1px solid var(--border);
        }

        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--emerald);
            box-shadow: 0 0 6px var(--emerald);
        }

        .ip-bar label {
            font-size: 12px;
            font-weight: 500;
            color: var(--text-muted);
        }

        /* GRID */
        .grid {
            display: grid;
            grid-template-columns: 1fr;
            gap: 24px;
            align-items: start;
        }

        @media (min-width: 1200px) {
            .grid {
                grid-template-columns: 1.55fr 1fr;
            }
        }

        .card {
            background: var(--surface);
            border-radius: 12px;
            padding: 22px;
            border: 1px solid var(--border);
        }

        .card-header {
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 18px;
            color: var(--text);
            font-size: 14px;
            font-weight: 600;
            letter-spacing: 0.01em;
        }

        .card-header svg {
            color: var(--text-muted);
        }

        /* FORMS */
        .form-row {
            display: flex;
            gap: 8px;
            align-items: center;
            margin-bottom: 14px;
        }

        input[type="text"], input[type="email"] {
            background: #090e17;
            border: 1px solid var(--border);
            color: #fff;
            padding: 9px 12px;
            border-radius: 6px;
            font-size: 13px;
            font-family: inherit;
            outline: none;
            transition: border-color 0.15s ease;
        }

        input:focus {
            border-color: var(--border-accent);
        }

        /* MODERN FILE UPLOAD DROPZONE */
        .dropzone {
            position: relative;
            border: 1px dashed var(--border-hover);
            background: #090e17;
            border-radius: 8px;
            padding: 20px 16px;
            text-align: center;
            cursor: pointer;
            transition: all 0.2s ease;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            gap: 8px;
            margin-bottom: 14px;
        }

        .dropzone:hover, .dropzone.dragover {
            border-color: var(--border-accent);
            background: #0d1524;
        }

        .dropzone input[type="file"] {
            position: absolute;
            top: 0; left: 0; width: 100%; height: 100%;
            opacity: 0;
            cursor: pointer;
        }

        .dropzone-icon {
            color: #60a5fa;
        }

        .dropzone-text {
            font-size: 13px;
            font-weight: 500;
            color: var(--text);
        }

        .dropzone-sub {
            font-size: 11px;
            color: var(--text-sub);
        }

        .selected-file-name {
            font-size: 12px;
            color: #38bdf8;
            font-weight: 500;
            display: none;
            word-break: break-all;
        }

        /* BUTTONS */
        .btn {
            background: var(--primary);
            color: #fff;
            border: none;
            padding: 8px 14px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 12px;
            font-weight: 500;
            font-family: inherit;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 6px;
            white-space: nowrap;
            transition: background-color 0.15s ease;
        }

        .btn:hover { background: var(--primary-hover); }

        .btn-emerald { background: var(--emerald); }
        .btn-emerald:hover { background: var(--emerald-hover); }

        .action-cell {
            display: flex;
            align-items: center;
            justify-content: flex-end;
            gap: 6px;
        }

        .btn-tap {
            background: rgba(59, 130, 246, 0.12);
            color: #60a5fa;
            border: 1px solid rgba(59, 130, 246, 0.24);
            padding: 6px 10px;
            font-size: 12px;
        }
        .btn-tap:hover { background: var(--primary); color: #fff; }

        .btn-del {
            background: rgba(244, 63, 94, 0.1);
            color: #fb7185;
            border: 1px solid rgba(244, 63, 94, 0.2);
            padding: 6px 9px;
            font-size: 12px;
        }
        .btn-del:hover { background: var(--rose); color: #fff; }

        /* TABLES */
        .table-wrap {
            overflow-x: auto;
            border-radius: 8px;
            border: 1px solid var(--border);
            margin-top: 6px;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
            text-align: left;
        }

        th {
            background: #0c121e;
            color: var(--text-sub);
            padding: 10px 14px;
            font-weight: 600;
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            border-bottom: 1px solid var(--border);
            white-space: nowrap;
        }

        td {
            padding: 10px 14px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.04);
            color: var(--text);
            vertical-align: middle;
        }

        tr:last-child td { border-bottom: none; }
        tr:hover td { background: rgba(255, 255, 255, 0.02); }

        .badge {
            display: inline-block;
            padding: 2px 7px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 500;
            white-space: nowrap;
        }

        .badge-grade {
            background: rgba(59, 130, 246, 0.1);
            color: #60a5fa;
            border: 1px solid rgba(59, 130, 246, 0.2);
        }

        .badge-uid {
            background: rgba(255, 255, 255, 0.05);
            color: var(--text-muted);
            font-family: monospace;
            border: 1px solid var(--border);
        }

        .log-box {
            background: #090e17;
            padding: 10px 14px;
            border-radius: 6px;
            font-size: 12px;
            color: #93c5fd;
            border: 1px solid var(--border);
            margin-top: 14px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
    </style>
</head>
<body>

<div class="container">
    <header>
        <div class="brand">
            <div class="brand-badge">
                <svg width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"></rect><line x1="8" y1="21" x2="16" y2="21"></line><line x1="12" y1="17" x2="12" y2="21"></line></svg>
            </div>
            <div>
                <h1>Учителска станция</h1>
                <p class="subtitle">Управление на смарт чинове, сесии и електронни ресурси</p>
            </div>
        </div>

        <div class="ip-bar">
            <div class="status-dot"></div>
            <label>Raspberry Pi:</label>
            <input type="text" id="desk-ip" value="{{ pi_ip }}" style="width: 125px; padding: 4px 8px; font-size: 12px;">
            <button class="btn" style="padding: 5px 10px;" onclick="saveDeskIP()">Запази</button>
        </div>
    </header>

    <div class="grid">
        <!-- 1. УЧЕНИЦИ -->
        <div class="card">
            <div class="card-header">
                <svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg>
                Ученици и сесии на чина
            </div>
            
            <form id="add-student-form" class="form-row" onsubmit="addStudent(event)">
                <input type="text" id="st-name" placeholder="Име и фамилия" required style="flex: 2; min-width: 130px;">
                <input type="text" id="st-grade" placeholder="Клас" required style="width: 75px;">
                <input type="email" id="st-email" placeholder="Google акаунт" required style="flex: 2.5; min-width: 170px;">
                <input type="text" id="st-uid" placeholder="NFC UID" required style="width: 85px;">
                <button type="submit" class="btn btn-emerald">+ Добави</button>
            </form>

            <div class="table-wrap">
                <table>
                    <thead>
                        <tr>
                            <th style="width: 80px;">NFC UID</th>
                            <th style="width: 180px;">Име</th>
                            <th style="width: 70px;">Клас</th>
                            <th>Google Профил</th>
                            <th style="width: 155px; text-align: right;">Действия</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for s in students %}
                        <tr>
                            <td><span class="badge badge-uid">{{ s.nfc_uid }}</span></td>
                            <td><strong>{{ s.name }}</strong></td>
                            <td><span class="badge badge-grade">{{ s.grade }}</span></td>
                            <td style="color: var(--text-muted); font-size: 12px;">{{ s.google_email }}</td>
                            <td>
                                <div class="action-cell">
                                    <button class="btn btn-tap" onclick="loginStudent('{{ s.student_id }}')">
                                        <svg width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M4.9 19.1C1 15.2 1 8.8 4.9 4.9"></path><path d="M7.8 16.2c-2.3-2.3-2.3-6.1 0-8.5"></path><circle cx="12" cy="12" r="2"></circle><path d="M16.2 7.8c2.3 2.3 2.3 6.1 0 8.5"></path><path d="M19.1 4.9C23 8.8 23 15.2 19.1 19.1"></path></svg>
                                        Допри карта
                                    </button>
                                    <button class="btn btn-del" onclick="deleteStudent('{{ s.nfc_uid }}')">✕</button>
                                </div>
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>

            <div id="login-log" class="log-box">
                <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>
                <span id="login-log-txt">Готов за сканиране на карти и управление...</span>
            </div>
        </div>

        <!-- 2. МАТЕРИАЛИ -->
        <div class="card">
            <div class="card-header">
                <svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path></svg>
                Учебници и дигитални материали
            </div>

            <!-- MODERNISED DROPZONE -->
            <div class="dropzone" id="drop-area">
                <input type="file" id="pdf-input" accept=".pdf" onchange="handleFileSelect(this)">
                <div class="dropzone-icon">
                    <svg width="26" height="26" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="17 8 12 3 7 8"></polyline><line x1="12" y1="3" x2="12" y2="15"></line></svg>
                </div>
                <div class="dropzone-text" id="drop-prompt">Изберете PDF файл или го плъзнете тук</div>
                <div class="dropzone-sub" id="drop-sub">Поддържа се само .pdf формат</div>
                <div class="selected-file-name" id="file-display"></div>
            </div>

            <div class="form-row">
                <input type="text" id="book-subject" placeholder="Предмет (напр. Математика)" required style="flex: 2;">
                <input type="text" id="book-grade" placeholder="Клас (10Г)" required style="width: 85px;">
                <button class="btn btn-emerald" onclick="uploadMaterial()">Качи материал</button>
            </div>

            <div class="table-wrap">
                <table>
                    <thead>
                        <tr>
                            <th>Предмет</th>
                            <th>Файл</th>
                            <th style="width: 70px;">Клас</th>
                            <th style="width: 60px; text-align: right;">Изтрий</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for b in textbooks %}
                        <tr>
                            <td><strong>{{ b.subject }}</strong></td>
                            <td style="color: var(--text-muted); font-size: 12px; word-break: break-all;">{{ b.filename }}</td>
                            <td><span class="badge badge-grade">{{ b.grade }}</span></td>
                            <td style="text-align: right;">
                                <button class="btn btn-del" onclick="deleteBook('{{ b.id }}')">✕</button>
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>

            <div id="upload-log" class="log-box">
                <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>
                <span id="upload-log-txt">Файловете се синхронизират автоматично към чина според класа.</span>
            </div>
        </div>
    </div>
</div>

<script>
function handleFileSelect(input) {
    const display = document.getElementById('file-display');
    const prompt = document.getElementById('drop-prompt');
    const sub = document.getElementById('drop-sub');
    if (input.files && input.files[0]) {
        const file = input.files[0];
        display.innerText = "Избран файл: " + file.name + " (" + (file.size / (1024*1024)).toFixed(2) + " MB)";
        display.style.display = "block";
        prompt.style.display = "none";
        sub.style.display = "none";
    }
}

function saveDeskIP() {
    const ip = document.getElementById('desk-ip').value.trim();
    fetch('/api/set_ip', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ ip: ip })
    })
    .then(r => r.json())
    .then(d => { alert(d.msg); });
}

function loginStudent(id) {
    const logTxt = document.getElementById('login-log-txt');
    logTxt.innerText = "Изпращане на сигнал към чина...";
    fetch(`/api/login/${id}`, { method: 'POST' })
    .then(r => r.json())
    .then(data => { logTxt.innerText = data.msg; })
    .catch(err => { logTxt.innerText = "Грешка: " + err; });
}

function addStudent(e) {
    e.preventDefault();
    const payload = {
        name: document.getElementById('st-name').value,
        grade: document.getElementById('st-grade').value,
        email: document.getElementById('st-email').value,
        uid: document.getElementById('st-uid').value
    };
    fetch('/api/students/add', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
    })
    .then(r => r.json())
    .then(data => { location.reload(); });
}

function deleteStudent(uid) {
    if(!confirm("Сигурни ли сте, че искате да изтриете този ученик?")) return;
    fetch(`/api/students/del/${uid}`, { method: 'POST' })
    .then(r => r.json())
    .then(data => { location.reload(); });
}

function uploadMaterial() {
    const fileInput = document.getElementById('pdf-input');
    const subject = document.getElementById('book-subject').value;
    const grade = document.getElementById('book-grade').value;
    const logTxt = document.getElementById('upload-log-txt');

    if (!fileInput.files.length || !subject || !grade) {
        alert("Моля, попълнете предмет, клас и изберете PDF файл.");
        return;
    }
    logTxt.innerText = "Качване на материала...";
    const formData = new FormData();
    formData.append("file", fileInput.files[0]);
    formData.append("subject", subject);
    formData.append("grade", grade);

    fetch('/api/upload', { method: 'POST', body: formData })
    .then(r => r.json())
    .then(data => { 
        logTxt.innerText = data.msg; 
        if(data.success) setTimeout(() => location.reload(), 800);
    });
}

function deleteBook(bookId) {
    if(!confirm("Изтриване на този материал?")) return;
    fetch(`/api/textbooks/del/${bookId}`, { method: 'POST' })
    .then(r => r.json())
    .then(data => { location.reload(); });
}
</script>
</body>
</html>
"""

@app.route("/")
def index():
    db = get_db()
    students = db.execute("SELECT * FROM students").fetchall()
    textbooks = db.execute("SELECT * FROM textbooks").fetchall()
    db.close()
    return render_template_string(HTML_PAGE, students=students, textbooks=textbooks, pi_ip=PI_IP)

@app.route("/api/set_ip", methods=["POST"])
def api_set_ip():
    global PI_IP
    data = request.json or {}
    new_ip = data.get("ip", "").strip()
    if new_ip:
        PI_IP = new_ip
        return jsonify({"success": True, "msg": f"IP адресът е сменен на {PI_IP}"})
    return jsonify({"success": False, "msg": "Невалиден IP адрес!"})

@app.route("/api/students/add", methods=["POST"])
def api_add_student():
    data = request.json
    db = get_db()
    clean_id = data["name"].strip().lower().replace(" ", "_")
    db.execute("""
        INSERT OR REPLACE INTO students (nfc_uid, student_id, name, grade, google_email)
        VALUES (?, ?, ?, ?, ?)
    """, (data["uid"].strip(), clean_id, data["name"].strip(), data["grade"].strip(), data["email"].strip()))
    db.commit()
    db.close()
    return jsonify({"success": True})

@app.route("/api/students/del/<uid>", methods=["POST"])
def api_del_student(uid):
    db = get_db()
    db.execute("DELETE FROM students WHERE nfc_uid = ?", (uid,))
    db.commit()
    db.close()
    return jsonify({"success": True})

@app.route("/api/login/<student_id>", methods=["POST"])
def api_login(student_id):
    db = get_db()
    student = db.execute("SELECT * FROM students WHERE student_id = ?", (student_id,)).fetchone()
    if not student:
        db.close()
        return jsonify({"success": False, "msg": "Ученикът не е намерен!"})

    try:
        db.execute("UPDATE desk_status SET current_student_id = ?, last_ping = CURRENT_TIMESTAMP WHERE desk_id = 1", (student_id,))
        db.commit()
    except Exception:
        pass

    books = db.execute("SELECT * FROM textbooks WHERE grade = ?", (student["grade"],)).fetchall()
    books_list = [dict(b) for b in books]
    db.close()

    email_val = student["google_email"] if "google_email" in student.keys() else ""

    payload = {
        "action": "login",
        "student": {
            "id": student["student_id"],
            "name": student["name"],
            "grade": student["grade"],
            "email": email_val.strip()
        },
        "textbooks": books_list
    }

    ok, err = send_signal_to_desk(payload)
    if ok:
        msg = f"Успех! {student['name']} ({student['grade']}) с акаунт {email_val} е логнат на чина."
    else:
        msg = f"Грешка при изпращане към чина ({PI_IP}:{PI_PORT}): {err}"

    return jsonify({"success": ok, "msg": msg})

@app.route("/api/upload", methods=["POST"])
def api_upload():
    if "file" not in request.files:
        return jsonify({"success": False, "msg": "Липсва файл"})
    f = request.files["file"]
    subject = request.form.get("subject", "Материал").strip()
    grade = request.form.get("grade", "10А").strip()

    if not f.filename.endswith(".pdf"):
        return jsonify({"success": False, "msg": "Разрешени са само PDF файлове!"})

    save_path = os.path.join(TEXTBOOKS_DIR, f.filename)
    f.save(save_path)

    db = get_db()
    db.execute("""
        INSERT INTO textbooks (title, subject, grade, filename)
        VALUES (?, ?, ?, ?)
    """, (f.filename.replace(".pdf", ""), subject, grade, f.filename))
    db.commit()
    db.close()

    return jsonify({"success": True, "msg": f"Файлът '{f.filename}' за {grade} клас е качен успешно!"})

@app.route("/api/textbooks/del/<book_id>", methods=["POST"])
def api_del_book(book_id):
    db = get_db()
    row = db.execute("SELECT filename FROM textbooks WHERE id = ?", (book_id,)).fetchone()
    if row:
        file_p = os.path.join(TEXTBOOKS_DIR, row["filename"])
        if os.path.exists(file_p):
            try: os.remove(file_p)
            except: pass
    db.execute("DELETE FROM textbooks WHERE id = ?", (book_id,))
    db.commit()
    db.close()
    return jsonify({"success": True})


from flask import send_from_directory

@app.route("/api/textbooks/download/<filename>")
def api_download_book(filename):
    return send_from_directory(TEXTBOOKS_DIR, filename)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
EOF