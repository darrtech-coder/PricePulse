# 🛒 PricePulse

A lightweight Flask-based web app for tracking and managing product prices from supplier URLs. It periodically checks for price updates, maintains historical pricing data, and allows users to monitor price changes over time.

---

## 🚀 Features

✅ **Add New Products**  
- Add products by name, category, supplier, and URL  
- Automatically fetches the current price upon creation

✅ **View Product List**  
- See a table of all products with current price, last price, last sync time, and status (e.g., `UPDATED`, `UNCHANGED`, `new`)

✅ **Automatic Price Syncing**  
- Fetches latest prices via a background sync
- Updates product records if prices change
- Sync status and timestamps tracked

✅ **Price History Tracking**  
- Maintains a per-product price history in `product_history.xlsx`
- Historical data updated on each sync
- Frontend allows users to **view price history** for each product

✅ **JSON API**  
- `/api/products [GET]`: List all products  
- `/api/products [POST]`: Add a new product  
- `/api/products/<product_id>/history [GET]`: Get price history for a product  
- `/api/sync [POST]`: Trigger price sync

---

## 📁 Project Structure

```
├── app.py                # Flask app with routes
├── thread.py             # Background sync logic
├── product_data.xlsx     # Main product database
├── product_history.xlsx  # Historical price tracking
├── templates/
│   └── index.html        # Frontend interface
├── static/
│   └── style.css         # Optional styling
```

---

## 🛠️ Installation

```bash
pip install flask pandas openpyxl requests
```

Start the server:

```bash
python app.py
```

Open your browser at [http://localhost:5000](http://localhost:5000)

---

## 🔮 Roadmap

Here’s what's planned for future development:

- [ ] **Scheduled Background Sync (cron-like behavior)**  
  Run automatic price syncs every X hours/days

- [ ] **Email Notifications for Price Drops**  
  Notify users when prices fall below a threshold

- [ ] **Import/Export Support**  
  Upload or download product data via CSV/Excel

- [ ] **User Authentication**  
  Secure endpoints and allow personalized tracking

- [ ] **Price Charting (Graph View)**  
  Show historical price changes as line graphs

- [ ] **Tagging and Filtering Products**  
  Group and search products by tags or keywords

---

## 📌 Notes

- The app currently works best with supplier websites that return prices in a consistent HTML structure
- You may need to customize `fetch_price_from_url()` for each new supplier