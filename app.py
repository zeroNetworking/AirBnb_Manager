"""
Airbnb Maintenance Manager - Simplified
Excel-style interface for managing maintenance checklists per room/unit.
"""
import os
import sqlite3
import json
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory, Response

app = Flask(__name__, static_folder='static')

# CORS is optional - same-origin deployment doesn't need it
try:
    from flask_cors import CORS
    CORS(app)
except ImportError:
    pass

DB_PATH = os.environ.get('DB_PATH', 'airbnb.db')


# -------------------- DATABASE --------------------

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()
    c.executescript('''
        CREATE TABLE IF NOT EXISTS rooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            locker_code TEXT DEFAULT '',
            map_link TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            sort_order INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS checklist_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id INTEGER NOT NULL,
            category TEXT DEFAULT '',
            description TEXT NOT NULL,
            status TEXT DEFAULT '',
            note TEXT DEFAULT '',
            last_checked TEXT DEFAULT '',
            sort_order INTEGER DEFAULT 0,
            FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_items_room ON checklist_items(room_id);
    ''')
    conn.commit()
    conn.close()


# -------------------- ROOMS --------------------

@app.route('/api/rooms', methods=['GET'])
def list_rooms():
    conn = get_db()
    rows = conn.execute('''
        SELECT r.*,
               COUNT(ci.id) AS total_items,
               SUM(CASE WHEN ci.status = 'OK' THEN 1 ELSE 0 END) AS ok_items,
               SUM(CASE WHEN ci.status = 'Action Required' THEN 1 ELSE 0 END) AS issues
        FROM rooms r
        LEFT JOIN checklist_items ci ON ci.room_id = r.id
        GROUP BY r.id
        ORDER BY r.sort_order, r.id
    ''').fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route('/api/rooms', methods=['POST'])
def create_room():
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'name required'}), 400
    conn = get_db()
    cur = conn.execute(
        'INSERT INTO rooms (name, locker_code, map_link, notes) VALUES (?, ?, ?, ?)',
        (name, data.get('locker_code', ''), data.get('map_link', ''), data.get('notes', ''))
    )
    conn.commit()
    rid = cur.lastrowid
    conn.close()
    return jsonify({'id': rid}), 201


@app.route('/api/rooms/<int:rid>', methods=['GET'])
def get_room(rid):
    conn = get_db()
    room = conn.execute('SELECT * FROM rooms WHERE id = ?', (rid,)).fetchone()
    if not room:
        conn.close()
        return jsonify({'error': 'not found'}), 404
    items = conn.execute(
        'SELECT * FROM checklist_items WHERE room_id = ? ORDER BY sort_order, id',
        (rid,)
    ).fetchall()
    conn.close()
    return jsonify({
        'room': dict(room),
        'items': [dict(i) for i in items]
    })


@app.route('/api/rooms/<int:rid>', methods=['PATCH'])
def update_room(rid):
    data = request.get_json() or {}
    fields = ['name', 'locker_code', 'map_link', 'notes']
    updates = {k: data[k] for k in fields if k in data}
    if not updates:
        return jsonify({'ok': True})
    conn = get_db()
    sql = 'UPDATE rooms SET ' + ', '.join(f'{k} = ?' for k in updates) + ' WHERE id = ?'
    conn.execute(sql, list(updates.values()) + [rid])
    conn.commit()
    conn.close()
    return jsonify({'ok': True})


@app.route('/api/rooms/<int:rid>', methods=['DELETE'])
def delete_room(rid):
    conn = get_db()
    conn.execute('DELETE FROM rooms WHERE id = ?', (rid,))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})


# -------------------- CHECKLIST ITEMS --------------------

