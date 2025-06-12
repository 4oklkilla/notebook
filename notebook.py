from flask import Flask, render_template_string, request, redirect, jsonify, send_from_directory
import sqlite3
import os
import time
import sqlite3
from werkzeug.utils import secure_filename

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'txt'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    # Vrací True, pokud má soubor povolenou příponu
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- Nastavení databáze ---
DB_FILE = 'notes_new.db'

# Inicializace databáze a případná migrace schématu

def init_db():
    # Kontrola, zda je potřeba migrace databáze
    needs_migration = False
    if os.path.exists(DB_FILE):
        try:
            with sqlite3.connect(DB_FILE) as conn:
                c = conn.cursor()
                try:
                    c.execute("SELECT status FROM notes LIMIT 1")
                except sqlite3.OperationalError:
                    needs_migration = True
        except sqlite3.OperationalError:
            # Pokud se nelze připojit k databázi, bude znovu vytvořena
            needs_migration = True
    
    if needs_migration:
        # Pokus o odstranění starého souboru databáze, pokud existuje
        try:
            if os.path.exists(DB_FILE):
                os.remove(DB_FILE)
        except PermissionError:
            print("Warning: Nelze odstranit starý soubor databáze. Ujistěte se, že jej nepoužívá jiný proces.")
            return
    
    # Vytvoření nové databáze s aktualizovaným schématem
    try:
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor()
            c.execute('''CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'Uncategorized',
                status TEXT NOT NULL DEFAULT 'Not started',
                attachment TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )''')
    except sqlite3.OperationalError as e:
        print(f"Chyba při vytváření databáze: {e}")
        return

# --- Routy ---
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    # Vrací soubor z upload složky
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/')
def index():
    category = request.args.get('category', 'all')
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        query = "SELECT id, title, content, category, status, attachment, timestamp FROM notes"
        params = []
        if category != 'all':
            query += " WHERE category = ?"
            params.append(category)
        query += " ORDER BY timestamp DESC"
        c.execute(query, tuple(params))
        notes = c.fetchall()
        
        # Získání unikátních kategorií pro záložky a výběr
        c.execute("SELECT DISTINCT category FROM notes ORDER BY category")
        categories = [row[0] for row in c.fetchall()]
        
    return render_template_string(TEMPLATE, notes=notes, categories=categories, current_category=category)

@app.route('/add', methods=['POST'])
def add_note():
    title = request.form.get('title')
    content = request.form.get('content', '')
    category = request.form.get('category')
    new_category = request.form.get('new_category')
    file = request.files.get('attachment')
    attachment_filename = None
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        attachment_filename = filename
    # Použij novou kategorii, pokud je zadána, jinak vybranou kategorii
    final_category = new_category if new_category else category
    if not title or (not category and not new_category):
        return redirect('/')
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("INSERT INTO notes (title, content, category, status, attachment) VALUES (?, ?, ?, ?, ?)", 
                 (title, content, final_category, 'Not started', attachment_filename))
    return redirect('/')

@app.route('/edit/<int:note_id>', methods=['POST'])
def edit_note(note_id):
    title = request.form.get('title')
    content = request.form.get('content', '')
    category = request.form.get('category')
    new_category = request.form.get('new_category')
    file = request.files.get('attachment')
    attachment_filename = None
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        attachment_filename = filename
    # Použij novou kategorii, pokud je zadána, jinak vybranou kategorii
    final_category = new_category if new_category else category
    if not title or (not category and not new_category):
        return redirect('/')
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        if attachment_filename:
            c.execute("UPDATE notes SET title = ?, content = ?, category = ?, status = ?, attachment = ? WHERE id = ?",
                     (title, content, final_category, 'Not started', attachment_filename, note_id))
        else:
            c.execute("UPDATE notes SET title = ?, content = ?, category = ?, status = ? WHERE id = ?",
                     (title, content, final_category, 'Not started', note_id))
    return redirect('/')

@app.route('/delete/<int:note_id>', methods=['POST'])
def delete_note(note_id):
    # Smaže poznámku podle ID
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM notes WHERE id = ?", (note_id,))
    return redirect('/')

@app.route('/update_status/<int:note_id>', methods=['POST'])
def update_status(note_id):
    data = request.get_json()
    # Nastaví status na 'Dokončeno' pokud je checkbox zaškrtnutý, jinak na 'Nezačato'
    new_status = 'Dokončeno' if data.get('completed') else 'Nezačato'
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("UPDATE notes SET status = ? WHERE id = ?", (new_status, note_id))
    return jsonify({'success': True, 'status': new_status})

