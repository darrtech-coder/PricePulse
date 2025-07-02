import requests
from bs4 import BeautifulSoup
import re
import json

def fetch_price_from_url(url, supplier):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        }
        response = requests.get(url, headers=headers, timeout=15)
        html = response.text
        soup = BeautifulSoup(html, "html.parser")
        supplier = supplier.lower()

        # === ALIEXPRESS ===
        if "aliexpress" in supplier or "aliexpress.com" in url:
            price_meta = soup.find("meta", {"itemprop": "price"})
            if price_meta and price_meta.get("content"):
                return float(price_meta["content"])
            match = re.search(r'"salePrice":\s*\{"formattedValue":"\$([\d\.]+)"\}', html)
            if match:
                return float(match.group(1))

        # === NEWEGG ===
        if "newegg" in supplier or "newegg.com" in url:
            for script in soup.find_all("script", type="application/ld+json"):
                try:
                    data = json.loads(script.string.strip())
                    if isinstance(data, dict) and "offers" in data:
                        offers = data["offers"]
                        if isinstance(offers, dict) and "price" in offers:
                            return float(offers["price"])
                except Exception:
                    continue

            # Fallback: Look for price in visible HTML
            price_div = soup.find("li", class_="price-current")
            if price_div:
                match = re.search(r"\$([\d,.]+)", price_div.text)
                if match:
                    return float(match.group(1).replace(",", ""))

        # === SHOPIFY-LIKE ===
        if any(key in supplier for key in [
            "shopify", "spocket", "dsers", "zendrop", "cjdropshipping", "modalyst", "autods", "shopify collective"
        ]):
            meta_price = soup.find("meta", {"property": "product:price:amount"})
            if meta_price and meta_price.get("content"):
                return float(meta_price["content"])
            for script in soup.find_all("script", type="application/ld+json"):
                try:
                    data = json.loads(script.string.strip())
                    if isinstance(data, dict) and "offers" in data:
                        offers = data["offers"]
                        if isinstance(offers, dict) and "price" in offers:
                            return float(offers["price"])
                except:
                    continue
            span = soup.find("span", class_="price")
            if span:
                match = re.search(r"([\d,.]+)", span.text)
                if match:
                    return float(match.group(1).replace(",", ""))

        # === WOOCOMMERCE ===
        if "woocommerce" in supplier:
            meta_price = soup.find("meta", {"property": "product:price:amount"})
            if meta_price and meta_price.get("content"):
                return float(meta_price["content"])
            for script in soup.find_all("script", type="application/ld+json"):
                try:
                    data = json.loads(script.string.strip())
                    if isinstance(data, dict) and "offers" in data:
                        offers = data["offers"]
                        if isinstance(offers, dict) and "price" in offers:
                            return float(offers["price"])
                except:
                    continue
            span = soup.find("span", class_="woocommerce-Price-amount")
            if span:
                match = re.search(r"([\d,.]+)", span.text)
                if match:
                    return float(match.group(1).replace(",", ""))

        # === OTHERS (Fallback) ===
        if "price" in html.lower():
            match = re.search(r'"price"\s*:\s*"?([\d.]+)"?', html)
            if match:
                return float(match.group(1))

    except Exception as e:
        print(f"[ERROR] {supplier} scraping failed: {e}")
    return None
