import threading
import time
from datetime import datetime
import pandas as pd
import os
from utils import fetch_price_from_url

PRODUCT_FILE = "products.xlsx"
SYNC_STATUS_FILE = "sync_status.txt"

def is_sync_enabled():
    return os.path.exists(SYNC_STATUS_FILE) and open(SYNC_STATUS_FILE).read().strip() == "enabled"

def start_auto_sync(interval=600):
    def sync():
        while True:
            if is_sync_enabled():
                try:
                    print("Running auto price sync...")
                    df = pd.read_excel(PRODUCT_FILE)
                    for index, row in df.iterrows():
                        url = row.get("URL")
                        if pd.notnull(url):
                            try:
                                new_price = fetch_price_from_url(url, row.get("Supplier"))
                                df.at[index, "Last Sync"] = datetime.now().isoformat()
                                if new_price is not None:
                                    df.at[index, "Last Price"] = df.at[index, "Current Price"]
                                    df.at[index, "Current Price"] = new_price
                                    df.at[index, "Last Updated"] = datetime.now().isoformat()
                            except Exception as e:
                                print(f"Error updating product {row.get('Name')}: {e}")
                    df.to_excel(PRODUCT_FILE, index=False)
                    print("Auto price sync complete.")
                except Exception as e:
                    print(f"Error during auto sync: {e}")
            time.sleep(interval)

    thread = threading.Thread(target=sync, daemon=True)
    thread.start()