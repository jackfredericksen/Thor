#!/usr/bin/env python3
"""
Thor Memecoin Sniping Bot - Modern Web Dashboard
Flask-based interface with real-time updates and social sentiment tracking
"""

from flask import Flask, render_template, jsonify, request
import asyncio
import threading
import time
from datetime import datetime
from typing import Dict, List
import os

app = Flask(__name__)

# Global bot instance
bot = None
bot_thread = None
bot_running = False
bot_paused = False

# Data stores
stats_data = {
    'cycle_count': 0,
    'total_discovered': 0,
    'total_filtered': 0,
    'total_trades': 0,
    'uptime': 0,
    'status': 'stopped',
    'ai_active': False,
    'ai_decisions': 0
}

latest_tokens = []
latest_trades = []
system_logs = []

def _get_sol_balance() -> float:
    """Fetch live SOL wallet balance; returns 0.0 on any error."""
    try:
        if bot and hasattr(bot, 'trader') and hasattr(bot.trader, 'solana_client'):
            return bot.trader._run_async(bot.trader.solana_client.get_sol_balance())
    except Exception:
        pass
    return 0.0


def add_log(message: str, level: str = "INFO"):
    """Add log message"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    system_logs.append({
        'timestamp': timestamp,
        'level': level,
        'message': message
    })
    # Keep only last 100 logs
    if len(system_logs) > 100:
        system_logs.pop(0)

def run_bot_loop():
    """Run the bot in a loop"""
    global bot_running, bot_paused, stats_data, latest_tokens, latest_trades

    from config import FETCH_INTERVAL

    while bot_running:
        if not bot_paused:
            try:
                add_log(f"Starting cycle {bot.cycle_count + 1}...", "INFO")

                # --- Discovery + filtering (fast, update UI immediately after) ---
                filtered = bot.discover_and_filter_tokens()
                latest_tokens = bot.get_latest_tokens(20)  # visible right after discovery
                stats_data = bot.get_dashboard_stats()
                stats_data['status'] = 'running'

                # --- Process tokens (slow - trading decisions) ---
                if filtered:
                    bot.process_tokens(filtered)

                # --- Smart money + final state sync ---
                bot.monitor_smart_money()
                bot.cycle_count += 1

                stats_data = bot.get_dashboard_stats()
                stats_data['status'] = 'running'
                latest_tokens = bot.get_latest_tokens(20)
                latest_trades = bot.get_recent_trades(50)

                add_log(f"Cycle {bot.cycle_count} complete", "SUCCESS")
                time.sleep(FETCH_INTERVAL)

            except Exception as e:
                add_log(f"Error in bot cycle: {str(e)}", "ERROR")
                time.sleep(5)
        else:
            time.sleep(0.5)

@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('dashboard.html')

@app.route('/api/status')
def get_status():
    """Get current status — reads live from bot so uptime/counts always update."""
    live_stats = dict(stats_data)
    if bot is not None:
        live_stats['uptime'] = time.time() - getattr(bot, 'start_time', time.time())
        live_stats['cycle_count'] = getattr(bot, 'cycle_count', 0)
        live_stats['total_discovered'] = getattr(bot, 'total_tokens_discovered', 0)
        live_stats['total_filtered'] = getattr(bot, 'total_tokens_filtered', 0)
        live_stats['total_trades'] = getattr(bot, 'total_trades_executed', 0)
        live_stats['sol_balance'] = _get_sol_balance()
    return jsonify({
        'running': bot_running,
        'paused': bot_paused,
        'stats': live_stats
    })

@app.route('/api/tokens')
def get_tokens():
    """Get latest tokens with full analytics"""
    # Fall back to reading directly from bot so data shows up mid-cycle
    tokens_source = latest_tokens or (bot.get_latest_tokens(20) if bot else [])
    tokens_formatted = []
    for token in tokens_source:
        # Get validation results if available
        validation = token.get('validation', {})

        tokens_formatted.append({
            'symbol': token.get('symbol', 'N/A'),
            'address': (token.get('address') or token.get('token_address') or '')[:8] + '...',
            'price': token.get('price_usd', 0),
            'price_display': f"${token.get('price_usd', 0):.8f}",
            'change': token.get('price_change_24h', 0),
            'change_display': f"{token.get('price_change_24h', 0):+.2f}%",
            'volume': token.get('daily_volume_usd', 0),
            'volume_display': f"${token.get('daily_volume_usd', 0):,.0f}",
            'liquidity': token.get('liquidity_usd', 0),
            'liquidity_display': f"${token.get('liquidity_usd', 0):,.0f}",
            'market_cap': token.get('market_cap', 0),
            'market_cap_display': f"${token.get('market_cap', 0):,.0f}",
            'holders': token.get('holder_count', 0),
            'age_hours': token.get('age_hours', 0),
            'score': token.get('filter_score', 0),
            'score_display': f"{token.get('filter_score', 0):.3f}",
            # DexScreener HotScanner data
            'dex_hotness_score': token.get('dex_hotness_score'),
            'dex_tags': token.get('dex_tags', []),
            'discovery_source': token.get('discovery_source', 'unknown'),
            'breakout_readiness': (token.get('dex_analytics') or {}).get('breakout_readiness'),
            # Validation layer results
            'contract_safe': validation.get('contract_safe', None),
            'momentum_score': validation.get('momentum_score', 0),
            'timing_score': validation.get('timing_score', 0),
            'social_score': validation.get('social_score', 0),
            'social_mentions': validation.get('social_mentions', 0),
            'social_sentiment': validation.get('social_sentiment', 0),
            'curve_health': validation.get('curve_health', 0),
            # AI decision if available
            'ai_decision': validation.get('ai_decision', None),
            'ai_confidence': validation.get('ai_confidence', 0),
            'ai_reasoning': validation.get('ai_reasoning', ''),
        })
    return jsonify(tokens_formatted)

@app.route('/api/trades')
def get_trades():
    """Get latest trades"""
    trades_formatted = []
    for trade in latest_trades[-50:]:
        timestamp = trade.get('timestamp', datetime.now())
        if isinstance(timestamp, datetime):
            time_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
        else:
            time_str = str(timestamp)

        trades_formatted.append({
            'time': time_str,
            'action': trade.get('action', 'N/A').upper(),
            'symbol': trade.get('symbol', 'N/A'),
            'price': f"${trade.get('price', 0):.8f}",
            'quantity': f"{trade.get('quantity', 0):,}"
        })
    return jsonify(trades_formatted)

@app.route('/api/logs')
def get_logs():
    """Get system logs"""
    return jsonify(system_logs[-50:])

@app.route('/api/validation')
def get_validation():
    """Get validation statistics"""
    if bot and hasattr(bot, 'trader'):
        return jsonify(bot.trader.get_validation_stats())
    return jsonify({
        'total_evaluated': 0,
        'passed_all': 0,
        'rejection_breakdown': {},
        'pass_rate': 0
    })

@app.route('/api/portfolio')
def get_portfolio():
    """Get portfolio summary"""
    if bot and hasattr(bot, 'trader'):
        return jsonify(bot.trader.get_portfolio_summary())
    return jsonify({})

@app.route('/api/positions')
def get_positions():
    """Get all open positions with live P&L."""
    if not bot or not hasattr(bot, 'trader'):
        return jsonify([])
    positions = []
    for addr, pos in bot.trader.risk_manager.positions.items():
        entry = pos.entry_price or 0
        current = pos.current_price or entry
        pnl_usd = (current - entry) * pos.quantity if entry else 0
        pnl_pct = ((current - entry) / entry * 100) if entry else 0
        positions.append({
            'address': addr,
            'symbol': pos.symbol,
            'quantity': pos.quantity,
            'entry_price': entry,
            'current_price': current,
            'peak_price': pos.peak_price,
            'pnl_usd': round(pnl_usd, 4),
            'pnl_pct': round(pnl_pct, 2),
            'cost_usd': round(pos.cost_basis, 4),
            'partial_sold': pos.partial_sold,
            'entry_tx': pos.entry_tx,
            'entry_time': pos.entry_time,
        })
    return jsonify(positions)

@app.route('/api/positions/<token_address>/close', methods=['POST'])
def close_position(token_address):
    """Manually close an open position via the web GUI."""
    if not bot or not hasattr(bot, 'trader'):
        return jsonify({'error': 'Bot not running'}), 400
    pos = bot.trader.risk_manager.positions.get(token_address)
    if not pos:
        return jsonify({'error': 'Position not found'}), 404
    try:
        ok = bot.trader._execute_sell(
            token_address, pos.symbol,
            pos.current_price or pos.entry_price,
            reason="Manual close (web GUI)",
        )
        return jsonify({'success': ok})
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500

@app.route('/api/dashboard')
def get_dashboard():
    """Get complete dashboard data in one request"""
    validation_stats = {}
    portfolio = {}
    ai_stats = {
        'enabled': False,
        'model': 'None',
        'total_decisions': 0,
        'avg_confidence': 0
    }

    if bot and hasattr(bot, 'trader'):
        validation_stats = bot.trader.get_validation_stats()
        portfolio = bot.trader.get_portfolio_summary()

        # Get AI stats if enabled
        if hasattr(bot.trader, 'ai_agent') and bot.trader.ai_agent:
            ai_stats = {
                'enabled': True,
                'model': bot.trader.ai_agent.model,
                'total_decisions': bot.trader.ai_agent.total_decisions,
                'avg_confidence': 0  # TODO: Calculate from decision history
            }

    # Build live stats so uptime/counts always reflect current bot state
    live_stats = dict(stats_data)
    if bot is not None:
        live_stats['uptime'] = time.time() - getattr(bot, 'start_time', time.time())
        live_stats['cycle_count'] = getattr(bot, 'cycle_count', 0)
        live_stats['total_discovered'] = getattr(bot, 'total_tokens_discovered', 0)
        live_stats['total_filtered'] = getattr(bot, 'total_tokens_filtered', 0)
        live_stats['total_trades'] = getattr(bot, 'total_trades_executed', 0)
        live_stats['sol_balance'] = _get_sol_balance()

    live_tokens = latest_tokens or (bot.get_latest_tokens(20) if bot else [])
    live_trades = latest_trades or (bot.get_recent_trades(10) if bot else [])

    return jsonify({
        'status': live_stats,
        'validation': validation_stats,
        'portfolio': portfolio,
        'ai': ai_stats,
        'tokens': live_tokens[:10],
        'recent_trades': live_trades[-10:],
        'logs': system_logs[-20:]
    })

@app.route('/api/control', methods=['POST'])
def control():
    """Control bot (start/pause/stop)"""
    global bot_running, bot_paused, bot_thread, stats_data

    action = request.json.get('action')

    if action == 'start':
        if not bot_running:
            bot_running = True
            bot_paused = False
            stats_data['status'] = 'running'
            add_log("Bot started", "SUCCESS")

            bot_thread = threading.Thread(target=run_bot_loop, daemon=True)
            bot_thread.start()

            return jsonify({'success': True, 'message': 'Bot started'})

    elif action == 'pause':
        bot_paused = not bot_paused
        if bot_paused:
            stats_data['status'] = 'paused'
            add_log("Bot paused", "WARNING")
            return jsonify({'success': True, 'message': 'Bot paused'})
        else:
            stats_data['status'] = 'running'
            add_log("Bot resumed", "SUCCESS")
            return jsonify({'success': True, 'message': 'Bot resumed'})

    elif action == 'stop':
        if bot_running:
            bot_running = False
            bot_paused = False
            stats_data['status'] = 'stopped'
            add_log("Bot stopped", "WARNING")
            return jsonify({'success': True, 'message': 'Bot stopped'})

    return jsonify({'success': False, 'message': 'Unknown action'})

def create_html_template():
    """Create HTML template"""
    os.makedirs('templates', exist_ok=True)

    html = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Thor Memecoin Sniping Bot</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            color: #fff;
            padding: 20px;
        }
        .container { max-width: 1400px; margin: 0 auto; }
        header {
            background: rgba(0,0,0,0.3);
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        h1 { font-size: 28px; }
        .status-indicator {
            display: inline-block;
            width: 20px;
            height: 20px;
            border-radius: 50%;
            margin-right: 10px;
        }
        .status-running { background: #4CAF50; box-shadow: 0 0 10px #4CAF50; }
        .status-paused { background: #FF9800; box-shadow: 0 0 10px #FF9800; }
        .status-stopped { background: #f44336; box-shadow: 0 0 10px #f44336; }
        .controls {
            display: flex;
            gap: 10px;
        }
        button {
            padding: 10px 20px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 14px;
            font-weight: bold;
            transition: all 0.3s;
        }
        .btn-start { background: #4CAF50; color: white; }
        .btn-start:hover { background: #45a049; }
        .btn-pause { background: #FF9800; color: white; }
        .btn-pause:hover { background: #e68900; }
        .btn-stop { background: #f44336; color: white; }
        .btn-stop:hover { background: #da190b; }
        .btn-start:disabled, .btn-pause:disabled, .btn-stop:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }
        .stat-card {
            background: rgba(0,0,0,0.3);
            padding: 20px;
            border-radius: 10px;
            text-align: center;
        }
        .stat-value {
            font-size: 32px;
            font-weight: bold;
            margin: 10px 0;
        }
        .stat-label { font-size: 14px; opacity: 0.8; }
        .tabs {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
        }
        .tab {
            padding: 10px 20px;
            background: rgba(0,0,0,0.3);
            border: none;
            color: white;
            cursor: pointer;
            border-radius: 5px 5px 0 0;
            transition: all 0.3s;
        }
        .tab.active {
            background: rgba(0,0,0,0.5);
            font-weight: bold;
        }
        .tab-content {
            background: rgba(0,0,0,0.3);
            padding: 20px;
            border-radius: 0 10px 10px 10px;
            min-height: 400px;
            display: none;
        }
        .tab-content.active { display: block; }
        table {
            width: 100%;
            border-collapse: collapse;
        }
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        th {
            background: rgba(0,0,0,0.3);
            font-weight: bold;
        }
        .log-entry {
            padding: 8px;
            margin: 5px 0;
            border-radius: 5px;
            background: rgba(0,0,0,0.2);
            font-family: 'Courier New', monospace;
            font-size: 13px;
        }
        .log-INFO { border-left: 3px solid #2196F3; }
        .log-SUCCESS { border-left: 3px solid #4CAF50; }
        .log-WARNING { border-left: 3px solid #FF9800; }
        .log-ERROR { border-left: 3px solid #f44336; }
        .empty-state {
            text-align: center;
            padding: 60px 20px;
            opacity: 0.5;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div>
                <h1>
                    <span class="status-indicator status-stopped" id="statusIndicator"></span>
                    Thor Memecoin Sniping Bot
                    <span id="statusText" style="font-size: 18px; margin-left: 10px;">STOPPED</span>
                </h1>
            </div>
            <div class="controls">
                <button class="btn-start" id="btnStart" onclick="controlBot('start')">▶ START</button>
                <button class="btn-pause" id="btnPause" onclick="controlBot('pause')" disabled>⏸ PAUSE</button>
                <button class="btn-stop" id="btnStop" onclick="controlBot('stop')" disabled>⏹ STOP</button>
            </div>
        </header>

        <div class="stats">
            <div class="stat-card">
                <div class="stat-label">Cycles</div>
                <div class="stat-value" id="statCycles">0</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Discovered</div>
                <div class="stat-value" id="statDiscovered">0</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Filtered</div>
                <div class="stat-value" id="statFiltered">0</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Trades</div>
                <div class="stat-value" id="statTrades">0</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Uptime</div>
                <div class="stat-value" id="statUptime">00:00:00</div>
            </div>
        </div>

        <div class="tabs">
            <button class="tab active" onclick="switchTab('tokens')">📊 Live Token Feed</button>
            <button class="tab" onclick="switchTab('validation')">🔒 Validation Stats</button>
            <button class="tab" onclick="switchTab('portfolio')">💼 Portfolio</button>
            <button class="tab" onclick="switchTab('trades')">💰 Trades</button>
            <button class="tab" onclick="switchTab('logs')">📝 System Logs</button>
        </div>

        <div class="tab-content active" id="tabTokens">
            <table id="tokensTable">
                <thead>
                    <tr>
                        <th>Symbol</th>
                        <th>Price</th>
                        <th>24h Change</th>
                        <th>Volume</th>
                        <th>Score</th>
                        <th>Hot🔥</th>
                        <th>Tags</th>
                        <th>Source</th>
                    </tr>
                </thead>
                <tbody id="tokensBody">
                    <tr><td colspan="8" class="empty-state">No tokens discovered yet. Click START to begin.</td></tr>
                </tbody>
            </table>
        </div>

        <div class="tab-content" id="tabValidation">
            <h3 style="margin-bottom: 20px;">8-Layer Validation System</h3>
            <div class="stats" style="grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));">
                <div class="stat-card">
                    <div class="stat-label">Evaluated</div>
                    <div class="stat-value" id="validationTotal">0</div>
                </div>
                <div class="stat-card" style="background: rgba(76, 175, 80, 0.2);">
                    <div class="stat-label">✅ Passed All</div>
                    <div class="stat-value" id="validationPassed">0</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Pass Rate</div>
                    <div class="stat-value" id="validationPassRate">0%</div>
                </div>
            </div>
            <h4 style="margin: 30px 0 15px 0;">Rejection Breakdown</h4>
            <table>
                <thead>
                    <tr>
                        <th>Validation Layer</th>
                        <th>Rejected</th>
                        <th>Description</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>💰 Price Check</td>
                        <td id="rejPrice">0</td>
                        <td>Invalid or $0.00 prices</td>
                    </tr>
                    <tr>
                        <td>📊 Volume Check</td>
                        <td id="rejVolume">0</td>
                        <td>Volume < $50,000</td>
                    </tr>
                    <tr>
                        <td>💧 Liquidity Check</td>
                        <td id="rejLiquidity">0</td>
                        <td>Liquidity < $10,000</td>
                    </tr>
                    <tr>
                        <td>🔒 Contract Safety</td>
                        <td id="rejContract">0</td>
                        <td>Mint/freeze authority, holder distribution</td>
                    </tr>
                    <tr>
                        <td>📉 Momentum Analysis</td>
                        <td id="rejDump">0</td>
                        <td>Dump detected or low buy/sell ratio</td>
                    </tr>
                    <tr>
                        <td>⏰ Launch Timing</td>
                        <td id="rejTiming">0</td>
                        <td>Outside golden window or bad timing</td>
                    </tr>
                    <tr>
                        <td>📱 Social Sentiment</td>
                        <td id="rejSocial">0</td>
                        <td>Negative sentiment or shrinking community</td>
                    </tr>
                    <tr>
                        <td>🎯 Bonding Curve</td>
                        <td id="rejCurve">0</td>
                        <td>High rug risk or low graduation chance</td>
                    </tr>
                </tbody>
            </table>
        </div>

        <div class="tab-content" id="tabPortfolio">
            <h3 style="margin-bottom: 20px;">Portfolio Summary</h3>
            <div class="stats">
                <div class="stat-card">
                    <div class="stat-label">Portfolio Value</div>
                    <div class="stat-value" id="portfolioValue">$0</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Total Exposure</div>
                    <div class="stat-value" id="portfolioExposure">$0</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Positions</div>
                    <div class="stat-value" id="portfolioPositions">0</div>
                </div>
                <div class="stat-card" id="pnlCard">
                    <div class="stat-label">Unrealized P&L</div>
                    <div class="stat-value" id="portfolioPnL">$0</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Success Rate</div>
                    <div class="stat-value" id="portfolioSuccessRate">0%</div>
                </div>
            </div>
        </div>

        <div class="tab-content" id="tabTrades">
            <table id="tradesTable">
                <thead>
                    <tr>
                        <th>Time</th>
                        <th>Action</th>
                        <th>Symbol</th>
                        <th>Price</th>
                        <th>Quantity</th>
                    </tr>
                </thead>
                <tbody id="tradesBody">
                    <tr><td colspan="5" class="empty-state">No trades executed yet.</td></tr>
                </tbody>
            </table>
        </div>

        <div class="tab-content" id="tabLogs">
            <div id="logsContainer">
                <div class="empty-state">System logs will appear here.</div>
            </div>
        </div>
    </div>

    <script>
        let currentTab = 'tokens';

        function switchTab(tab) {
            // Update tab buttons
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            event.target.classList.add('active');

            // Update tab content
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            document.getElementById('tab' + tab.charAt(0).toUpperCase() + tab.slice(1)).classList.add('active');

            currentTab = tab;
        }

        async function controlBot(action) {
            try {
                const response = await fetch('/api/control', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ action })
                });
                const data = await response.json();
                console.log(data.message);
            } catch (error) {
                console.error('Control error:', error);
            }
        }

        async function updateData() {
            try {
                // Update status
                const statusResp = await fetch('/api/status');
                const status = await statusResp.json();

                // Update status indicator
                const indicator = document.getElementById('statusIndicator');
                const statusText = document.getElementById('statusText');
                const btnStart = document.getElementById('btnStart');
                const btnPause = document.getElementById('btnPause');
                const btnStop = document.getElementById('btnStop');

                if (status.running) {
                    if (status.paused) {
                        indicator.className = 'status-indicator status-paused';
                        statusText.textContent = 'PAUSED';
                        btnStart.disabled = true;
                        btnPause.disabled = false;
                        btnPause.textContent = '▶ RESUME';
                        btnStop.disabled = false;
                    } else {
                        indicator.className = 'status-indicator status-running';
                        statusText.textContent = 'RUNNING';
                        btnStart.disabled = true;
                        btnPause.disabled = false;
                        btnPause.textContent = '⏸ PAUSE';
                        btnStop.disabled = false;
                    }
                } else {
                    indicator.className = 'status-indicator status-stopped';
                    statusText.textContent = 'STOPPED';
                    btnStart.disabled = false;
                    btnPause.disabled = true;
                    btnStop.disabled = true;
                }

                // Update stats
                document.getElementById('statCycles').textContent = status.stats.cycle_count || 0;
                document.getElementById('statDiscovered').textContent = (status.stats.total_discovered || 0).toLocaleString();
                document.getElementById('statFiltered').textContent = (status.stats.total_filtered || 0).toLocaleString();
                document.getElementById('statTrades').textContent = status.stats.total_trades || 0;

                const uptime = status.stats.uptime || 0;
                const hours = Math.floor(uptime / 3600);
                const minutes = Math.floor((uptime % 3600) / 60);
                const seconds = Math.floor(uptime % 60);
                document.getElementById('statUptime').textContent =
                    `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;

                // Update tokens
                const tokensResp = await fetch('/api/tokens');
                const tokens = await tokensResp.json();
                const tokensBody = document.getElementById('tokensBody');

                if (tokens.length > 0) {
                    tokensBody.innerHTML = tokens.map(t => {
                        const hotScore = t.dex_hotness_score != null ? t.dex_hotness_score.toFixed(0) : '-';
                        const hotColor = t.dex_hotness_score >= 70 ? '#4CAF50' : t.dex_hotness_score >= 50 ? '#FF9800' : '#aaa';
                        const tags = (t.dex_tags || []).slice(0, 2).join(' ') || '-';
                        const src = (t.discovery_source || 'unknown').replace('dex_hot_scanner', '🔥dex').replace('gmgn_hot_sol', 'gmgn').replace(/_/g, ' ');
                        const changeColor = t.change >= 0 ? '#4CAF50' : '#f44336';
                        return `<tr>
                            <td>${t.symbol}</td>
                            <td>${t.price_display}</td>
                            <td style="color:${changeColor}">${t.change_display}</td>
                            <td>${t.volume_display}</td>
                            <td>${t.score_display}</td>
                            <td style="color:${hotColor};font-weight:bold">${hotScore}</td>
                            <td style="font-size:11px">${tags}</td>
                            <td style="font-size:11px;opacity:0.7">${src}</td>
                        </tr>`;
                    }).join('');
                }

                // Update trades
                const tradesResp = await fetch('/api/trades');
                const trades = await tradesResp.json();
                const tradesBody = document.getElementById('tradesBody');

                if (trades.length > 0) {
                    tradesBody.innerHTML = trades.map(t => `
                        <tr>
                            <td>${t.time}</td>
                            <td>${t.action}</td>
                            <td>${t.symbol}</td>
                            <td>${t.price}</td>
                            <td>${t.quantity}</td>
                        </tr>
                    `).join('');
                }

                // Update logs
                const logsResp = await fetch('/api/logs');
                const logs = await logsResp.json();
                const logsContainer = document.getElementById('logsContainer');

                if (logs.length > 0) {
                    logsContainer.innerHTML = logs.map(l => `
                        <div class="log-entry log-${l.level}">
                            [${l.timestamp}] ${l.level}: ${l.message}
                        </div>
                    `).join('');
                    logsContainer.scrollTop = logsContainer.scrollHeight;
                }

                // Update validation stats
                const validationResp = await fetch('/api/validation');
                const validation = await validationResp.json();

                document.getElementById('validationTotal').textContent = validation.total_evaluated || 0;
                document.getElementById('validationPassed').textContent = validation.passed_all || 0;
                document.getElementById('validationPassRate').textContent =
                    (validation.pass_rate || 0).toFixed(1) + '%';

                if (validation.rejection_breakdown) {
                    document.getElementById('rejPrice').textContent = validation.rejection_breakdown.price || 0;
                    document.getElementById('rejVolume').textContent = validation.rejection_breakdown.volume || 0;
                    document.getElementById('rejLiquidity').textContent = validation.rejection_breakdown.liquidity || 0;
                    document.getElementById('rejContract').textContent = validation.rejection_breakdown.contract_unsafe || 0;
                    document.getElementById('rejDump').textContent = validation.rejection_breakdown.dump_detected || 0;
                    document.getElementById('rejTiming').textContent = validation.rejection_breakdown.bad_timing || 0;
                    document.getElementById('rejSocial').textContent = validation.rejection_breakdown.negative_social || 0;
                    document.getElementById('rejCurve').textContent = validation.rejection_breakdown.bonding_curve || 0;
                }

                // Update portfolio
                const portfolioResp = await fetch('/api/portfolio');
                const portfolio = await portfolioResp.json();

                if (portfolio.portfolio_value !== undefined) {
                    document.getElementById('portfolioValue').textContent =
                        '$' + (portfolio.portfolio_value || 0).toFixed(2);
                    document.getElementById('portfolioExposure').textContent =
                        '$' + (portfolio.total_exposure || 0).toFixed(2);
                    document.getElementById('portfolioPositions').textContent =
                        portfolio.number_of_positions || 0;

                    const pnl = portfolio.unrealized_pnl || 0;
                    const pnlCard = document.getElementById('pnlCard');
                    document.getElementById('portfolioPnL').textContent =
                        '$' + pnl.toFixed(2);

                    // Color code P&L
                    if (pnl > 0) {
                        pnlCard.style.background = 'rgba(76, 175, 80, 0.2)';
                    } else if (pnl < 0) {
                        pnlCard.style.background = 'rgba(244, 67, 54, 0.2)';
                    } else {
                        pnlCard.style.background = 'rgba(0,0,0,0.3)';
                    }

                    document.getElementById('portfolioSuccessRate').textContent =
                        ((portfolio.success_rate || 0) * 100).toFixed(1) + '%';
                }

            } catch (error) {
                console.error('Update error:', error);
            }
        }

        // Update every second
        setInterval(updateData, 1000);
        updateData();
    </script>
</body>
</html>'''

    with open('templates/index.html', 'w') as f:
        f.write(html)

def main():
    """Entry point for web GUI"""
    global bot

    # Import bot
    from main import TradingBot

    print("🔨 Thor Memecoin Sniping Bot - Modern Web Dashboard")
    print("=" * 60)
    print("")

    add_log("Web GUI initialized", "INFO")

    # Initialize bot
    print("Initializing bot...")
    bot = TradingBot()
    add_log("Bot initialized", "SUCCESS")

    print("")
    print("✅ Web GUI ready!")
    print("")
    print("🌐 Open your browser and go to:")
    print("   http://localhost:5001")
    print("")
    print("Press Ctrl+C to stop the server")
    print("")

    # Run Flask app
    app.run(host='0.0.0.0', port=5001, debug=False)

if __name__ == "__main__":
    main()
