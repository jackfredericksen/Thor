# storage.py

import json
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
            self.conn.execute(
                """CREATE TABLE IF NOT EXISTS open_positions (
                token_address TEXT PRIMARY KEY,
                symbol TEXT,
                quantity REAL,
                entry_price REAL,
                current_price REAL DEFAULT 0.0,
                peak_price REAL DEFAULT 0.0,
                partial_sold INTEGER DEFAULT 0,
                entry_tx TEXT DEFAULT '',
                entry_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                cost_usd REAL DEFAULT 0.0
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

    def save_position(self, token_address, symbol, quantity, entry_price,
                      peak_price=0.0, partial_sold=0, entry_tx="", cost_usd=0.0):
        """Persist an open position to survive restarts."""
        with self.lock, self.conn:
            self.conn.execute(
                """INSERT OR REPLACE INTO open_positions
                   (token_address, symbol, quantity, entry_price, current_price,
                    peak_price, partial_sold, entry_tx, cost_usd)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (token_address, symbol, quantity, entry_price, entry_price,
                 peak_price or entry_price, partial_sold, entry_tx, cost_usd),
            )

    def update_position(self, token_address, current_price=None, peak_price=None, partial_sold=None, quantity=None):
        """Update mutable fields of an existing position."""
        fields, values = [], []
        if current_price is not None:
            fields.append("current_price = ?"); values.append(current_price)
        if peak_price is not None:
            fields.append("peak_price = ?"); values.append(peak_price)
        if partial_sold is not None:
            fields.append("partial_sold = ?"); values.append(partial_sold)
        if quantity is not None:
            fields.append("quantity = ?"); values.append(quantity)
        if not fields:
            return
        values.append(token_address)
        with self.lock, self.conn:
            self.conn.execute(
                f"UPDATE open_positions SET {', '.join(fields)} WHERE token_address = ?",
                values,
            )

    def delete_position(self, token_address):
        """Remove a closed position."""
        with self.lock, self.conn:
            self.conn.execute(
                "DELETE FROM open_positions WHERE token_address = ?",
                (token_address,),
            )

    def load_positions(self):
        """Load all open positions from DB (called at startup)."""
        with self.lock:
            cursor = self.conn.execute(
                "SELECT token_address, symbol, quantity, entry_price, current_price, "
                "peak_price, partial_sold, entry_tx FROM open_positions"
            )
            return [
                {
                    "token_address": row[0],
                    "symbol": row[1],
                    "quantity": row[2],
                    "entry_price": row[3],
                    "current_price": row[4],
                    "peak_price": row[5],
                    "partial_sold": row[6],
                    "entry_tx": row[7],
                }
                for row in cursor.fetchall()
            ]

    def save_order_status(self, order_id, status):
        with self.lock, self.conn:
            self.conn.execute(
                "INSERT INTO order_status (order_id, status) VALUES (?, ?)",
                (order_id, status),
            )

    def close(self):
        """Close the database connection."""
        with self.lock:
            if self.conn:
                self.conn.close()
                self.conn = None

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass
