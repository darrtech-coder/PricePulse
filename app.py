from flask import Flask, jsonify, request, send_file, render_template
import sqlite3
import os
import json
from datetime import datetime
from dateutil.parser import parse as parse_date
from utils import fetch_price_from_url
import thread
thread.start_auto_sync()

app = Flask(__name__)
DB_FILE = "database.db"
SUPPLIER_FILE = "suppliers.txt"
CATEGORY_FILE = "categories.txt"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS products (
        product_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        category TEXT,
        supplier TEXT,
        url TEXT,
        current_price REAL,
        last_price REAL,
        last_updated TEXT,
        last_sync TEXT,
        status TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS price_history (
        product_id INTEGER,
        date TEXT,
        old_price REAL,
        new_price REAL,
        change REAL,
        price_history TEXT,
        PRIMARY KEY (product_id)
    )''')
    conn.commit()
    conn.close()

init_db()

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/api/products", methods=["GET"])
def get_products():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    rows = c.execute("SELECT * FROM products").fetchall()
    colnames = [desc[0] for desc in c.description]
    conn.close()
    
    products = [dict(zip(colnames, row)) for row in rows]
    for p in products:
        for k in ["last_updated", "last_sync"]:
            if p[k]:
                try:
                    p[k] = parse_date(p[k]).isoformat()
                except:
                    pass
    return jsonify(products)

@app.route("/api/products", methods=["POST"])
def add_product():
    data = request.json
    now = datetime.utcnow().isoformat()
    price = fetch_price_from_url(data["url"], data["supplier"]) or 0

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''INSERT INTO products
        (name, category, supplier, url, current_price, last_price, last_updated, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
        (data["name"], data.get("category", ""), data["supplier"], data["url"], price, price, now, "new"))
    conn.commit()
    conn.close()
    return jsonify({"message": "Product added"})

@app.route("/api/products/<int:pid>", methods=["PUT"])
def update_product(pid):
    data = request.json
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT 1 FROM products WHERE product_id = ?", (pid,))
    if not c.fetchone():
        conn.close()
        return jsonify({"error": "Product not found"}), 404

    for field in ["name", "url", "supplier", "category"]:
        if field in data:
            c.execute(f"UPDATE products SET {field} = ? WHERE product_id = ?", (data[field], pid))
    conn.commit()
    conn.close()
    return jsonify({"message": "Product updated"})

@app.route("/api/products/<int:pid>", methods=["DELETE"])
def delete_product(pid):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM products WHERE product_id = ?", (pid,))
    conn.commit()
    conn.close()
    return jsonify({"message": "Product deleted"})

@app.route("/api/products/<int:product_id>/history", methods=["GET"])
def get_price_history(product_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    row = c.execute("SELECT price_history FROM price_history WHERE product_id = ?", (product_id,)).fetchone()
    conn.close()

    if not row or not row[0]:
        return jsonify({"history": []})
    try:
        history = json.loads(row[0])
    except:
        return jsonify({"error": "Invalid price history format"}), 500
    return jsonify({"history": history})

@app.route("/api/suppliers", methods=["GET"])
def get_suppliers():
    with open(SUPPLIER_FILE) as f:
        return jsonify([line.strip() for line in f if line.strip()])

@app.route("/api/suppliers", methods=["POST"])
def add_supplier():
    name = request.json.get("supplier")
    if not name:
        return jsonify({"error": "Supplier name required"}), 400
    with open(SUPPLIER_FILE, "a") as f:
        f.write(f"{name}\n")
    return jsonify({"message": "Supplier added"})

@app.route("/api/categories", methods=["GET"])
def get_categories():
    with open(CATEGORY_FILE) as f:
        return jsonify([line.strip() for line in f if line.strip()])

@app.route("/api/categories", methods=["POST"])
def add_category():
    name = request.json.get("category")
    if not name:
        return jsonify({"error": "Category name required"}), 400
    with open(CATEGORY_FILE, "a") as f:
        f.write(f"{name}\n")
    return jsonify({"message": "Category added"})

@app.route("/api/sync", methods=["POST"])
def sync_prices():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    rows = c.execute("SELECT * FROM products").fetchall()
    columns = [desc[0] for desc in c.description]
    updated = 0
    unchanged = 0

    now = datetime.utcnow().isoformat()

    for row in rows:
        row_dict = dict(zip(columns, row))
        pid = row_dict["product_id"]
        new_price = fetch_price_from_url(row_dict["url"], row_dict["supplier"])

        c.execute("UPDATE products SET last_sync = ? WHERE product_id = ?", (now, pid))

        if new_price is not None and new_price != row_dict["current_price"]:
            updated += 1
            c.execute("""
                UPDATE products SET
                    last_price = ?,
                    current_price = ?,
                    last_updated = ?,
                    status = 'UPDATED'
                WHERE product_id = ?
            """, (row_dict["current_price"], new_price, now, pid))

            prev = c.execute("SELECT price_history FROM price_history WHERE product_id = ?", (pid,)).fetchone()
            history_list = []
            if prev and prev[0]:
                try:
                    history_list = json.loads(prev[0])
                except:
                    history_list = []

            history_list.append({"date": now, "price": new_price})

            c.execute("REPLACE INTO price_history VALUES (?, ?, ?, ?, ?, ?)", (
                pid, now, row_dict["current_price"], new_price,
                new_price - row_dict["current_price"],
                json.dumps(history_list)
            ))
        else:
            unchanged += 1

    conn.commit()
    conn.close()
    return jsonify({"message": "Sync complete", "updated": updated, "unchanged": unchanged})

@app.route("/api/analytics")
def analytics():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    data = c.execute("SELECT category, current_price FROM products WHERE current_price IS NOT NULL").fetchall()
    conn.close()
    result = {}
    for cat, price in data:
        if cat not in result:
            result[cat] = []
        result[cat].append(price)
    result = {k: sum(v)/len(v) for k, v in result.items() if v}
    return jsonify(result)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)
