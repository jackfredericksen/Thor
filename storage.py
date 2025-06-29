# storage.py

import sqlite3
import threading


class Storage:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.lock = threading.Lock()
        self._init_tables()

    def _init_tables(self):
        with self.conn:
            self.conn.execute(
                """CREATE TABLE IF NOT EXISTS tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                address TEXT UNIQUE,
                data TEXT,
                source TEXT,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )"""
            )
            self.conn.execute(
                """CREATE TABLE IF NOT EXISTS smart_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wallet TEXT,
                token_address TEXT,
                value_usd REAL,
                tx_hash TEXT,
                tags TEXT,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )"""
            )
            self.conn.execute(
                """CREATE TABLE IF NOT EXISTS smart_accumulation (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token_address TEXT,
                wallet TEXT,
                tags TEXT,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )"""
            )
            self.conn.execute(
                """CREATE TABLE IF NOT EXISTS order_status (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT,
                status TEXT,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )"""
            )

    def save_token_data(self, token_address, data, source):
        with self.lock, self.conn:
            self.conn.execute(
                "INSERT OR REPLACE INTO tokens (address, data, source) VALUES (?, ?, ?)",
                (token_address, data, source),
            )

    def save_smart_trade(self, wallet, token, value, tx_hash, tags):
        with self.lock, self.conn:
            self.conn.execute(
                "INSERT INTO smart_trades (wallet, token_address, value_usd, tx_hash, tags) VALUES (?, ?, ?, ?, ?)",
                (wallet, token, value, tx_hash, ",".join(tags)),
            )

    def flag_token_smart_accumulation(self, token, wallet, tags):
        with self.lock, self.conn:
            self.conn.execute(
                "INSERT INTO smart_accumulation (token_address, wallet, tags) VALUES (?, ?, ?)",
                (token, wallet, ",".join(tags)),
            )

    def save_order_status(self, order_id, status):
        with self.lock, self.conn:
            self.conn.execute(
                "INSERT INTO order_status (order_id, status) VALUES (?, ?)",
                (order_id, status),
            )
