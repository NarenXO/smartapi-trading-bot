import logging
from typing import Optional, Dict, Any
from SmartApi import SmartConnect
from src.config import Config

logger = logging.getLogger(__name__)

class OrderEngine:
    def __init__(self, smart_api: SmartConnect, dry_run: bool = True):
        self.smart_api = smart_api
        self.dry_run = dry_run

    def place_order(
        self,
        symbol: str,
        token: str,
        transaction_type: str,
        quantity: int,
        price: float = 0.0,
        stop_loss: float = 0.0,
        exchange: str = "NSE",
        product_type: str = "INTRADAY"
    ) -> Optional[Dict[str, Any]]:
        """
        Places order via SmartAPI.
        transaction_type: 'BUY' or 'SELL'
        Returns order response dict or None on failure.
        """
        order_params = {
            "variety": "NORMAL",
            "tradingsymbol": symbol,
            "symboltoken": token,
            "transactiontype": transaction_type,
            "exchange": exchange,
            "ordertype": Config.ORDER_TYPE,
            "producttype": product_type,
            "duration": "DAY",
            "quantity": quantity
        }

        if Config.ORDER_TYPE == "LIMIT" and price > 0:
            order_params["price"] = price

        if stop_loss > 0:
            order_params["squareoff"] = str(round(price * 0.02, 1))
            order_params["stoploss"] = str(round(stop_loss, 1))

        if self.dry_run:
            logger.info(
                f"[DRY RUN] {transaction_type} {quantity}x {symbol} @ "
                f"{'MARKET' if Config.ORDER_TYPE == 'MARKET' else price} | "
                f"SL: {stop_loss if stop_loss > 0 else 'None'}"
            )
            return {
                "status": True,
                "data": {"orderId": f"DRY-{symbol}-{transaction_type}"},
                "message": "Dry run - no real order placed"
            }

        try:
            logger.info(
                f"[LIVE ORDER] {transaction_type} {quantity}x {symbol} @ "
                f"{'MARKET' if Config.ORDER_TYPE == 'MARKET' else price}"
            )
            response = self.smart_api.placeOrder(order_params)

            if response and response.get("status"):
                order_id = response.get("data", {}).get("orderId", "UNKNOWN")
                logger.info(f"Order placed successfully: {order_id}")
                return response
            else:
                error_msg = response.get("message", "Unknown error") if response else "No response"
                logger.error(f"Order FAILED: {error_msg}")
                return None

        except Exception as e:
            logger.error(f"Exception placing order: {str(e)}")
            return None

    def place_stop_loss(
        self,
        symbol: str,
        token: str,
        quantity: int,
        trigger_price: float,
        exchange: str = "NSE"
    ) -> Optional[Dict[str, Any]]:
        """Places a stop-loss SELL order for an existing BUY position."""
        if self.dry_run:
            logger.info(f"[DRY RUN] STOP-LOSS {quantity}x {symbol} @ trigger Rs{trigger_price}")
            return {"status": True, "data": {"orderId": f"DRY-SL-{symbol}"}}

        try:
            sl_params = {
                "variety": "STOPLOSS",
                "tradingsymbol": symbol,
                "symboltoken": token,
                "transactiontype": "SELL",
                "exchange": exchange,
                "ordertype": "STOPLOSS_LIMIT",
                "producttype": "INTRADAY",
                "duration": "DAY",
                "quantity": quantity,
                "price": str(round(trigger_price * 0.995, 1)),
                "triggerprice": str(trigger_price)
            }
            response = self.smart_api.placeOrder(sl_params)
            if response and response.get("status"):
                logger.info(f"Stop-loss placed: {response['data']['orderId']}")
            return response
        except Exception as e:
            logger.error(f"Stop-loss order failed: {str(e)}")
            return None
