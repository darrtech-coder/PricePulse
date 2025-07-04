# thread.py

import threading
import time
import sqlite3
from datetime import datetime
import os
from utils import fetch_price_from_url

DB_FILE = "database.db"
SYNC_STATUS_FILE = "sync_status.txt"

def is_sync_enabled():
    return os.path.exists(SYNC_STATUS_FILE) and open(SYNC_STATUS_FILE).read().strip() == "enabled"

def start_auto_sync(interval=600):
    def sync():
        while True:
            if is_sync_enabled():
                try:
                    print("🔁 Running auto price sync...")
                    conn = sqlite3.connect(DB_FILE)
                    conn.row_factory = sqlite3.Row
                    cur = conn.cursor()

                    cur.execute("SELECT * FROM products")
                    products = cur.fetchall()

                    for row in products:
                        pid = row["id"]
                        url = row["url"]
                        supplier = row["supplier"]
                        current_price = row["current_price"]

                        if not url:
                            continue

                        try:
                            new_price = fetch_price_from_url(url, supplier)
                            now = datetime.now().isoformat()

                            # Always update last sync
                            cur.execute("UPDATE products SET last_sync = ? WHERE id = ?", (now, pid))

                            if new_price is not None and new_price != current_price:
                                cur.execute("""
                                    UPDATE products
                                    SET last_price = ?, current_price = ?, last_updated = ?, status = ?
                                    WHERE id = ?
                                """, (current_price, new_price, now, "UPDATED", pid))

                                # Get existing history
                                cur.execute("SELECT price_history FROM price_history WHERE product_id = ?", (pid,))
                                row = cur.fetchone()
                                history = []

                                if row and row["price_history"]:
                                    try:
                                        import json
                                        history = json.loads(row["price_history"])
                                    except:
                                        history = []

                                history.append({
                                    "date": now,
                                    "price": new_price
                                })

                                # Upsert history record
                                history_json = json.dumps(history)
                                cur.execute("""
                                    INSERT INTO price_history (product_id, date, old_price, new_price, change, price_history)
                                    VALUES (?, ?, ?, ?, ?, ?)
                                    ON CONFLICT(product_id) DO UPDATE SET
                                        date=excluded.date,
                                        old_price=excluded.old_price,
                                        new_price=excluded.new_price,
                                        change=excluded.change,
                                        price_history=excluded.price_history
                                """, (pid, now, current_price, new_price, new_price - current_price, history_json))

                        except Exception as e:
                            print(f"[ERROR] Failed to update product {row['name']}: {e}")

                    conn.commit()
                    conn.close()
                    print("✅ Auto price sync complete.")
                except Exception as e:
                    print(f"[ERROR] during auto sync: {e}")

            time.sleep(interval)

    thread = threading.Thread(target=sync, daemon=True)
    thread.start()
