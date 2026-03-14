import os 

from frozendict import frozendict as freezed
from dotenv_vault import load_dotenv
from hashlib import sha256
load_dotenv()

envs = freezed({
    "KITE_BASE_URL": os.getenv("KITE_BASE_URL"),
    "KITE_USER_ID": os.getenv("KITE_USER_ID"),
    "KITE_API_KEY": os.getenv("KITE_API_KEY"),
    "KITE_API_SECRET": os.getenv("KITE_API_SECRET"),
    "KITE_REQUEST_TOKEN": os.getenv("KITE_REQUEST_TOKEN"),
    "KITE_ACCESS_TOKEN": os.getenv("KITE_ACCESS_TOKEN"),
    "KITE_PUBLIC_TOKEN": os.getenv("KITE_PUBLIC_TOKEN"),

    # Strategy config
    "TRADE_SYMBOL": os.getenv("TRADE_SYMBOL", "RELIANCE"),
    "TRADE_EXCHANGE": os.getenv("TRADE_EXCHANGE", "NSE"),
    "TRADE_QUANTITY": os.getenv("TRADE_QUANTITY", "1"),
    "TRADE_INTERVAL": os.getenv("TRADE_INTERVAL", "5minute"),
    "RSI_PERIOD": os.getenv("RSI_PERIOD", "14"),
})
