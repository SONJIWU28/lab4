import os
import psycopg2
import re
from psycopg2.extras import RealDictCursor
from flask import Flask, request, redirect, url_for, render_template_string, flash

app = Flask(__name__)
app.secret_key = 'phone-directory-secret-key'

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
            full_name VARCHAR(70) NOT NULL,
            phone VARCHAR(16) NOT NULL,
            note VARCHAR(200) DEFAULT ''
        )
    """)

    cur.execute("""
        ALTER TABLE contacts DROP CONSTRAINT IF EXISTS chk_full_name_format;
        ALTER TABLE contacts DROP CONSTRAINT IF EXISTS chk_phone_format;
        ALTER TABLE contacts DROP CONSTRAINT IF EXISTS chk_full_name_length;
        ALTER TABLE contacts DROP CONSTRAINT IF EXISTS chk_phone_length;
        ALTER TABLE contacts DROP CONSTRAINT IF EXISTS chk_note_length;
    """)

    cur.execute("""
        DELETE FROM contacts
        WHERE full_name !~ '^[А-Яа-яA-Za-z-]{2,20}[[:space:]][А-Яа-яA-Za-z-]{2,20}[[:space:]][А-Яа-яA-Za-z-]{2,20}$'
           OR phone !~ '^\+[0-9]-[0-9]{3}-[0-9]{3}-[0-9]{2}-[0-9]{2}$';

        ALTER TABLE contacts
        ADD CONSTRAINT chk_full_name_format
        CHECK (full_name ~ '^[А-Яа-яA-Za-z-]{2,20}[[:space:]][А-Яа-яA-Za-z-]{2,20}[[:space:]][А-Яа-яA-Za-z-]{2,20}$');

        ALTER TABLE contacts
        ADD CONSTRAINT chk_phone_format
        CHECK (phone ~ '^\+[0-9]-[0-9]{3}-[0-9]{3}-[0-9]{2}-[0-9]{2}$');

        ALTER TABLE contacts
        ADD CONSTRAINT chk_full_name_length
        CHECK (length(full_name) <= 64);

        ALTER TABLE contacts
        ADD CONSTRAINT chk_phone_length
        CHECK (length(phone) = 16);

        ALTER TABLE contacts
        ADD CONSTRAINT chk_note_length
        CHECK (length(note) <= 200);
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
    if not name or not name.strip():
        return False, "ФИО не может быть пустым"
    name = name.strip()
    words = name.split()
    if len(words) != 3:
        return False, "ФИО должно состоять из 3 слов (Фамилия Имя Отчество)"
    for word in words:
        if len(word) < 2:
            return False, f"'{word}' — минимум 2 символа"
        if len(word) > 20:
            return False, f"'{word}' — максимум 20 символов"
        if not re.match(r'^[А-Яа-яA-Za-z-]+$', word):
            return False, f"'{word}' содержит недопустимые символы"
    return True, "OK"


def validate_phone(phone):
    if not phone or not phone.strip():
        return False, "Телефон не может быть пустым"
    phone = phone.strip()
    if not re.match(r'^\+\d-\d{3}-\d{3}-\d{2}-\d{2}$', phone):
        return False, "Формат: +X-XXX-XXX-XX-XX"
    return True, "OK"