@app.route('/api/rooms/<int:rid>/items', methods=['POST'])
def create_item(rid):
    data = request.get_json() or {}
    description = (data.get('description') or '').strip()
    if not description:
        return jsonify({'error': 'description required'}), 400
    conn = get_db()
    # find next sort order
    max_sort = conn.execute(
        'SELECT COALESCE(MAX(sort_order), 0) AS m FROM checklist_items WHERE room_id = ?',
        (rid,)
    ).fetchone()['m']
    cur = conn.execute('''
        INSERT INTO checklist_items (room_id, category, description, status, note, sort_order)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        rid,
        data.get('category', ''),
        description,
        data.get('status', ''),
        data.get('note', ''),
        max_sort + 1
    ))
    conn.commit()
    iid = cur.lastrowid
    conn.close()
    return jsonify({'id': iid}), 201


@app.route('/api/items/<int:iid>', methods=['PATCH'])
def update_item(iid):
    data = request.get_json() or {}
    fields = ['category', 'description', 'status', 'note']
    updates = {k: data[k] for k in fields if k in data}

    # If status changed, update last_checked timestamp
    if 'status' in updates and updates['status']:
        updates['last_checked'] = datetime.now().strftime('%Y-%m-%d %H:%M')
    elif 'status' in updates and not updates['status']:
        updates['last_checked'] = ''

    if not updates:
        return jsonify({'ok': True})
    conn = get_db()
    sql = 'UPDATE checklist_items SET ' + ', '.join(f'{k} = ?' for k in updates) + ' WHERE id = ?'
    conn.execute(sql, list(updates.values()) + [iid])
    conn.commit()
    conn.close()
    return jsonify({'ok': True})


@app.route('/api/items/<int:iid>', methods=['DELETE'])
def delete_item(iid):
    conn = get_db()
    conn.execute('DELETE FROM checklist_items WHERE id = ?', (iid,))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})


@app.route('/api/rooms/<int:rid>/items/reorder', methods=['POST'])
def reorder_items(rid):
    data = request.get_json() or {}
    order = data.get('order', [])  # [item_id, item_id, ...]
    conn = get_db()
    for idx, iid in enumerate(order):
        conn.execute(
            'UPDATE checklist_items SET sort_order = ? WHERE id = ? AND room_id = ?',
            (idx, iid, rid)
        )
    conn.commit()
    conn.close()
    return jsonify({'ok': True})


# -------------------- TEMPLATE --------------------

MASTER_TEMPLATE = [
    # (category, description)
    ("1. Ηλεκτρικά & Φωτισμός", "Όλες οι λάμπες ανάβουν (κάθε δωμάτιο, μπάνιο, κουζίνα, μπαλκόνι)"),
    ("1. Ηλεκτρικά & Φωτισμός", "Όλοι οι διακόπτες δουλεύουν"),
    ("1. Ηλεκτρικά & Φωτισμός", "Πρίζες — δοκιμή με φορτιστή σε όλες τις βασικές"),
    ("1. Ηλεκτρικά & Φωτισμός", "USB πρίζες φορτίζουν"),
    ("1. Ηλεκτρικά & Φωτισμός", "Πίνακας — πάτημα RCD test button"),
    ("1. Ηλεκτρικά & Φωτισμός", "Τηλεχειριστήρια συσκευών — αλλαγή μπαταριών"),

    ("2. Νερό & Μπάνιο", "Όλες οι βρύσες ανοίγουν, ζεστό + κρύο"),
    ("2. Νερό & Μπάνιο", "Ντους — πίεση και θερμοκρασία ΟΚ"),
    ("2. Νερό & Μπάνιο", "Καζανάκι WC — τραβάει και γεμίζει σωστά"),
    ("2. Νερό & Μπάνιο", "Αποχετεύσεις (νεροχύτες, ντους) — αδειάζουν γρήγορα"),
    ("2. Νερό & Μπάνιο", "Καθαρισμός aerator (πλεγματάκια στις βρύσες)"),
    ("2. Νερό & Μπάνιο", "Έλεγχος για διαρροές κάτω από νεροχύτες & πίσω από WC"),
    ("2. Νερό & Μπάνιο", "Boiler/Θερμοσίφωνας ζεσταίνει"),

    ("3. Κλιματισμός", "A/C — κρύο και ζεστό δουλεύει σε κάθε μονάδα"),
    ("3. Κλιματισμός", "Πλύσιμο φίλτρων"),
    ("3. Κλιματισμός", "Τηλεχειριστήρια A/C — αλλαγή μπαταριών"),
    ("3. Κλιματισμός", "Έλεγχος για στάξιμο συμπυκνωμάτων"),
    ("3. Κλιματισμός", "Εξωτερική μονάδα — ξεσκόνισμα"),

    ("4. Συσκευές & Tech", "TV ανάβει, remote δουλεύει, streaming apps OK"),
    ("4. Συσκευές & Tech", "Wi-Fi router — restart + έλεγχος ότι δίνει internet"),
    ("4. Συσκευές & Tech", "Έλεγχος Wi-Fi σήματος σε όλα τα δωμάτια"),
    ("4. Συσκευές & Tech", "Smart lock — μπαταρίες + δοκιμή κωδικού"),
    ("4. Συσκευές & Tech", "Πλυντήριο — δοκιμή σύντομου κύκλου"),
    ("4. Συσκευές & Tech", "Πλυντήριο πιάτων — δοκιμή σύντομου κύκλου"),
    ("4. Συσκευές & Tech", "Φούρνος / εστίες / μικροκυμάτων — όλα ανάβουν"),
    ("4. Συσκευές & Tech", "Ψυγείο — κρυώνει σωστά, καθαρό λάστιχο πόρτας"),

    ("5. Πόρτες, Έπιπλα & Βίδες", "Πόρτα εισόδου — κλείνει, κλειδώνει, λαδωμένη κλειδαριά"),
    ("5. Πόρτες, Έπιπλα & Βίδες", "Εσωτερικές πόρτες — ανοίγουν χωρίς τρίξιμο, λάδωμα μεντεσέδων"),
    ("5. Πόρτες, Έπιπλα & Βίδες", "Μπαλκονόπορτες — γλιστράνε σωστά, κλειδώνουν"),
    ("5. Πόρτες, Έπιπλα & Βίδες", "Παράθυρα — ανοίγουν/κλείνουν, μηχανισμοί OK"),
    ("5. Πόρτες, Έπιπλα & Βίδες", "Ρολά / παντζούρια — ανεβαίνουν/κατεβαίνουν"),
    ("5. Πόρτες, Έπιπλα & Βίδες", "Σύσφιξη βιδών — καρέκλες (κάθε μία)"),
    ("5. Πόρτες, Έπιπλα & Βίδες", "Σύσφιξη βιδών — τραπέζια"),
    ("5. Πόρτες, Έπιπλα & Βίδες", "Σύσφιξη βιδών — ντουλάπια κουζίνας/μπάνιου (πόμολα + μεντεσέδες)"),
    ("5. Πόρτες, Έπιπλα & Βίδες", "Σύσφιξη βιδών — κρεβάτια"),
    ("5. Πόρτες, Έπιπλα & Βίδες", "Συρτάρια — ανοίγουν/κλείνουν σωστά"),

    ("6. Ασφάλεια — Quick Check", "Ανιχνευτής καπνού — πάτημα test button"),
    ("6. Ασφάλεια — Quick Check", "Πυροσβεστήρας — μανόμετρο στο πράσινο"),
    ("6. Ασφάλεια — Quick Check", "First aid kit — γεμάτο, χωρίς ληγμένα"),
    ("6. Ασφάλεια — Quick Check", "Έλεγχος για εμφανείς διαρροές νερού (πατώματα, ταβάνι)"),
    ("6. Ασφάλεια — Quick Check", "Έλεγχος μούχλας σε σιλικόνες μπάνιου"),
]


@app.route('/api/rooms/<int:rid>/import-template', methods=['POST'])
def import_template(rid):
    """Clear existing checklist items and insert master template."""
    conn = get_db()
    # Check room exists
    if not conn.execute('SELECT 1 FROM rooms WHERE id = ?', (rid,)).fetchone():
        conn.close()
        return jsonify({'error': 'room not found'}), 404

    # Wipe existing items for this room
    conn.execute('DELETE FROM checklist_items WHERE room_id = ?', (rid,))

    for idx, (cat, desc) in enumerate(MASTER_TEMPLATE):
        conn.execute('''
            INSERT INTO checklist_items (room_id, category, description, sort_order)
            VALUES (?, ?, ?, ?)
        ''', (rid, cat, desc, idx + 1))

    conn.commit()
    conn.close()
    return jsonify({'ok': True, 'count': len(MASTER_TEMPLATE)})


# -------------------- IMPORT / EXPORT --------------------

@app.route('/api/export', methods=['GET'])
def export_all():
    conn = get_db()
    rooms = conn.execute('SELECT * FROM rooms ORDER BY sort_order, id').fetchall()
    payload = {
        'exported_at': datetime.now().isoformat(),
        'version': 2,
        'rooms': []
    }
    for r in rooms:
        items = conn.execute(
            'SELECT * FROM checklist_items WHERE room_id = ? ORDER BY sort_order, id',
            (r['id'],)
        ).fetchall()
        payload['rooms'].append({
            **dict(r),
            'items': [dict(i) for i in items]
        })
    conn.close()
    return Response(
        json.dumps(payload, ensure_ascii=False, indent=2),
        mimetype='application/json',
        headers={'Content-Disposition': f'attachment; filename=airbnb-backup-{datetime.now().strftime("%Y%m%d-%H%M")}.json'}
    )


@app.route('/api/import', methods=['POST'])
def import_data():
    data = request.get_json() or {}
    rooms = data.get('rooms', [])
    if not isinstance(rooms, list):
        return jsonify({'error': 'invalid format'}), 400

    mode = data.get('mode', 'replace')  # 'replace' or 'append'

    conn = get_db()
    if mode == 'replace':
        conn.execute('DELETE FROM checklist_items')
        conn.execute('DELETE FROM rooms')

    imported = 0
    for r in rooms:
        cur = conn.execute('''
            INSERT INTO rooms (name, locker_code, map_link, notes, sort_order)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            r.get('name', 'Untitled'),
            r.get('locker_code', ''),
            r.get('map_link', ''),
            r.get('notes', ''),
            r.get('sort_order', 0)
        ))
        new_rid = cur.lastrowid
        for it in r.get('items', []):
            conn.execute('''
                INSERT INTO checklist_items
                (room_id, category, description, status, note, last_checked, sort_order)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                new_rid,
                it.get('category', ''),
                it.get('description', ''),
                it.get('status', ''),
                it.get('note', ''),
                it.get('last_checked', ''),
                it.get('sort_order', 0)
            ))
        imported += 1

    conn.commit()
    conn.close()
    return jsonify({'ok': True, 'imported': imported})


# -------------------- STATIC --------------------

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')


@app.route('/<path:path>')
def static_files(path):
    return send_from_directory('static', path)


# -------------------- MAIN --------------------

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5050, debug=False)
else:
    init_db()
