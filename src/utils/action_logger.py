import os
import csv
import logging
import datetime

log = logging.getLogger(__name__)

class ActionLogger:
    """
    Unified logging mechanism to record trade actions and the candle context.
    Logs are written to an append-only CSV file to enable future visualizations.
    """
    
    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        
        # Generate a timestamped filename when instantiated
        now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.filename = f"action_logs_{now_str}.csv"
        self.filepath = os.path.join(self.output_dir, self.filename)
        
        self.headers = [
            "timestamp", "mode", "strategy", "symbol", "action", 
            "trigger_price", "candle_time", "candle_open", 
            "candle_high", "candle_low", "candle_close", "candle_volume"
        ]
        
        # Ensure directory exists and initialize file with headers
        os.makedirs(self.output_dir, exist_ok=True)
        try:
            with open(self.filepath, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(self.headers)
            log.info("Initialized ActionLogger at %s", self.filepath)
        except Exception as e:
            log.error("Failed to initialize ActionLogger at %s: %s", self.filepath, e)
                
    def log_action(
        self,
        mode: str,
        strategy_label: str,
        symbol: str,
        action: str,
        trigger_price: float,
        candle: dict | None
    ):
        """
        Appends an action record to the CSV log.
        """
        now = datetime.datetime.now().isoformat()
        
        c_time = candle.get("date", "") if candle else ""
        if isinstance(c_time, datetime.datetime):
            c_time = c_time.isoformat()
            
        c_open = candle.get("open", "") if candle else ""
        c_high = candle.get("high", "") if candle else ""
        c_low = candle.get("low", "") if candle else ""
        c_close = candle.get("close", "") if candle else ""
        c_volume = candle.get("volume", "") if candle else ""
        
        row = [
            now,
            mode,
            strategy_label,
            symbol,
            action,
            trigger_price,
            c_time,
            c_open,
            c_high,
            c_low,
            c_close,
            c_volume
        ]
        
        try:
            with open(self.filepath, mode="a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(row)
            log.debug("Action log appended for %s: %s at %s", strategy_label, action, trigger_price)
        except Exception as e:
            log.error("Failed to write to action log %s: %s", self.filepath, e)
