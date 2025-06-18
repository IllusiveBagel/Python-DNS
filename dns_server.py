import socket
import struct
import json
import time
from collections import defaultdict
import threading

# --- DNS & Zone Constants ---
ZONE_FILE = 'zones.json'
ZONES = {}
TYPE = {'A': 1, 'MX': 15, 'TXT': 16, 'AAAA': 28}
IN = 1

# --- Stats ---
stats = {
    "total": 0,
    "domains": defaultdict(int),
    "types": defaultdict(int)
}

# --- Stats File ---
STATS_FILE = 'stats.json'
def save_stats():
    with open(STATS_FILE, 'w') as f:
        json.dump({
            "total": stats["total"],
            "domains": dict(stats["domains"]),
            "types": dict(stats["types"])
        }, f)

# --- Load Zones from JSON File ---
def load_zones():
    global ZONES
    try:
        with open(ZONE_FILE) as f:
            ZONES = json.load(f)
            print(f"[INFO] Zones reloaded at {time.ctime()}")
    except Exception as e:
        print(f"[ERROR] Could not load zones: {e}")

# --- Parse DNS Labels from Request ---
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

# --- Encode Domain Name ---
def encode_name(name):
    parts = name.strip('.').split('.')
    return b''.join(bytes([len(part)]) + part.encode() for part in parts) + b'\x00'

# --- Build DNS Resource Record ---
def build_resource_record(qname, rtype, ttl, rdata_bytes):
    return b'\xc0\x0c' + struct.pack("!HHI", rtype, IN, ttl) + struct.pack("!H", len(rdata_bytes)) + rdata_bytes

# --- Build DNS Response from Query ---
def build_dns_response(query):
    transaction_id = query[:2]
    domain_name, offset = parse_labels(query, 12)
    qtype = struct.unpack("!H", query[offset:offset+2])[0]
    qtype_name = next((k for k, v in TYPE.items() if v == qtype), str(qtype))

    # Update stats
    stats["total"] += 1
    stats["domains"][domain_name] += 1
    stats["types"][qtype_name] += 1
    save_stats()

    header = transaction_id + b'\x81\x80' + b'\x00\x01'  # Standard response, 1 question
    question = query[12:offset+4]

    if domain_name in ZONES and qtype_name in ZONES[domain_name]:
        zone = ZONES[domain_name]
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

# --- DNS Server Thread Entry Point ---
def start_dns_server(host='0.0.0.0', port=5311):
    load_zones()
    last_reload = time.time()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((host, port))
    print(f"[INFO] DNS server listening on {host}:{port}")

    while True:
        if time.time() - last_reload > 5:
            load_zones()
            last_reload = time.time()

        try:
            data, addr = sock.recvfrom(512)
            response = build_dns_response(data)
            sock.sendto(response, addr)
        except Exception as e:
            print(f"[ERROR] DNS handling failed: {e}")

# --- Optional Main Entry ---
if __name__ == '__main__':
    threading.Thread(target=start_dns_server, daemon=True).start()
    input("[INFO] DNS server running in background. Press Enter to stop...\n")
