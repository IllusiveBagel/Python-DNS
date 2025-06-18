import socket
import struct
import json
import time

ZONE_FILE = 'zones.json'
ZONES = {}

TYPE = {'A': 1, 'MX': 15, 'TXT': 16, 'AAAA': 28}
IN = 1

def load_zones():
    global ZONES
    try:
        with open(ZONE_FILE) as f:
            ZONES = json.load(f)
            print(f"[INFO] Zones reloaded at {time.ctime()}")
    except Exception as e:
        print(f"[ERROR] Could not load zones: {e}")

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
    qtype_name = next((k for k, v in TYPE.items() if v == qtype), None)

    header = transaction_id + b'\x81\x80' + b'\x00\x01'  # standard response, 1 question
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

    # No match found — NXDOMAIN response
    flags = b'\x81\x83'  # Standard query response, recursion not available, name error
    return transaction_id + flags + b'\x00\x01' + b'\x00\x00\x00\x00' + query[12:]

def main():
    load_zones()
    last_reload = time.time()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('0.0.0.0', 53))
    print("[INFO] DNS server (isolated) listening on UDP port 53...")

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

if __name__ == '__main__':
    main()