from flask import Flask, render_template, request, redirect, jsonify
import sqlite3

DB_FILE = 'dns.db'

app = Flask(__name__)

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS zones (
            domain TEXT,
            type TEXT,
            value TEXT,
            PRIMARY KEY (domain, type)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS stats (
            key TEXT PRIMARY KEY,
            value INTEGER
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS domain_stats (
            domain TEXT PRIMARY KEY,
            count INTEGER
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS type_stats (
            type TEXT PRIMARY KEY,
            count INTEGER
        )
    ''')
    conn.commit()
    conn.close()

def load_zones():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT domain, type, value FROM zones")
    rows = c.fetchall()
    zones = {}
    for domain, rtype, value in rows:
        if domain not in zones:
            zones[domain] = {}
        if rtype == 'MX':
            pref, exchange = value.split(' ', 1)
            zones[domain][rtype] = {"preference": int(pref), "exchange": exchange}
        else:
            zones[domain][rtype] = value
    conn.close()
    return zones

def save_zones(zones):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM zones")
    for domain, records in zones.items():
        for rtype, value in records.items():
            if rtype == 'MX':
                val = f"{value['preference']} {value['exchange']}"
            else:
                val = value
            c.execute("INSERT INTO zones (domain, type, value) VALUES (?, ?, ?)", (domain, rtype, val))
    conn.commit()
    conn.close()

@app.route('/')
def index():
    zones = load_zones()
    return render_template('index.html', zones=zones)

@app.route('/add', methods=['POST'])
def add_record():
    domain = request.form['domain'].strip('.')
    record_type = request.form['type']

    zones = load_zones()
    fqdn = domain + '.'

    if fqdn not in zones:
        zones[fqdn] = {}

    if record_type == 'MX':
        pref = request.form['mx_pref']
        exchange = request.form['mx_exch']
        zones[fqdn]['MX'] = {
            "preference": int(pref),
            "exchange": exchange
        }
    else:
        value = request.form['value']
        zones[fqdn][record_type] = value

    save_zones(zones)
    return redirect('/')

@app.route('/delete/<domain>/<record_type>')
def delete_record(domain, record_type):
    domain += '.'
    zones = load_zones()

    if domain in zones and record_type in zones[domain]:
        del zones[domain][record_type]
        if not zones[domain]:
            del zones[domain]
        save_zones(zones)

    return redirect('/')

@app.route('/stats')
def stats_page():
    return render_template('stats.html')

@app.route('/stats/data')
def stats_data():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Total
    c.execute("SELECT value FROM stats WHERE key = 'total'")
    total = c.fetchone()
    total = total[0] if total else 0
    # Domains
    c.execute("SELECT domain, count FROM domain_stats")
    domains = dict(c.fetchall())
    # Types
    c.execute("SELECT type, count FROM type_stats")
    types = dict(c.fetchall())
    conn.close()
    return jsonify({"total": total, "domains": domains, "types": types})

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000)