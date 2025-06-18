from flask import Flask, render_template, request, redirect, jsonify
import json
import os
from dns_server import stats

app = Flask(__name__)
ZONE_FILE = 'zones.json'
STATS_FILE = 'stats.json'

# Load zones from the JSON file
def load_zones():
    with open(ZONE_FILE) as f:
        return json.load(f)

# Save zones to the JSON file
def save_zones(zones):
    with open(ZONE_FILE, 'w') as f:
        json.dump(zones, f, indent=4)

# Index route to display the DNS records
@app.route('/')
def index():
    zones = load_zones()
    return render_template('index.html', zones=zones)

# Add a new DNS record
@app.route('/add', methods=['POST'])
def add_record():
    domain = request.form['domain'].strip('.')
    record_type = request.form['type']
    value = request.form['value']

    zones = load_zones()
    fqdn = domain + '.'

    if fqdn not in zones:
        zones[fqdn] = {}

    if record_type == 'MX':
        pref, exchange = value.split()
        zones[fqdn]['MX'] = {
            "preference": int(pref),
            "exchange": exchange
        }
    else:
        zones[fqdn][record_type] = value

    save_zones(zones)
    return redirect('/')

# Delete a DNS record
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

# Show stats page
@app.route('/stats')
def stats_page():
    return render_template('stats.html')

# Serve stats data as JSON for JavaScript
@app.route('/stats/data')
def stats_data():
    if os.path.exists(STATS_FILE):
        with open(STATS_FILE) as f:
            stats = json.load(f)
    else:
        stats = {"total": 0, "domains": {}, "types": {}}
    return jsonify(stats)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)