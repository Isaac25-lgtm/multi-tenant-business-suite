"""
Utility to auto-fetch product images from the internet using DuckDuckGo image search.
Falls back gracefully if the service is unavailable.
"""
import threading


def fetch_product_image(product_name, category_name=None):
    """
    Search for a product image URL using DuckDuckGo image search.

    Args:
        product_name: Name of the product (e.g., "Women's Dress")
        category_name: Optional category for better search results

    Returns:
        str: URL of the first matching image, or None if not found
    """
    try:
        from duckduckgo_search import DDGS

        # Build search query - include "boutique" context for better results
        query = product_name
        if category_name:
            query = f"{category_name} {product_name}"
        query += " product"

        with DDGS() as ddgs:
            results = ddgs.images(
                keywords=query,
                region="wt-wt",
                safesearch="moderate",
                max_results=3
            )

            for result in results:
                image_url = result.get("image", "")
                # Filter for reasonable image URLs
                if image_url and image_url.startswith("http"):
                    return image_url

    except ImportError:
        print("[Image Fetch] duckduckgo-search not installed. Run: pip install duckduckgo-search")
    except Exception as e:
        print(f"[Image Fetch] Could not fetch image for '{product_name}': {e}")

    return None


def fetch_product_image_async(stock_item_id, product_name, category_name=None):
    """
    Fetch a product image in the background and update the database.
    This avoids slowing down the stock creation flow.

    Args:
        stock_item_id: ID of the BoutiqueStock item to update
        product_name: Name of the product
        category_name: Optional category for better search
    """
    from flask import current_app

    app = current_app._get_current_object()

    def _fetch_and_update():
        with app.app_context():
            from app.extensions import db
            from app.models.boutique import BoutiqueStock

            image_url = fetch_product_image(product_name, category_name)
            if image_url:
                item = BoutiqueStock.query.get(stock_item_id)
                if item:
                    item.image_url = image_url
                    db.session.commit()
                    print(f"[Image Fetch] Found image for '{product_name}': {image_url[:80]}...")
            else:
                print(f"[Image Fetch] No image found for '{product_name}'")

    thread = threading.Thread(target=_fetch_and_update, daemon=True)
    thread.start()
