import sqlite3
import os

DB_NAME = "school.db"

def setup_database():
    # Свързване (ако файлът не съществува, SQLite го създава автоматично)
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # 1. Таблица с ученици
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            nfc_uid TEXT PRIMARY KEY,
            student_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            grade TEXT NOT NULL,
            google_email TEXT NOT NULL
        )
    """)

    # 2. Таблица с учебници
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS textbooks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            subject TEXT NOT NULL,
            grade TEXT NOT NULL,
            filename TEXT NOT NULL
        )
    """)

    # 3. Таблица за следене на текущата сесия на чина
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS desk_status (
            desk_id INTEGER PRIMARY KEY,
            current_student_id TEXT,
            last_ping TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Вкарваме примерни тестови ученици
    sample_students = [
        ("1001", "alex", "Алекс", "10А", "alex.student@school.bg"),
        ("1002", "maria", "Мария", "10Б", "maria.student@school.bg"),
        ("1003", "ivan", "Иван", "9В", "ivan.student@school.bg")
    ]

    cursor.executemany("""
        INSERT OR IGNORE INTO students (nfc_uid, student_id, name, grade, google_email)
        VALUES (?, ?, ?, ?, ?)
    """, sample_students)

    # Вкарваме примерни учебници по класове
    sample_books = [
        ("Математика 10. клас", "Математика", "10А", "Matematika_10.pdf"),
        ("Физика 10. клас", "Физика", "10А", "Fizika_10.pdf"),
        ("Български език 10. клас", "БЕЛ", "10Б", "BEL_10.pdf"),
        ("История 9. клас", "История", "9В", "Istoriya_9.pdf")
    ]

    cursor.executemany("""
        INSERT OR IGNORE INTO textbooks (title, subject, grade, filename)
        VALUES (?, ?, ?, ?)
    """, sample_books)

    # Инициализираме статус за чин 1 (в началото свободен)
    cursor.execute("""
        INSERT OR IGNORE INTO desk_status (desk_id, current_student_id)
        VALUES (1, NULL)
    """)

    conn.commit()
    conn.close()
    print(" Базата данни school.db е създадена успешно с тестови данни!")

if __name__ == "__main__":
    setup_database()