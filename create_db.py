# Run this once to create the DB schema
import sqlite3

conn = sqlite3.connect('dns.db')
c = conn.cursor()

# Zones table
c.execute('''
CREATE TABLE IF NOT EXISTS zones (
    domain TEXT,
    type TEXT,
    value TEXT,
    PRIMARY KEY (domain, type)
)
''')

# Stats table
c.execute('''
CREATE TABLE IF NOT EXISTS stats (
    key TEXT PRIMARY KEY,
    value INTEGER
)
''')

# Domain stats table
c.execute('''
CREATE TABLE IF NOT EXISTS domain_stats (
    domain TEXT PRIMARY KEY,
    count INTEGER
)
''')

# Type stats table
c.execute('''
CREATE TABLE IF NOT EXISTS type_stats (
    type TEXT PRIMARY KEY,
    count INTEGER
)
''')

conn.commit()
conn.close()