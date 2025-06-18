import socket
import struct
import time
import threading
import sqlite3

DB_FILE = 'dns.db'
TYPE = {'A': 1, 'MX': 15, 'TXT': 16, 'AAAA': 28}
IN = 1

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

def save_stats(domain_name, qtype_name):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Total
    c.execute("INSERT OR IGNORE INTO stats (key, value) VALUES ('total', 0)")
    c.execute("UPDATE stats SET value = value + 1 WHERE key = 'total'")
    # Domain
    c.execute("INSERT OR IGNORE INTO domain_stats (domain, count) VALUES (?, 0)", (domain_name,))
    c.execute("UPDATE domain_stats SET count = count + 1 WHERE domain = ?", (domain_name,))
    # Type
    c.execute("INSERT OR IGNORE INTO type_stats (type, count) VALUES (?, 0)", (qtype_name,))
    c.execute("UPDATE type_stats SET count = count + 1 WHERE type = ?", (qtype_name,))
    conn.commit()
    conn.close()

def parse_labels(data, offset):
    labels = []
    while True:
        length = data[offset]
        if length == 0:
            offset += 1
            break
        labels.append(data[offset + 1:offset + 1 + length].decode())
        offset += 1 + length
    return '.'.join(labels) + '.', offset

def encode_name(name):
    parts = name.strip('.').split('.')
    return b''.join(bytes([len(part)]) + part.encode() for part in parts) + b'\x00'

def build_resource_record(qname, rtype, ttl, rdata_bytes):
    return b'\xc0\x0c' + struct.pack("!HHI", rtype, IN, ttl) + struct.pack("!H", len(rdata_bytes)) + rdata_bytes

def build_dns_response(query):
    transaction_id = query[:2]
    domain_name, offset = parse_labels(query, 12)
    qtype = struct.unpack("!H", query[offset:offset+2])[0]
    qtype_name = next((k for k, v in TYPE.items() if v == qtype), str(qtype))

    # Update stats in DB
    save_stats(domain_name, qtype_name)

    header = transaction_id + b'\x81\x80' + b'\x00\x01'  # Standard response, 1 question
    question = query[12:offset+4]

    zones = load_zones()
    if domain_name in zones and qtype_name in zones[domain_name]:
        zone = zones[domain_name]
        answer = b''

        if qtype_name == 'A':
            ip = zone['A']
            ip_bytes = bytes(map(int, ip.split('.')))
            answer = build_resource_record(domain_name, TYPE['A'], 60, ip_bytes)

        elif qtype_name == 'AAAA':
            parts = zone['AAAA'].split(':')
            full = []
            for part in parts:
                if part == '':
                    full += ['0000'] * (8 - len([p for p in parts if p != '']))
                else:
                    full.append(part.zfill(4))
            ipv6_bytes = b''.join(struct.pack("!H", int(part, 16)) for part in full[:8])
            answer = build_resource_record(domain_name, TYPE['AAAA'], 60, ipv6_bytes)

        elif qtype_name == 'MX':
            pref = zone['MX']['preference']
            exchange = encode_name(zone['MX']['exchange'])
            mx_bytes = struct.pack("!H", pref) + exchange
            answer = build_resource_record(domain_name, TYPE['MX'], 60, mx_bytes)

        elif qtype_name == 'TXT':
            txt = zone['TXT']
            txt_bytes = bytes([len(txt)]) + txt.encode()
            answer = build_resource_record(domain_name, TYPE['TXT'], 60, txt_bytes)

        ancount = b'\x00\x01'
        header += ancount + b'\x00\x00\x00\x00'
        return header + question + answer

    # NXDOMAIN (no match)
    flags = b'\x81\x83'  # Standard response, name error
    return transaction_id + flags + b'\x00\x01' + b'\x00\x00\x00\x00' + query[12:]

def start_dns_server(host='0.0.0.0', port=5311):
    init_db()
    last_reload = time.time()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((host, port))
    print(f"[INFO] DNS server listening on {host}:{port}")

    while True:
        try:
            data, addr = sock.recvfrom(512)
            response = build_dns_response(data)
            sock.sendto(response, addr)
        except Exception as e:
            print(f"[ERROR] DNS handling failed: {e}")

if __name__ == '__main__':
    threading.Thread(target=start_dns_server, daemon=True).start()
    input("[INFO] DNS server running in background. Press Enter to stop...\n")