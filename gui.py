#!/usr/bin/env python3
"""
Thor Memecoin Sniping Bot - Lightweight GUI
Simple Tkinter-based interface for monitoring and control
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
import time
import queue
from datetime import datetime
from typing import Dict, List, Any
import sys

class ThorGUI:
    """Lightweight GUI for Thor bot"""

    def __init__(self, bot):
        self.bot = bot
        self.root = tk.Tk()
        self.root.title("Thor Memecoin Sniping Bot")
        self.root.geometry("1200x800")

        # Message queue for thread-safe updates
        self.message_queue = queue.Queue()

        # Bot control
        self.running = False
        self.paused = False

        # Setup UI
        self.setup_ui()

        # Start update loop
        self.root.after(100, self.process_queue)

    def setup_ui(self):
        """Create the GUI layout"""
        # Top frame - Controls
        control_frame = ttk.Frame(self.root, padding="10")
        control_frame.pack(fill=tk.X)

        # Status indicator
        self.status_label = ttk.Label(control_frame, text="●", font=("Arial", 24), foreground="red")
        self.status_label.pack(side=tk.LEFT, padx=5)

        self.status_text = ttk.Label(control_frame, text="STOPPED", font=("Arial", 14, "bold"))
        self.status_text.pack(side=tk.LEFT, padx=5)

        # Control buttons
        self.start_btn = ttk.Button(control_frame, text="▶ START", command=self.start_bot, width=12)
        self.start_btn.pack(side=tk.LEFT, padx=5)

        self.pause_btn = ttk.Button(control_frame, text="⏸ PAUSE", command=self.pause_bot, state=tk.DISABLED, width=12)
        self.pause_btn.pack(side=tk.LEFT, padx=5)

        self.stop_btn = ttk.Button(control_frame, text="⏹ STOP", command=self.stop_bot, state=tk.DISABLED, width=12)
        self.stop_btn.pack(side=tk.LEFT, padx=5)

        # Stats frame
        stats_frame = ttk.LabelFrame(self.root, text="Statistics", padding="10")
        stats_frame.pack(fill=tk.X, padx=10, pady=5)

        # Stats grid
        stats_grid = ttk.Frame(stats_frame)
        stats_grid.pack(fill=tk.X)

        # Cycles
        ttk.Label(stats_grid, text="Cycles:", font=("Arial", 10, "bold")).grid(row=0, column=0, sticky=tk.W, padx=5)
        self.cycles_label = ttk.Label(stats_grid, text="0", font=("Arial", 10))
        self.cycles_label.grid(row=0, column=1, sticky=tk.W, padx=5)

        # Discovered
        ttk.Label(stats_grid, text="Tokens Discovered:", font=("Arial", 10, "bold")).grid(row=0, column=2, sticky=tk.W, padx=5)
        self.discovered_label = ttk.Label(stats_grid, text="0", font=("Arial", 10))
        self.discovered_label.grid(row=0, column=3, sticky=tk.W, padx=5)

        # Filtered
        ttk.Label(stats_grid, text="Filtered:", font=("Arial", 10, "bold")).grid(row=0, column=4, sticky=tk.W, padx=5)
        self.filtered_label = ttk.Label(stats_grid, text="0", font=("Arial", 10))
        self.filtered_label.grid(row=0, column=5, sticky=tk.W, padx=5)

        # Trades
        ttk.Label(stats_grid, text="Trades:", font=("Arial", 10, "bold")).grid(row=0, column=6, sticky=tk.W, padx=5)
        self.trades_label = ttk.Label(stats_grid, text="0", font=("Arial", 10))
        self.trades_label.grid(row=0, column=7, sticky=tk.W, padx=5)

        # Uptime
        ttk.Label(stats_grid, text="Uptime:", font=("Arial", 10, "bold")).grid(row=0, column=8, sticky=tk.W, padx=5)
        self.uptime_label = ttk.Label(stats_grid, text="0s", font=("Arial", 10))
        self.uptime_label.grid(row=0, column=9, sticky=tk.W, padx=5)

        # Notebook for tabs
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Tab 1: Live Feed
        feed_frame = ttk.Frame(notebook)
        notebook.add(feed_frame, text="📊 Live Token Feed")

        # Token feed table
        self.feed_tree = ttk.Treeview(feed_frame, columns=("symbol", "price", "change", "volume", "score"), show="headings", height=15)
        self.feed_tree.heading("symbol", text="Symbol")
        self.feed_tree.heading("price", text="Price")
        self.feed_tree.heading("change", text="24h Change")
        self.feed_tree.heading("volume", text="Volume")
        self.feed_tree.heading("score", text="Score")

        self.feed_tree.column("symbol", width=100)
        self.feed_tree.column("price", width=120)
        self.feed_tree.column("change", width=120)
        self.feed_tree.column("volume", width=150)
        self.feed_tree.column("score", width=80)

        feed_scroll = ttk.Scrollbar(feed_frame, orient=tk.VERTICAL, command=self.feed_tree.yview)
        self.feed_tree.configure(yscrollcommand=feed_scroll.set)

        self.feed_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        feed_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Tab 2: Trades
        trades_frame = ttk.Frame(notebook)
        notebook.add(trades_frame, text="💰 Trades")

        self.trades_tree = ttk.Treeview(trades_frame, columns=("time", "action", "symbol", "price", "quantity"), show="headings", height=15)
        self.trades_tree.heading("time", text="Time")
        self.trades_tree.heading("action", text="Action")
        self.trades_tree.heading("symbol", text="Symbol")
        self.trades_tree.heading("price", text="Price")
        self.trades_tree.heading("quantity", text="Quantity")

        self.trades_tree.column("time", width=180)
        self.trades_tree.column("action", width=100)
        self.trades_tree.column("symbol", width=120)
        self.trades_tree.column("price", width=120)
        self.trades_tree.column("quantity", width=120)

        trades_scroll = ttk.Scrollbar(trades_frame, orient=tk.VERTICAL, command=self.trades_tree.yview)
        self.trades_tree.configure(yscrollcommand=trades_scroll.set)

        self.trades_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        trades_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Tab 3: Logs
        log_frame = ttk.Frame(notebook)
        notebook.add(log_frame, text="📝 System Logs")

        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, width=100, height=20, font=("Courier", 9))
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # Configure text tags for colored logs
        self.log_text.tag_config("INFO", foreground="blue")
        self.log_text.tag_config("WARNING", foreground="orange")
        self.log_text.tag_config("ERROR", foreground="red")
        self.log_text.tag_config("SUCCESS", foreground="green")

        # Bottom status bar
        status_bar = ttk.Frame(self.root)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)

        self.status_bar_label = ttk.Label(status_bar, text="Ready to start", relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar_label.pack(fill=tk.X, padx=5, pady=2)

    def log(self, message: str, level: str = "INFO"):
        """Add log message (thread-safe)"""
        self.message_queue.put(("log", (message, level)))

    def update_stats(self, stats: Dict):
        """Update statistics (thread-safe)"""
        self.message_queue.put(("stats", stats))

    def update_tokens(self, tokens: List[Dict]):
        """Update token feed (thread-safe)"""
        self.message_queue.put(("tokens", tokens))

    def update_trades(self, trades: List[Dict]):
        """Update trades (thread-safe)"""
        self.message_queue.put(("trades", trades))

    def process_queue(self):
        """Process messages from queue"""
        try:
            while True:
                msg_type, data = self.message_queue.get_nowait()

                if msg_type == "log":
                    message, level = data
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    self.log_text.insert(tk.END, f"[{timestamp}] {message}\n", level)
                    self.log_text.see(tk.END)

                elif msg_type == "stats":
                    self.cycles_label.config(text=str(data.get('cycle_count', 0)))
                    self.discovered_label.config(text=f"{data.get('total_discovered', 0):,}")
                    self.filtered_label.config(text=f"{data.get('total_filtered', 0):,}")
                    self.trades_label.config(text=str(data.get('total_trades', 0)))

                    uptime = int(data.get('uptime', 0))
                    hours = uptime // 3600
                    minutes = (uptime % 3600) // 60
                    seconds = uptime % 60
                    self.uptime_label.config(text=f"{hours:02d}:{minutes:02d}:{seconds:02d}")

                elif msg_type == "tokens":
                    # Clear and update token feed
                    for item in self.feed_tree.get_children():
                        self.feed_tree.delete(item)

                    for token in data[:20]:  # Show top 20
                        symbol = token.get('symbol', 'N/A')
                        price = f"${token.get('price_usd', 0):.8f}"
                        change = f"{token.get('price_change_24h', 0):+.2f}%"
                        volume = f"${token.get('daily_volume_usd', 0):,.0f}"
                        score = f"{token.get('filter_score', 0):.3f}"

                        self.feed_tree.insert("", tk.END, values=(symbol, price, change, volume, score))

                elif msg_type == "trades":
                    # Update trades (keep last 50)
                    for item in self.feed_tree.get_children():
                        self.feed_tree.delete(item)

                    for trade in data[-50:]:
                        time_str = trade.get('timestamp', datetime.now()).strftime("%Y-%m-%d %H:%M:%S")
                        action = trade.get('action', 'N/A').upper()
                        symbol = trade.get('symbol', 'N/A')
                        price = f"${trade.get('price', 0):.8f}"
                        quantity = f"{trade.get('quantity', 0):,}"

                        self.trades_tree.insert("", 0, values=(time_str, action, symbol, price, quantity))

        except queue.Empty:
            pass

        # Schedule next update
        self.root.after(100, self.process_queue)

    def start_bot(self):
        """Start the bot"""
        if not self.running:
            self.running = True
            self.paused = False

            # Update UI
            self.status_label.config(foreground="green")
            self.status_text.config(text="RUNNING")
            self.start_btn.config(state=tk.DISABLED)
            self.pause_btn.config(state=tk.NORMAL)
            self.stop_btn.config(state=tk.NORMAL)
            self.status_bar_label.config(text="Bot is running...")

            self.log("Starting Thor bot...", "SUCCESS")

            # Start bot in separate thread
            bot_thread = threading.Thread(target=self.run_bot_loop, daemon=True)
            bot_thread.start()

    def pause_bot(self):
        """Pause/unpause the bot"""
        self.paused = not self.paused

        if self.paused:
            self.status_label.config(foreground="orange")
            self.status_text.config(text="PAUSED")
            self.pause_btn.config(text="▶ RESUME")
            self.status_bar_label.config(text="Bot paused")
            self.log("Bot paused", "WARNING")
        else:
            self.status_label.config(foreground="green")
            self.status_text.config(text="RUNNING")
            self.pause_btn.config(text="⏸ PAUSE")
            self.status_bar_label.config(text="Bot resumed")
            self.log("Bot resumed", "SUCCESS")

    def stop_bot(self):
        """Stop the bot"""
        if self.running:
            self.running = False
            self.paused = False

            # Update UI
            self.status_label.config(foreground="red")
            self.status_text.config(text="STOPPED")
            self.start_btn.config(state=tk.NORMAL)
            self.pause_btn.config(state=tk.DISABLED, text="⏸ PAUSE")
            self.stop_btn.config(state=tk.DISABLED)
            self.status_bar_label.config(text="Bot stopped")

            self.log("Bot stopped", "WARNING")

    def run_bot_loop(self):
        """Run the bot in a loop"""
        from config import FETCH_INTERVAL

        while self.running:
            if not self.paused:
                try:
                    # Run one cycle
                    self.log(f"Starting cycle {self.bot.cycle_count + 1}...", "INFO")
                    self.bot.run_single_cycle()

                    # Update GUI with latest data
                    stats = self.bot.get_dashboard_stats()
                    self.update_stats(stats)

                    tokens = self.bot.get_latest_tokens(20)
                    self.update_tokens(tokens)

                    trades = self.bot.get_recent_trades(50)
                    self.update_trades(trades)

                    self.log(f"Cycle {self.bot.cycle_count} complete", "SUCCESS")

                    # Sleep between cycles
                    time.sleep(FETCH_INTERVAL)

                except Exception as e:
                    self.log(f"Error in bot cycle: {str(e)}", "ERROR")
                    time.sleep(5)
            else:
                time.sleep(0.5)

    def run(self):
        """Start the GUI"""
        self.root.mainloop()


def main():
    """Entry point for GUI mode"""
    # Import bot
    from main import TradingBot

    print("Starting Thor GUI...")
    bot = TradingBot()
    gui = ThorGUI(bot)
    gui.run()


if __name__ == "__main__":
    main()
