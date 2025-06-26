# trader.py

import time


class Trader:
    def __init__(self, gmgn_client, storage):
        self.gmgn = gmgn_client
        self.storage = storage

    def execute_trade(self, token_address, rating, max_slippage=0.02):
        if rating == "bullish":
            quantity = self.calculate_position_size(token_address)
            order = self.gmgn.place_order(
                token_address=token_address,
                side="buy",
                quantity=quantity,
                order_type="market",
                slippage=max_slippage,
            )
            self.monitor_order(order["order_id"])
        elif rating == "bearish":
            print(f"Bearish rating for {token_address}, skipping trade.")
        else:
            print(f"Neutral rating for {token_address}, holding position.")

    def monitor_order(self, order_id):
        while True:
            status = self.gmgn.check_order_status(order_id)
            print(f"Order {order_id} status: {status['status']}")
            self.storage.save_order_status(order_id, status["status"])
            if status["status"] in ["filled", "cancelled", "failed"]:
                break
            time.sleep(3)

    def calculate_position_size(self, token_address):
        # Placeholder: replace with your position sizing logic
        return 100
