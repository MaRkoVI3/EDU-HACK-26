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

# IP адрес на чина (Raspberry Pi)
PI_IP = "10.124.145.219" 
PI_PORT = 5005

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def send_signal_to_desk(payload):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2.0)
        s.connect((PI_IP, PI_PORT))
        raw = json.dumps(payload).encode("utf-8")
        s.sendall(len(raw).to_bytes(4, "big") + raw)
        s.close()
        return True, "Успех"
    except Exception as e:
        return False, str(e)

HTML_PAGE = """
<!DOCTYPE html>
<html lang="bg">
<head>
    <meta charset="UTF-8">
    <title>Учителски контролен панел</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0b0f19; color: #f8fafc; padding: 24px; margin: 0; }
        .box { max-width: 900px; margin: 0 auto; }
        h1 { color: #38bdf8; font-size: 24px; margin-bottom: 20px; }
        .card { background: #1e293b; padding: 20px; border-radius: 12px; margin-bottom: 24px; border: 1px solid #334155; }
        h3 { margin-top: 0; color: #94a3b8; font-size: 16px; border-bottom: 1px solid #334155; padding-bottom: 8px; }
        .btn { background: #0284c7; color: white; border: none; padding: 8px 14px; border-radius: 6px; cursor: pointer; font-size: 13px; font-weight: bold; }
        .btn:hover { background: #0369a1; }
        .btn-green { background: #16a34a; }
        .btn-green:hover { background: #15803d; }
        .btn-del { background: #ef4444; padding: 4px 8px; font-size: 12px; }
        .btn-del:hover { background: #dc2626; }
        .btn-tap { background: #3b82f6; margin-right: 6px; }
        table { width: 100%; border-collapse: collapse; margin-top: 12px; }
        th, td { text-align: left; padding: 10px; border-bottom: 1px solid #334155; font-size: 14px; }
        th { color: #94a3b8; }
        input, select { background: #0f172a; border: 1px solid #334155; color: white; padding: 8px; border-radius: 6px; font-size: 13px; }
        .form-row { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 12px; align-items: center; }
        .log { background: #020617; padding: 12px; border-radius: 8px; font-family: monospace; color: #38bdf8; margin-top: 14px; font-size: 13px; }
    </style>
</head>
<body>
<div class="box">
    <h1>🏫 Учителско бюро (Управление на чина)</h1>

    <!-- 1. УЧЕНИЦИ И СИМУЛАЦИЯ НА КАРТИ -->
    <div class="card">
        <h3>1. Ученици & Вход на чина (Симулация на NFC)</h3>
        
        <!-- Форма за добавяне -->
        <form id="add-student-form" class="form-row" onsubmit="addStudent(event)">
            <input type="text" id="st-name" placeholder="Име на ученика" required>
            <input type="text" id="st-grade" placeholder="Клас (напр. 10А)" required style="width: 100px;">
            <input type="email" id="st-email" placeholder="Google имейл (Classroom)" required style="width: 200px;">
            <input type="text" id="st-uid" placeholder="NFC UID (напр. 1001)" required style="width: 120px;">
            <button type="submit" class="btn btn-green">+ Добави ученик</button>
        </form>

        <table>
            <tr>
                <th>NFC Код</th>
                <th>Име</th>
                <th>Клас</th>
                <th>Google Account</th>
                <th>Действия</th>
            </tr>
            {% for s in students %}
            <tr>
                <td><code>{{ s.nfc_uid }}</code></td>
                <td><strong>{{ s.name }}</strong></td>
                <td><span style="background: #334155; padding: 2px 6px; border-radius: 4px;">{{ s.grade }}</span></td>
                <td>{{ s.google_email }}</td>
                <td>
                    <button class="btn btn-tap" onclick="loginStudent('{{ s.student_id }}')">📡 Допри карта</button>
                    <button class="btn btn-del" onclick="deleteStudent('{{ s.nfc_uid }}')">✕</button>
                </td>
            </tr>
            {% endfor %}
        </table>
        <div id="login-log" class="log">Готов за сканиране на карти...</div>
    </div>

    <!-- 2. УЧЕБНИЦИ ПО КЛАСОВЕ -->
    <div class="card">
        <h3>2. Учебници & Материали</h3>
        
        <!-- Форма за качване на истински учебник -->
        <div class="form-row">
            <input type="file" id="pdf-input" accept=".pdf" required>
            <input type="text" id="book-subject" placeholder="Предмет (напр. Математика)" required>
            <input type="text" id="book-grade" placeholder="За кой клас (напр. 10А)" required style="width: 120px;">
            <button class="btn btn-green" onclick="uploadMaterial()">📤 Качи PDF</button>
        </div>

        <table>
            <tr>
                <th>Предмет</th>
                <th>Файл</th>
                <th>Клас</th>
                <th>Действие</th>
            </tr>
            {% for b in textbooks %}
            <tr>
                <td><strong>{{ b.subject }}</strong></td>
                <td>{{ b.filename }}</td>
                <td><span style="background: #334155; padding: 2px 6px; border-radius: 4px;">{{ b.grade }}</span></td>
                <td>
                    <button class="btn btn-del" onclick="deleteBook('{{ b.id }}')">✕ Изтрий</button>
                </td>
            </tr>
            {% endfor %}
        </table>
        <div id="upload-log" class="log">Избери учебен материал за качване.</div>
    </div>
</div>

<script>
function loginStudent(id) {
    const log = document.getElementById('login-log');
    log.innerText = `Пращане на сигнал към чина...`;
    fetch(`/api/login/${id}`, { method: 'POST' })
    .then(r => r.json())
    .then(data => { log.innerText = data.msg; })
    .catch(err => { log.innerText = "Грешка: " + err; });
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
    const log = document.getElementById('upload-log');

    if (!fileInput.files.length || !subject || !grade) {
        alert("Попълнете предмет, клас и изберете PDF файл!");
        return;
    }
    log.innerText = "Качване на учебника...";
    const formData = new FormData();
    formData.append("file", fileInput.files[0]);
    formData.append("subject", subject);
    formData.append("grade", grade);

    fetch('/api/upload', { method: 'POST', body: formData })
    .then(r => r.json())
    .then(data => {
        log.innerText = data.msg;
        if(data.success) setTimeout(() => location.reload(), 1200);
    });
}

function deleteBook(bookId) {
    if(!confirm("Изтриване на този учебник от базата?")) return;
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
    return render_template_string(HTML_PAGE, students=students, textbooks=textbooks)

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

    db.execute("UPDATE desk_status SET current_student_id = ?, last_ping = CURRENT_TIMESTAMP WHERE desk_id = 1", (student_id,))
    db.commit()

    books = db.execute("SELECT * FROM textbooks WHERE grade = ?", (student["grade"],)).fetchall()
    books_list = [dict(b) for b in books]
    db.close()

    payload = {
        "action": "LOGIN",
        "student": {
            "id": student["student_id"],
            "name": student["name"],
            "grade": student["grade"],
            "email": student["google_email"]
        },
        "textbooks": books_list
    }

    ok, err = send_signal_to_desk(payload)
    if ok:
        msg = f"Успех! {student['name']} ({student['grade']}) е логнат на чина. Заредени {len(books_list)} учебника."
    else:
        msg = f"Записано в базата за {student['name']}, но чинът не отговаря на {PI_IP}:{PI_PORT} (изключен е)."

    return jsonify({"success": True, "msg": msg})

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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)