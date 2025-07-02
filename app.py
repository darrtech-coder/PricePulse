# app.py
from flask import Flask, jsonify, request, send_file, render_template
import pandas as pd
import os
import json
from dateutil.parser import parse as parse_date
from utils import fetch_price_from_url
import thread
thread.start_auto_sync()


app = Flask(__name__)

PRODUCT_FILE = "products.xlsx"
SUPPLIER_FILE = "suppliers.txt"
CATEGORY_FILE = "categories.txt"
HISTORY_FILE = "product_history.xlsx"

# Initialize Excel and supporting files if missing
if not os.path.exists(PRODUCT_FILE):
    df = pd.DataFrame(columns=[
        "Product ID", "Name", "Category", "Supplier", "URL",
        "Current Price", "Last Price", "Last Updated", "Last Sync", "Status"
    ])
    df.to_excel(PRODUCT_FILE, index=False)

if not os.path.exists(SUPPLIER_FILE):
    with open(SUPPLIER_FILE, "w") as f:
        f.write("AliExpress\nWooCommerce")

if not os.path.exists(CATEGORY_FILE):
    with open(CATEGORY_FILE, "w") as f:
        f.write("Electronics\nClothing\nAccessories")



@app.route("/")
def home():
    return render_template("index.html")

@app.route("/api/products", methods=["GET"])
def get_products():
    df = pd.read_excel(PRODUCT_FILE)
    df = df.where(pd.notnull(df), None)
    if "Last Updated" in df.columns:
        def clean_date(val):
            if pd.isnull(val): return None
            if isinstance(val, str):
                try: val = parse_date(val)
                except: return val
            try: return val.isoformat()
            except: return None
        df["Last Updated"] = df["Last Updated"].apply(clean_date)
    return jsonify(df.to_dict(orient="records"))

@app.route("/api/products", methods=["POST"])
def add_product():
    data = request.json
    df = pd.read_excel(PRODUCT_FILE)
    new_id = df["Product ID"].max() + 1 if not df.empty else 1
    new_row = {
        "Product ID": new_id,
        "Name": data["name"],
        "Category": data.get("category", ""),
        "Supplier": data["supplier"],
        "URL": data["url"],
        "Current Price": fetch_price_from_url(data["url"], data["supplier"]) or 0,  # Set to 0 initially
        "Last Price": fetch_price_from_url(data["url"], data["supplier"]) or 0,     # Same as current price
        "Last Updated": pd.Timestamp.now(),  # Current datetime
        "Status": "new"
    }
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    df.to_excel(PRODUCT_FILE, index=False)
    return jsonify({"message": "Product added"})

@app.route("/api/products/<int:pid>", methods=["PUT"])
def update_product(pid):
    data = request.json
    df = pd.read_excel(PRODUCT_FILE)
    if pid not in df["Product ID"].values:
        return jsonify({"error": "Product not found"}), 404
    idx = df.index[df["Product ID"] == pid][0]
    for field in ["Name", "URL", "Supplier", "Category"]:
        if field in data:
            df.at[idx, field] = data[field]
    df.to_excel(PRODUCT_FILE, index=False)
    return jsonify({"message": "Product updated"})

@app.route("/api/products/<int:pid>", methods=["DELETE"])
def delete_product(pid):
    df = pd.read_excel(PRODUCT_FILE)
    df = df[df["Product ID"] != pid]
    df.to_excel(PRODUCT_FILE, index=False)
    return jsonify({"message": "Product deleted"})



@app.route("/api/products/<int:product_id>/history", methods=["GET"])
def get_price_history(product_id):
    df = pd.read_excel(HISTORY_FILE)

    # Find the product row
    product_row = df[df["Product ID"] == product_id]
    if product_row.empty:
        return jsonify({"error": "Product not found"}), 404

    # Extract and parse the price history
    raw_history = product_row.iloc[0].get("Price History")
    if pd.isna(raw_history) or not raw_history:
        return jsonify({"history": []})  # Return empty if missing

    try:
        history = json.loads(raw_history)
    except Exception:
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

@app.route("/api/export")
def export_excel():
    return send_file(PRODUCT_FILE, as_attachment=True)

@app.route("/api/sync", methods=["POST"])
def sync_prices():
    df = pd.read_excel(PRODUCT_FILE)
    updated = 0
    unchanged = 0

    history_file = "product_history.xlsx"
    if os.path.exists(history_file):
        history_df = pd.read_excel(history_file)
    else:
        history_df = pd.DataFrame(columns=["Product ID", "Date", "Old Price", "New Price", "Change", "Price History"])

    for i, row in df.iterrows():
        pid = row["Product ID"]
        url = row["URL"]
        supplier = row["Supplier"]
        current_price = row["Current Price"]

        new_price = fetch_price_from_url(url, supplier)
        now = pd.Timestamp.now()
        df.at[i, "Last Sync"] = now

        if new_price is not None and new_price != current_price:
            df.at[i, "Last Price"] = current_price
            df.at[i, "Current Price"] = new_price
            df.at[i, "Last Updated"] = now
            df.at[i, "Status"] = "UPDATED"
            updated += 1

            # Get previous history
            existing_row = history_df[history_df["Product ID"] == pid]
            if not existing_row.empty:
                try:
                    history_list = json.loads(existing_row.iloc[0]["Price History"])
                except Exception:
                    history_list = []
                # Drop the old entry
                history_df = history_df[history_df["Product ID"] != pid]
            else:
                history_list = []

            # Append new price record
            history_list.append({"date": now.isoformat(), "price": new_price})

            # Save updated row
            updated_row = {
                "Product ID": pid,
                "Date": now,
                "Old Price": current_price,
                "New Price": new_price,
                "Change": new_price - current_price,
                "Price History": json.dumps(history_list)
            }

            history_df = pd.concat([history_df, pd.DataFrame([updated_row])], ignore_index=True)
        else:
            unchanged += 1

    df.to_excel(PRODUCT_FILE, index=False)
    history_df.to_excel(history_file, index=False)

    return jsonify({
        "message": "Sync complete",
        "updated": updated,
        "unchanged": unchanged
    })


@app.route("/api/sync/status", methods=["GET"])
def get_sync_status():
    try:
        with open("sync_status.txt") as f:
            return jsonify({"status": f.read().strip()})
    except FileNotFoundError:
        return jsonify({"status": "disabled"})

@app.route("/api/sync/status", methods=["POST"])
def set_sync_status():
    status = request.json.get("status")
    if status not in ["enabled", "disabled"]:
        return jsonify({"error": "Invalid status"}), 400
    with open("sync_status.txt", "w") as f:
        f.write(status)
    return jsonify({"message": f"Auto-sync {status}"})

@app.route("/api/analytics")
def analytics():
    df = pd.read_excel(PRODUCT_FILE)
    result = df.groupby("Category")["Current Price"].mean().dropna().to_dict()
    return jsonify(result)

@app.route("/api/export/<fmt>")
def export_data(fmt):
    df = pd.read_excel(PRODUCT_FILE)
    if fmt == "csv":
        path = "products.csv"
        df.to_csv(path, index=False)
    else:
        path = "products.xlsx"
        df.to_excel(path, index=False)
    return send_file(path, as_attachment=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)