# --- HTML šablona ---
TEMPLATE = '''
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Notebook</title>
  <style>
    body { font-family: sans-serif; padding: 2rem; max-width: 700px; margin: auto; }
    form { margin-bottom: 2rem; }
    textarea, input, select { width: 100%; padding: 0.5rem; margin: 0.5rem 0; }
    .note { border: 1px solid #ccc; padding: 1rem; margin-bottom: 1rem; border-radius: 10px; position: relative; }
    .timestamp { color: #888; font-size: 0.8em; }
    .category { color: #666; font-size: 0.9em; margin-bottom: 0.5rem; }
    .tabs { display: flex; gap: 1rem; margin-bottom: 2rem; flex-wrap: wrap; }
    .tab { 
        padding: 0.5rem 1rem; 
        border: 1px solid #ccc; 
        border-radius: 5px; 
        cursor: pointer; 
        text-decoration: none;
        color: #333;
    }
    .tab.active { 
        background-color: #007bff; 
        color: white; 
        border-color: #007bff; 
    }
    .delete-btn, .edit-btn {
        position: absolute;
        top: 1rem;
        padding: 0.25rem 0.5rem;
        border-radius: 3px;
        cursor: pointer;
        border: none;
        color: white;
    }
    .delete-btn {
        right: 1rem;
        background-color: #dc3545;
    }
    .edit-btn {
        right: 5rem;
        background-color: #28a745;
    }
    .delete-btn:hover { background-color: #c82333; }
    .edit-btn:hover { background-color: #218838; }
    .category-input {
        display: flex;
        gap: 0.5rem;
    }
    .category-input select {
        flex: 1;
    }
    .category-input input {
        flex: 1;
    }
    .modal {
        display: none;
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background-color: rgba(0,0,0,0.5);
    }
    .modal-content {
        background-color: white;
        margin: 10% auto;
        padding: 2rem;
        border-radius: 10px;
        width: 80%;
        max-width: 600px;
    }
    .close {
        float: right;
        cursor: pointer;
        font-size: 1.5rem;
    }
    .status {
        color: #444;
        font-size: 0.9em;
        margin-bottom: 0.5rem;
        font-style: italic;
    }
    .status-checkbox {
        margin-right: 0.5em;
        transform: scale(1.3);
        vertical-align: middle;
    }
    .attachment {
        margin-top: 0.5rem;
    }
    .attachment img {
        max-width: 200px;
        max-height: 200px;
        display: block;
        margin-top: 0.5rem;
    }
  </style>
</head>
<body>
  <h1>Personal Notebook</h1>
  
  <div class="tabs">
    <a href="/" class="tab {% if current_category == 'all' %}active{% endif %}">All</a>
    {% for cat in categories %}
    <a href="/?category={{ cat }}" class="tab {% if current_category == cat %}active{% endif %}">{{ cat }}</a>
    {% endfor %}
  </div>

  <form method="POST" action="/add" id="note-form" enctype="multipart/form-data">
    <input name="title" placeholder="Note title" required>
    <div class="category-input">
      <select name="category" id="category-select">
        <option value="">Select a category or type a new one</option>
        {% for cat in categories %}
        <option value="{{ cat }}">{{ cat }}</option>
        {% endfor %}
      </select>
      <input type="text" id="new-category" name="new_category" placeholder="New category">
    </div>
    <input type="file" name="attachment" accept="image/*,.pdf,.txt">
    <textarea name="content" rows="4" placeholder="Note content"></textarea>
    <button type="submit">Add note</button>
  </form>

  {% for note in notes %}
    <div class="note" id="note-{{ note[0] }}">
      <form method="POST" action="/delete/{{ note[0] }}" style="display: inline;">
        <button type="submit" class="delete-btn" onclick="return confirm('Are you sure you want to delete this note?')">Delete</button>
      </form>
      <button class="edit-btn" onclick="openEditModal({{ note[0] }}, '{{ note[1] }}', '{{ note[2] }}', '{{ note[3] }}', '{{ note[4] }}', '{{ note[5] }}')">Edit</button>
      <div class="category">{{ note[3] }}</div>
      <div class="status">
        <input type="checkbox" class="status-checkbox" data-note-id="{{ note[0] }}" {% if note[4] == 'Dokončeno' %}checked{% endif %}>
      </div>
      {% if note[5] %}
      <div class="attachment">
        {% if note[5].endswith('.png') or note[5].endswith('.jpg') or note[5].endswith('.jpeg') or note[5].endswith('.gif') %}
          <img src="/uploads/{{ note[5] }}" alt="Attachment">
        {% else %}
          <a href="/uploads/{{ note[5] }}" target="_blank">Attachment</a>
        {% endif %}
      </div>
      {% endif %}
      <h3>{{ note[1] }}</h3>
      {% if note[2] %}<p>{{ note[2] }}</p>{% endif %}
      <div class="timestamp">{{ note[6] }}</div>
    </div>
  {% endfor %}

  <!-- Edit Modal -->
  <div id="editModal" class="modal">
    <div class="modal-content">
      <span class="close" onclick="closeEditModal()">&times;</span>
      <h2>Upravit poznámku</h2>
      <form method="POST" id="edit-form" enctype="multipart/form-data">
        <input name="title" id="edit-title" placeholder="Název poznámky" required>
        <div class="category-input">
          <select name="category" id="edit-category-select">
            <option value="">Vyberte kategorii nebo napište novou</option>
            {% for cat in categories %}
            <option value="{{ cat }}">{{ cat }}</option>
            {% endfor %}
          </select>
          <input type="text" id="edit-new-category" name="new_category" placeholder="Nová kategorie">
        </div>
        <input type="file" name="attachment" accept="image/*,.pdf,.txt">
        <textarea name="content" id="edit-content" rows="4" placeholder="Obsah poznámky"></textarea>
        <button type="submit">Uložit změny</button>
      </form>
    </div>
  </div>

  <script>
    // Handle category selection and new category input
    const categorySelect = document.getElementById('category-select');
    const newCategoryInput = document.getElementById('new-category');
    const noteForm = document.getElementById('note-form');
    
    categorySelect.addEventListener('change', function() {
      if (this.value) {
        newCategoryInput.value = '';
      }
    });
    
    newCategoryInput.addEventListener('input', function() {
      if (this.value) {
        categorySelect.value = '';
      }
    });
    
    // Before form submission, ensure we have a category
    noteForm.addEventListener('submit', function(e) {
      if (!categorySelect.value && !newCategoryInput.value) {
        e.preventDefault();
        alert('Select or enter a category');
      }
    });

    // Edit modal functionality
    const modal = document.getElementById('editModal');
    const editForm = document.getElementById('edit-form');
    const editCategorySelect = document.getElementById('edit-category-select');
    const editNewCategory = document.getElementById('edit-new-category');

    function openEditModal(id, title, content, category, status, attachment) {
      document.getElementById('edit-title').value = title;
      document.getElementById('edit-content').value = content;
      editCategorySelect.value = category;
      editNewCategory.value = '';
      document.getElementById('edit-status-select').value = status;
      editForm.action = '/edit/' + id;
      modal.style.display = 'block';
    }

    function closeEditModal() {
      modal.style.display = 'none';
    }

    // Close modal when clicking outside
    window.onclick = function(event) {
      if (event.target == modal) {
        closeEditModal();
      }
    }

    // Handle category selection in edit modal
    editCategorySelect.addEventListener('change', function() {
      if (this.value) {
        editNewCategory.value = '';
      }
    });
    
    editNewCategory.addEventListener('input', function() {
      if (this.value) {
        editCategorySelect.value = '';
      }
    });

    // Validate edit form
    editForm.addEventListener('submit', function(e) {
      if (!editCategorySelect.value && !editNewCategory.value) {
        e.preventDefault();
        alert('Select or enter a category');
      }
    });

    // Status checkbox AJAX
    document.querySelectorAll('.status-checkbox').forEach(function(checkbox) {
      checkbox.addEventListener('change', function() {
        const noteId = this.getAttribute('data-note-id');
        const completed = this.checked;
        fetch('/update_status/' + noteId, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({ completed: completed })
        })
        .then(response => response.json())
        .then(data => {
          // No label to update
        });
      });
    });
  </script>
</body>
</html>
'''

# --- Hlavní ---
if __name__ == '__main__':
    # Inicializace databáze při spuštění aplikace
    init_db()
    app.run(debug=True)