# Dex Trading Bot

A modular Python trading bot that fetches token data from Dexscreener, applies filters, integrates with PumpFun, Bubblemaps, Rugcheck, Moni Score, and GMGN APIs to analyze and trade tokens.

## Features
- Fetch tokens every 15 seconds.
- Filter tokens by volume, age, and holders.
- Vet new tokens via Rugcheck.
- Analyze holder distributions via Bubblemaps.
- Get Twitter sentiment from Moni Score.
- Monitor smart money trades via GMGN.
- Execute live trades with GMGN.
- Modular, extensible design.

## Setup

1. Create virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate   # Linux/macOS
   venv\Scripts\activate      # Windows
