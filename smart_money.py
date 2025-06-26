# smart_money.py
import logging
from storage import Storage

logger = logging.getLogger(__name__)

class SmartMoneyTracker:
    def __init__(self, gmgn_client: object, storage: Storage):
        self.gmgn = gmgn_client
        self.storage = storage
        logger.info("Smart money tracker initialized")

    def monitor_smart_trades(self):
        try:
            smart_trades = self.gmgn.fetch_smart_trades()
            for trade in smart_trades.get("trades", []):
                wallet = trade["wallet"]
                token = trade["token_address"]
                value = trade["value_usd"]
                tx_hash = trade["tx_hash"]
                tags = self.gmgn.fetch_wallet_tags(wallet).get("tags", [])
                self.storage.save_smart_trade(wallet, token, value, tx_hash, tags)
                if self.is_experienced_wallet(tags):
                    logger.info(f"Smart Money Alert: Wallet {wallet} bought {token} for ${value} with tags {tags}")
                    self.storage.flag_token_smart_accumulation(token, wallet, tags)
        except Exception as e:
            logger.error(f"Error in SmartMoneyTracker: {e}")

    def is_experienced_wallet(self, tags):
        keywords = ["early investor", "insider", "whale", "vc", "dex founder"]
        return any(any(k in tag.lower() for k in keywords) for tag in tags)