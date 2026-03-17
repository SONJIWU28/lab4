import os
import psycopg2
import re
from psycopg2.extras import RealDictCursor
from flask import Flask, request, redirect, url_for, render_template_string

app = Flask(__name__)
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/phone_directory")


def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS contacts (
            id SERIAL PRIMARY KEY,
            full_name VARCHAR(200) NOT NULL,
            phone VARCHAR(30) NOT NULL,
            note TEXT DEFAULT ''
        )
    """)

    cur.execute("""
        ALTER TABLE contacts DROP CONSTRAINT IF EXISTS chk_full_name_format;
        ALTER TABLE contacts DROP CONSTRAINT IF EXISTS chk_phone_format;
    """)

    cur.execute("""
        DELETE FROM contacts 
        WHERE full_name !~ '^[А-Яа-яA-Za-z-]+[[:space:]]+[А-Яа-яA-Za-z-]+[[:space:]]+[А-Яа-яA-Za-z-]+$'
           OR phone !~ '^\+[0-9]-[0-9]{3}-[0-9]{3}-[0-9]{2}-[0-9]{2}$';

        ALTER TABLE contacts
        ADD CONSTRAINT chk_full_name_format
        CHECK (full_name ~ '^[А-Яа-яA-Za-z-]+[[:space:]]+[А-Яа-яA-Za-z-]+[[:space:]]+[А-Яа-яA-Za-z-]+$');

        ALTER TABLE contacts
        ADD CONSTRAINT chk_phone_format
        CHECK (phone ~ '^\+[0-9]-[0-9]{3}-[0-9]{3}-[0-9]{2}-[0-9]{2}$');
    """)
    cur.execute("SELECT COUNT(*) FROM contacts")
    if cur.fetchone()[0] == 0:
        cur.execute("""
            INSERT INTO contacts (full_name, phone, note) VALUES
                ('Иванов Иван Иванович', '+7-900-111-22-33', 'Коллега по работе'),
                ('Петрова Мария Сергеевна', '+7-900-444-55-66', 'Соседка'),
                ('Сидоров Алексей Петрович', '+7-900-777-88-99', 'Друг из университета')
        """)

    cur.close()
    conn.close()

def validate_full_name(name):
    words = name.strip().split()
    if len(name) > 100:
        return False, "ФИО не должно превышать 100 символов"
    
    if len(words) != 3:
        return False, "ФИО должно состоять из 3 слов (фамилия, имя, отчество)"
    
    for word in words:
        if len(word) < 2:
            return False, f"Слово '{word}' слишком короткое"
        if len(word) > 30:
            return False, f"Слово '{word}' слишком длинное"
        if not re.match(r'^[А-Яа-яA-Za-z-]+$', word):
            return False, f"Слово '{word}' содержит недопустимые символы"
    
    return True, "OK"


def validate_phone(phone):
    if len(phone) > 20:
        return False, "Номер телефона слишком длинный (максимум 20 символов)"
    
    pattern = r'^\+\d-\d{3}-\d{3}-\d{2}-\d{2}$'
    if not re.match(pattern, phone):
        return False, "Телефон должен быть в формате +7-900-111-22-33"
    
    return True, "OK"

TEMPLATE = '''
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Телефонная книга</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: #f0f2f5;
            color: #1a1a2e;
            min-height: 100vh;
        }

        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px 0;
            text-align: center;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
        }

        .header h1 { font-size: 28px; font-weight: 600; }
        .header p { margin-top: 6px; opacity: 0.85; font-size: 14px; }

        .container {
            max-width: 900px;
            margin: 30px auto;
            padding: 0 20px;
        }

        .card {
            background: white;
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 24px;
            box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
        }

        .card h2 {
            font-size: 18px;
            margin-bottom: 16px;
            color: #667eea;
        }

        .form-row {
            display: flex;
            gap: 12px;
            flex-wrap: wrap;
            align-items: flex-end;
        }

        .form-group {
            flex: 1;
            min-width: 180px;
        }

        .form-group label {
            display: block;
            font-size: 13px;
            font-weight: 500;
            margin-bottom: 4px;
            color: #555;
        }

        .form-group input {
            width: 100%;
            padding: 10px 12px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-size: 14px;
            transition: border-color 0.2s;
        }

        .form-group input:focus {
            outline: none;
            border-color: #667eea;
        }

        .btn {
            padding: 10px 20px;
            border: none;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s;
            text-decoration: none;
            display: inline-block;
        }

        .btn-primary {
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
        }

        .btn-primary:hover { opacity: 0.9; transform: translateY(-1px); }

        .btn-danger {
            background: #ff6b6b;
            color: white;
            padding: 6px 14px;
            font-size: 13px;
        }

        .btn-danger:hover { background: #ee5a5a; }

        .btn-edit {
            background: #ffa726;
            color: white;
            padding: 6px 14px;
            font-size: 13px;
        }

        .btn-edit:hover { background: #fb8c00; }

        .search-box {
            width: 100%;
            padding: 12px 16px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-size: 15px;
            margin-bottom: 16px;
            transition: border-color 0.2s;
        }

        .search-box:focus { outline: none; border-color: #667eea; }

        table {
            width: 100%;
            border-collapse: collapse;
        }

        th {
            text-align: left;
            padding: 12px;
            font-size: 13px;
            color: #888;
            border-bottom: 2px solid #f0f0f0;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        td {
            padding: 14px 12px;
            border-bottom: 1px solid #f5f5f5;
            font-size: 14px;
        }

        tr:hover td { background: #fafbff; }

        .actions { display: flex; gap: 6px; }

        .empty {
            text-align: center;
            padding: 40px;
            color: #aaa;
            font-size: 15px;
        }

        .badge {
            display: inline-block;
            background: #f0f2f5;
            color: #667eea;
            padding: 2px 10px;
            border-radius: 12px;
            font-size: 13px;
            font-weight: 500;
        }

        .modal-bg {
            display: none;
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0,0,0,0.4);
            z-index: 100;
            align-items: center;
            justify-content: center;
        }

        .modal-bg.active { display: flex; }

        .modal {
            background: white;
            border-radius: 12px;
            padding: 28px;
            width: 90%;
            max-width: 500px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }

        .modal h2 { margin-bottom: 20px; }

        .modal .form-group { margin-bottom: 14px; min-width: unset; }

        .modal-actions {
            display: flex;
            gap: 10px;
            justify-content: flex-end;
            margin-top: 20px;
        }

        .btn-cancel {
            background: #e0e0e0;
            color: #555;
            padding: 10px 20px;
        }

        .btn-cancel:hover { background: #d0d0d0; }
    </style>
</head>
<body>

<div class="header">
    <h1>Телефонная книга</h1>
    <p>Управление контактами</p>
</div>

<div class="container">

    <div class="card">
        <h2>Добавить контакт</h2>
        <form method="POST" action="/add">
            <div class="form-row">
                <div class="form-group">
                    <label>ФИО</label>
                    <input type="text" name="full_name" placeholder="Иванов Иван Иванович" required>
                </div>
                <div class="form-group">
                    <label>Телефон</label>
                    <input type="text" name="phone" placeholder="+7-900-123-45-67" required>
                </div>
                <div class="form-group">
                    <label>Заметка</label>
                    <input type="text" name="note" placeholder="Необязательно">
                </div>
                <button type="submit" class="btn btn-primary">Добавить</button>
            </div>
        </form>
    </div>

    <div class="card">
        <h2>Контакты <span class="badge">{{ contacts|length }}</span></h2>
        <input type="text" class="search-box" id="search" placeholder="Поиск по имени или телефону..." onkeyup="filterTable()">

        {% if contacts %}
        <table id="contactsTable">
            <thead>
                <tr>
                    <th>ФИО</th>
                    <th>Телефон</th>
                    <th>Заметка</th>
                    <th>Действия</th>
                </tr>
            </thead>
            <tbody>
                {% for c in contacts %}
                <tr>
                    <td>{{ c.full_name }}</td>
                    <td>{{ c.phone }}</td>
                    <td>{{ c.note or '—' }}</td>
                    <td class="actions">
                        <button class="btn btn-edit" onclick="openEdit({{ c.id }}, '{{ c.full_name }}', '{{ c.phone }}', '{{ c.note or '' }}')">Изменить</button>
                        <form method="POST" action="/delete/{{ c.id }}" style="display:inline" onsubmit="return confirm('Удалить контакт?')">
                            <button type="submit" class="btn btn-danger">Удалить</button>
                        </form>
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        {% else %}
        <div class="empty">Контактов пока нет</div>
        {% endif %}
    </div>
</div>

<div class="modal-bg" id="editModal">
    <div class="modal">
        <h2>Редактировать контакт</h2>
        <form method="POST" id="editForm">
            <div class="form-group">
                <label>ФИО</label>
                <input type="text" name="full_name" id="editName" required>
            </div>
            <div class="form-group">
                <label>Телефон</label>
                <input type="text" name="phone" id="editPhone" required>
            </div>
            <div class="form-group">
                <label>Заметка</label>
                <input type="text" name="note" id="editNote">
            </div>
            <div class="modal-actions">
                <button type="button" class="btn btn-cancel" onclick="closeEdit()">Отмена</button>
                <button type="submit" class="btn btn-primary">Сохранить</button>
            </div>
        </form>
    </div>
</div>

<script>
function filterTable() {
    const query = document.getElementById('search').value.toLowerCase();
    const rows = document.querySelectorAll('#contactsTable tbody tr');
    rows.forEach(row => {
        const text = row.textContent.toLowerCase();
        row.style.display = text.includes(query) ? '' : 'none';
    });
}

function openEdit(id, name, phone, note) {
    document.getElementById('editForm').action = '/edit/' + id;
    document.getElementById('editName').value = name;
    document.getElementById('editPhone').value = phone;
    document.getElementById('editNote').value = note;
    document.getElementById('editModal').classList.add('active');
}

function closeEdit() {
    document.getElementById('editModal').classList.remove('active');
}

document.getElementById('editModal').addEventListener('click', function(e) {
    if (e.target === this) closeEdit();
});
</script>

</body>
</html>
'''


@app.route('/')
def index():
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM contacts ORDER BY id")
    contacts = cur.fetchall()
    cur.close()
    conn.close()
    return render_template_string(TEMPLATE, contacts=contacts)


@app.route('/add', methods=['POST'])
def add():
    name = request.form['full_name'].strip()
    phone = request.form['phone'].strip()
    note = request.form.get('note', '').strip()

    is_valid_name, name_error = validate_full_name(name)
    if not is_valid_name:
        return f'''<script>alert("Ошибка: {name_error}"); window.location.href = "/";</script>'''

    is_valid_phone, phone_error = validate_phone(phone)
    if not is_valid_phone:
        return f'''<script>alert("Ошибка: {phone_error}"); window.location.href = "/";</script>'''

    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO contacts (full_name, phone, note) VALUES (%s, %s, %s)", (name, phone, note))
    cur.close()
    conn.close()

    return redirect(url_for('index'))


@app.route('/edit/<int:contact_id>', methods=['POST'])
def edit(contact_id):
    name = request.form['full_name'].strip()
    phone = request.form['phone'].strip()
    note = request.form.get('note', '').strip()

    is_valid_name, name_error = validate_full_name(name)
    if not is_valid_name:
        return f'''<script>alert("Ошибка: {name_error}"); window.location.href = "/";</script>'''

    is_valid_phone, phone_error = validate_phone(phone)
    if not is_valid_phone:
        return f'''<script>alert("Ошибка: {phone_error}"); window.location.href = "/";</script>'''

    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE contacts SET full_name=%s, phone=%s, note=%s WHERE id=%s", (name, phone, note, contact_id))
    cur.close()
    conn.close()

    return redirect(url_for('index'))


@app.route('/delete/<int:contact_id>', methods=['POST'])
def delete(contact_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM contacts WHERE id=%s", (contact_id,))
    cur.close()
    conn.close()
    return redirect(url_for('index'))


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000)
