# Airbnb Maintenance Manager

Excel-style mobile-first interface for managing maintenance checklists per room/property. Built for personal use by a maintenance technician handling multiple Airbnb properties.

## What it does

- **Δωμάτια/Properties**: flat λίστα, κάθε ένα με όνομα, locker code, Google Maps link, σημειώσεις
- **Custom Checklists**: ανά δωμάτιο φτιάχνεις τα δικά σου σημεία ελέγχου ή φέρνεις το standard template (41 items)
- **Mobile-first**: card layout στο κινητό με collapsible κατηγορίες, table layout στο desktop
- **Inline editing**: όλα τα κελιά editable, auto-save χωρίς save buttons
- **Status tracking**: OK / Action Required / Replaced / Scheduled / N/A με χρωματική κωδικοποίηση
- **Auto-timestamp**: όταν αλλάζεις status, καταγράφεται αυτόματα η ημερομηνία ελέγχου
- **JSON Export/Import**: πλήρες backup σε JSON, με δυνατότητα replace ή append

## Master Template (41 σημεία)

Functional check list προσανατολισμένο σε γρήγορο maintenance:

1. **Ηλεκτρικά & Φωτισμός** (6) — λάμπες, διακόπτες, πρίζες, USB, RCD, μπαταρίες remotes
2. **Νερό & Μπάνιο** (7) — βρύσες, ντους, WC, αποχετεύσεις, aerators, διαρροές, boiler
3. **Κλιματισμός** (5) — λειτουργία, φίλτρα, μπαταρίες remote, στάξιμο, εξωτερική μονάδα
4. **Συσκευές & Tech** (8) — TV, Wi-Fi, smart lock, πλυντήρια, φούρνος, ψυγείο
5. **Πόρτες, Έπιπλα & Βίδες** (10) — πόρτες, παράθυρα, ρολά, σύσφιξη βιδών παντού
6. **Ασφάλεια — Quick Check** (5) — ανιχνευτές, πυροσβεστήρας, first aid, διαρροές, μούχλα

**Note:** Πατώντας ξανά "+ Master Template" σε δωμάτιο που έχει ήδη checklist, **διαγράφονται όλα τα υπάρχοντα items** και ξαναμπαίνει καθαρό template.

## Running locally

```bash
pip install -r requirements.txt
python app.py
```

Open `http://localhost:5050`

## Docker

```bash
docker-compose up -d --build
```

Open `http://<server-ip>:5050`

Database persists στο `./database/airbnb.db`.

## Backup & Restore

- **Export**: πάτα **Export** στο header — κατεβαίνει JSON
- **Import**: πάτα **Import**, διάλεξε αρχείο, μετά διάλεξε replace ή append

## Schema

Δύο tables only:
- `rooms` (id, name, locker_code, map_link, notes, sort_order)
- `checklist_items` (id, room_id, category, description, status, note, last_checked, sort_order)

## Tech stack

- **Backend**: Python, Flask, SQLite, Gunicorn
- **Frontend**: Vanilla JS, single HTML file, no frameworks
- **Deployment**: Docker, Docker Compose