def validate_note(note):
    if note and len(note) > 200:
        return False, "Заметка — максимум 200 символов"
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
        .flash-messages { margin-bottom: 16px; }
        .flash {
            padding: 12px 18px;
            border-radius: 8px;
            font-size: 14px;
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            gap: 8px;
            animation: slideIn 0.3s ease;
        }
        .flash-error {
            background: #fff0f0;
            color: #d32f2f;
            border: 1px solid #ffcdd2;
        }
        .flash-success {
            background: #f0fff0;
            color: #2e7d32;
            border: 1px solid #c8e6c9;
        }
        @keyframes slideIn {
            from { opacity: 0; transform: translateY(-10px); }
            to { opacity: 1; transform: translateY(0); }
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
            align-items: flex-start;
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
        .form-group input:focus { outline: none; border-color: #667eea; }
        .form-group input.valid { border-color: #4caf50; }
        .form-group input.invalid { border-color: #f44336; }
        .field-hint {
            font-size: 11px;
            margin-top: 3px;
            min-height: 16px;
        }
        .field-hint.error { color: #d32f2f; }
        .field-hint.ok { color: #4caf50; }
        .field-hint.info { color: #999; }
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
            margin-top: 18px;
        }
        .btn:disabled { opacity: 0.5; cursor: not-allowed; }
        .btn-primary {
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
        }
        .btn-primary:hover:not(:disabled) { opacity: 0.9; transform: translateY(-1px); }
        .btn-danger {
            background: #ff6b6b;
            color: white;
            padding: 6px 14px;
            font-size: 13px;
            margin-top: 0;
        }
        .btn-danger:hover { background: #ee5a5a; }
        .btn-edit {
            background: #ffa726;
            color: white;
            padding: 6px 14px;
            font-size: 13px;
            margin-top: 0;
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
        table { width: 100%; border-collapse: collapse; }
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
        .btn-cancel { background: #e0e0e0; color: #555; padding: 10px 20px; }
        .btn-cancel:hover { background: #d0d0d0; }
    </style>
</head>
<body>

<div class="header">
    <h1>Телефонная книга</h1>
    <p>Управление контактами</p>
</div>

<div class="container">

    {% with messages = get_flashed_messages(with_categories=true) %}
    {% if messages %}
    <div class="flash-messages">
        {% for category, message in messages %}
        <div class="flash flash-{{ category }}">
            {% if category == 'error' %}&#10060;{% else %}&#9989;{% endif %}
            {{ message }}
        </div>
        {% endfor %}
    </div>
    {% endif %}
    {% endwith %}

    <div class="card">
        <h2>Добавить контакт</h2>
        <form method="POST" action="/add" id="addForm" novalidate>
            <div class="form-row">
                <div class="form-group">
                    <label>ФИО</label>
                    <input type="text" name="full_name" id="addName"
                           placeholder="Иванов Иван Иванович"
                           maxlength="64" required
                           oninput="validateAddForm()">
                    <div class="field-hint info" id="addNameHint">3 слова, каждое 2-20 букв</div>
                </div>
                <div class="form-group">
                    <label>Телефон</label>
                    <input type="text" name="phone" id="addPhone"
                           placeholder="+7-900-123-45-67"
                           maxlength="16" required
                           oninput="formatPhone(this); validateAddForm()">
                    <div class="field-hint info" id="addPhoneHint">+X-XXX-XXX-XX-XX</div>
                </div>
                <div class="form-group">
                    <label>Заметка</label>
                    <input type="text" name="note" id="addNote"
                           placeholder="Необязательно"
                           maxlength="200"
                           oninput="validateAddForm()">
                    <div class="field-hint info" id="addNoteHint">&nbsp;</div>
                </div>
                <button type="submit" class="btn btn-primary" id="addBtn" disabled>Добавить</button>
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
                        <button class="btn btn-edit" onclick="openEdit({{ c.id }}, {{ c.full_name|tojson }}, {{ c.phone|tojson }}, {{ (c.note or '')|tojson }})">Изменить</button>
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
        <form method="POST" id="editForm" novalidate>
            <div class="form-group">
                <label>ФИО</label>
                <input type="text" name="full_name" id="editName" required
                       maxlength="64" oninput="validateEditForm()">
                <div class="field-hint info" id="editNameHint">3 слова, каждое 2-20 букв</div>
            </div>
            <div class="form-group">
                <label>Телефон</label>
                <input type="text" name="phone" id="editPhone" required
                       maxlength="16" oninput="formatPhone(this); validateEditForm()">
                <div class="field-hint info" id="editPhoneHint">+X-XXX-XXX-XX-XX</div>
            </div>
            <div class="form-group">
                <label>Заметка</label>
                <input type="text" name="note" id="editNote" maxlength="200">
            </div>
            <div class="modal-actions">
                <button type="button" class="btn btn-cancel" onclick="closeEdit()">Отмена</button>
                <button type="submit" class="btn btn-primary" id="editBtn">Сохранить</button>
            </div>
        </form>
    </div>
</div>

<script>
function validateName(value) {
    value = value.trim();
    if (!value) return { valid: false, msg: "Введите ФИО" };
    var words = value.split(/\s+/);
    if (words.length < 3) return { valid: false, msg: "Нужно 3 слова (введено " + words.length + ")" };
    if (words.length > 3) return { valid: false, msg: "Максимум 3 слова" };
    var nameRe = /^[А-Яа-яA-Za-z-]+$/;
    for (var i = 0; i < words.length; i++) {
        var w = words[i];
        if (w.length < 2) return { valid: false, msg: "'" + w + "' — минимум 2 символа" };
        if (w.length > 20) return { valid: false, msg: "'" + w + "' — максимум 20 символов" };
        if (!nameRe.test(w)) return { valid: false, msg: "'" + w + "' — только буквы и дефис" };
    }
    return { valid: true, msg: "✓" };
}

function validatePhoneValue(value) {
    value = value.trim();
    if (!value) return { valid: false, msg: "Введите телефон" };
    var phoneRe = /^\+\d-\d{3}-\d{3}-\d{2}-\d{2}$/;
    if (!phoneRe.test(value)) {
        var digits = value.replace(/\D/g, '');
        return { valid: false, msg: "+X-XXX-XXX-XX-XX (цифр: " + digits.length + "/11)" };
    }
    return { valid: true, msg: "✓" };
}

function validateNoteValue(value) {
    if (value && value.length > 200) return { valid: false, msg: "Максимум 200 символов" };
    return { valid: true, msg: "" };
}

function setHint(el, result) {
    el.className = 'field-hint ' + (result.valid ? 'ok' : 'error');
    el.textContent = result.msg;
}

function setInputState(input, valid) {
    input.classList.remove('valid', 'invalid');
    if (input.value.trim()) input.classList.add(valid ? 'valid' : 'invalid');
}

function formatPhone(input) {
    var val = input.value;
    if (input._prevLen && val.length < input._prevLen) {
        input._prevLen = val.length;
        return;
    }
    input._prevLen = val.length;
    var clean = val.replace(/[^\d+]/g, '');
    if (!clean.startsWith('+') && clean.length > 0) clean = '+' + clean;
    var formatted = '';
    var digits = clean.replace('+', '');
    if (clean.startsWith('+')) formatted = '+';
    for (var i = 0; i < digits.length && i < 11; i++) {
        if (i === 1 || i === 4 || i === 7 || i === 9) formatted += '-';
        formatted += digits[i];
    }
    if (formatted !== val) {
        input.value = formatted;
        input.setSelectionRange(formatted.length, formatted.length);
    }
}

function validateAddForm() {
    var nr = validateName(document.getElementById('addName').value);
    var pr = validatePhoneValue(document.getElementById('addPhone').value);
    var notr = validateNoteValue(document.getElementById('addNote').value);
    setHint(document.getElementById('addNameHint'), nr);
    setHint(document.getElementById('addPhoneHint'), pr);
    setInputState(document.getElementById('addName'), nr.valid);
    setInputState(document.getElementById('addPhone'), pr.valid);
    if (document.getElementById('addNote').value) {
        setHint(document.getElementById('addNoteHint'), notr);
    }
    document.getElementById('addBtn').disabled = !(nr.valid && pr.valid && notr.valid);
}

function validateEditForm() {
    var nr = validateName(document.getElementById('editName').value);
    var pr = validatePhoneValue(document.getElementById('editPhone').value);
    setHint(document.getElementById('editNameHint'), nr);
    setHint(document.getElementById('editPhoneHint'), pr);
    setInputState(document.getElementById('editName'), nr.valid);
    setInputState(document.getElementById('editPhone'), pr.valid);
    document.getElementById('editBtn').disabled = !(nr.valid && pr.valid);
}

document.getElementById('addForm').addEventListener('submit', function(e) {
    var nr = validateName(document.getElementById('addName').value);
    var pr = validatePhoneValue(document.getElementById('addPhone').value);
    if (!nr.valid || !pr.valid) { e.preventDefault(); validateAddForm(); }
});

document.getElementById('editForm').addEventListener('submit', function(e) {
    var nr = validateName(document.getElementById('editName').value);
    var pr = validatePhoneValue(document.getElementById('editPhone').value);
    if (!nr.valid || !pr.valid) { e.preventDefault(); validateEditForm(); }
});

function filterTable() {
    var query = document.getElementById('search').value.toLowerCase();
    var rows = document.querySelectorAll('#contactsTable tbody tr');
    rows.forEach(function(row) {
        row.style.display = row.textContent.toLowerCase().includes(query) ? '' : 'none';
    });
}

function openEdit(id, name, phone, note) {
    document.getElementById('editForm').action = '/edit/' + id;
    document.getElementById('editName').value = name;
    document.getElementById('editPhone').value = phone;
    document.getElementById('editNote').value = note;
    document.getElementById('editModal').classList.add('active');
    validateEditForm();
}

function closeEdit() {
    document.getElementById('editModal').classList.remove('active');
}

document.getElementById('editModal').addEventListener('click', function(e) {
    if (e.target === this) closeEdit();
});

setTimeout(function() {
    document.querySelectorAll('.flash').forEach(function(el) {
        el.style.transition = 'opacity 0.5s';
        el.style.opacity = '0';
        setTimeout(function() { el.remove(); }, 500);
    });
}, 5000);
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
    name = request.form.get('full_name', '').strip()
    phone = request.form.get('phone', '').strip()
    note = request.form.get('note', '').strip()

    is_valid_name, name_error = validate_full_name(name)
    if not is_valid_name:
        flash(f'Ошибка в ФИО: {name_error}', 'error')
        return redirect(url_for('index'))

    is_valid_phone, phone_error = validate_phone(phone)
    if not is_valid_phone:
        flash(f'Ошибка в телефоне: {phone_error}', 'error')
        return redirect(url_for('index'))

    is_valid_note, note_error = validate_note(note)
    if not is_valid_note:
        flash(f'Ошибка в заметке: {note_error}', 'error')
        return redirect(url_for('index'))

    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("INSERT INTO contacts (full_name, phone, note) VALUES (%s, %s, %s)", (name, phone, note))
        cur.close()
        conn.close()
        flash(f'Контакт "{name}" добавлен', 'success')
    except psycopg2.errors.CheckViolation:
        flash('Данные не прошли проверку ограничений БД', 'error')
    except Exception as e:
        flash(f'Ошибка: {str(e)}', 'error')

    return redirect(url_for('index'))


@app.route('/edit/<int:contact_id>', methods=['POST'])
def edit(contact_id):
    name = request.form.get('full_name', '').strip()
    phone = request.form.get('phone', '').strip()
    note = request.form.get('note', '').strip()

    is_valid_name, name_error = validate_full_name(name)
    if not is_valid_name:
        flash(f'Ошибка в ФИО: {name_error}', 'error')
        return redirect(url_for('index'))

    is_valid_phone, phone_error = validate_phone(phone)
    if not is_valid_phone:
        flash(f'Ошибка в телефоне: {phone_error}', 'error')
        return redirect(url_for('index'))

    is_valid_note, note_error = validate_note(note)
    if not is_valid_note:
        flash(f'Ошибка в заметке: {note_error}', 'error')
        return redirect(url_for('index'))

    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("UPDATE contacts SET full_name=%s, phone=%s, note=%s WHERE id=%s", (name, phone, note, contact_id))
        cur.close()
        conn.close()
        flash(f'Контакт "{name}" обновлён', 'success')
    except psycopg2.errors.CheckViolation:
        flash('Данные не прошли проверку ограничений БД', 'error')
    except Exception as e:
        flash(f'Ошибка: {str(e)}', 'error')

    return redirect(url_for('index'))


@app.route('/delete/<int:contact_id>', methods=['POST'])
def delete(contact_id):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("DELETE FROM contacts WHERE id=%s", (contact_id,))
        cur.close()
        conn.close()
        flash('Контакт удалён', 'success')
    except Exception as e:
        flash(f'Ошибка: {str(e)}', 'error')
    return redirect(url_for('index'))


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000)
