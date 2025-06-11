from flask import Flask, render_template_string, request, redirect, jsonify
import sqlite3
import os
import time

app = Flask(__name__)

# --- Database Setup ---
DB_FILE = 'notes_new.db'

def init_db():
    # Check if we need to migrate the database
    needs_migration = False
    if os.path.exists(DB_FILE):
        try:
            with sqlite3.connect(DB_FILE) as conn:
                c = conn.cursor()
                try:
                    c.execute("SELECT category FROM notes LIMIT 1")
                except sqlite3.OperationalError:
                    needs_migration = True
        except sqlite3.OperationalError:
            # If we can't connect to the database, we'll recreate it
            needs_migration = True
    
    if needs_migration:
        # Try to remove the old database file if it exists
        try:
            if os.path.exists(DB_FILE):
                os.remove(DB_FILE)
        except PermissionError:
            print("Warning: Could not remove old database file. Please make sure no other process is using it.")
            return
    
    # Create new database with updated schema
    try:
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor()
            c.execute('''CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'Uncategorized',
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )''')
    except sqlite3.OperationalError as e:
        print(f"Error creating database: {e}")
        return

# --- Routes ---
@app.route('/')
def index():
    category = request.args.get('category', 'all')
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        if category == 'all':
            c.execute("SELECT id, title, content, category, timestamp FROM notes ORDER BY timestamp DESC")
        else:
            c.execute("SELECT id, title, content, category, timestamp FROM notes WHERE category = ? ORDER BY timestamp DESC", (category,))
        notes = c.fetchall()
        
        # Get unique categories for the tabs and dropdown
        c.execute("SELECT DISTINCT category FROM notes ORDER BY category")
        categories = [row[0] for row in c.fetchall()]
        
    return render_template_string(TEMPLATE, notes=notes, categories=categories, current_category=category)

@app.route('/add', methods=['POST'])
def add_note():
    title = request.form.get('title')
    content = request.form.get('content')
    category = request.form.get('category')
    new_category = request.form.get('new_category')
    
    # Use new category if provided, otherwise use selected category
    final_category = new_category if new_category else category
    
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("INSERT INTO notes (title, content, category) VALUES (?, ?, ?)", 
                 (title, content, final_category))
    return redirect('/')

@app.route('/edit/<int:note_id>', methods=['POST'])
def edit_note(note_id):
    title = request.form.get('title')
    content = request.form.get('content')
    category = request.form.get('category')
    new_category = request.form.get('new_category')
    
    # Use new category if provided, otherwise use selected category
    final_category = new_category if new_category else category
    
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("UPDATE notes SET title = ?, content = ?, category = ? WHERE id = ?",
                 (title, content, final_category, note_id))
    return redirect('/')

@app.route('/delete/<int:note_id>', methods=['POST'])
def delete_note(note_id):
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM notes WHERE id = ?", (note_id,))
    return redirect('/')

# --- HTML Template ---
TEMPLATE = '''
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Zápisník</title>
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
  </style>
</head>
<body>
  <h1>Osobní zápisník</h1>
  
  <div class="tabs">
    <a href="/" class="tab {% if current_category == 'all' %}active{% endif %}">Vše</a>
    {% for cat in categories %}
    <a href="/?category={{ cat }}" class="tab {% if current_category == cat %}active{% endif %}">{{ cat }}</a>
    {% endfor %}
  </div>

  <form method="POST" action="/add" id="note-form">
    <input name="title" placeholder="Název poznámky" required>
    <div class="category-input">
      <select name="category" id="category-select">
        <option value="">Vyberte kategorii nebo napište novou</option>
        {% for cat in categories %}
        <option value="{{ cat }}">{{ cat }}</option>
        {% endfor %}
      </select>
      <input type="text" id="new-category" name="new_category" placeholder="Nová kategorie">
    </div>
    <textarea name="content" rows="4" placeholder="Obsah poznámky" required></textarea>
    <button type="submit">Přidat poznámku</button>
  </form>

  {% for note in notes %}
    <div class="note" id="note-{{ note[0] }}">
      <form method="POST" action="/delete/{{ note[0] }}" style="display: inline;">
        <button type="submit" class="delete-btn" onclick="return confirm('Opravdu chcete smazat tuto poznámku?')">Smazat</button>
      </form>
      <button class="edit-btn" onclick="openEditModal({{ note[0] }}, '{{ note[1] }}', '{{ note[2] }}', '{{ note[3] }}')">Upravit</button>
      <div class="category">{{ note[3] }}</div>
      <h3>{{ note[1] }}</h3>
      <p>{{ note[2] }}</p>
      <div class="timestamp">{{ note[4] }}</div>
    </div>
  {% endfor %}

  <!-- Edit Modal -->
  <div id="editModal" class="modal">
    <div class="modal-content">
      <span class="close" onclick="closeEditModal()">&times;</span>
      <h2>Upravit poznámku</h2>
      <form method="POST" id="edit-form">
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
        <textarea name="content" id="edit-content" rows="4" placeholder="Obsah poznámky" required></textarea>
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
        alert('Vyberte nebo zadejte kategorii');
      }
    });

    // Edit modal functionality
    const modal = document.getElementById('editModal');
    const editForm = document.getElementById('edit-form');
    const editCategorySelect = document.getElementById('edit-category-select');
    const editNewCategory = document.getElementById('edit-new-category');

    function openEditModal(id, title, content, category) {
      document.getElementById('edit-title').value = title;
      document.getElementById('edit-content').value = content;
      editCategorySelect.value = category;
      editNewCategory.value = '';
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
        alert('Vyberte nebo zadejte kategorii');
      }
    });
  </script>
</body>
</html>
'''

# --- Main ---
if __name__ == '__main__':
    init_db()
    app.run(debug=True)