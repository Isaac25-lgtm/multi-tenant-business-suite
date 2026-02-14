"""
Utility to auto-fetch product images from the internet using DuckDuckGo image search.
Falls back gracefully if the service is unavailable.
"""
import threading


def fetch_product_image(product_name, category_name=None, search_context='product'):
    """
    Search for a product image URL using DuckDuckGo image search.

    Args:
        product_name: Name of the product (e.g., "Women's Dress", "Iron Sheets")
        category_name: Optional category for better search results
        search_context: Context suffix for the search query
                        ('product' for boutique, 'hardware building material' for hardware)

    Returns:
        str: URL of the first matching image, or None if not found
    """
    try:
        from duckduckgo_search import DDGS

        # Build search query with appropriate context
        query = product_name
        if category_name:
            query = f"{category_name} {product_name}"
        query += f" {search_context}"

        with DDGS() as ddgs:
            results = ddgs.images(
                keywords=query,
                region="wt-wt",
                safesearch="moderate",
                max_results=5
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


def fetch_product_image_async(stock_item_id, product_name, category_name=None, model_class='BoutiqueStock'):
    """
    Fetch a product image in the background and update the database.
    This avoids slowing down the stock creation flow.

    Args:
        stock_item_id: ID of the stock item to update
        product_name: Name of the product
        category_name: Optional category for better search
        model_class: Name of the model class ('BoutiqueStock' or 'HardwareStock')
    """
    from flask import current_app

    app = current_app._get_current_object()

    def _fetch_and_update():
        with app.app_context():
            from app.extensions import db

            # Import the correct model based on model_class parameter
            if model_class == 'HardwareStock':
                from app.models.hardware import HardwareStock
                StockModel = HardwareStock
            else:
                from app.models.boutique import BoutiqueStock
                StockModel = BoutiqueStock

            # Use appropriate search context based on model type
            if model_class == 'HardwareStock':
                search_context = 'hardware building material'
            else:
                search_context = 'product'
            image_url = fetch_product_image(product_name, category_name, search_context)
            if image_url:
                item = StockModel.query.get(stock_item_id)
                if item:
                    item.image_url = image_url
                    db.session.commit()
                    print(f"[Image Fetch] Found image for '{product_name}': {image_url[:80]}...")
            else:
                print(f"[Image Fetch] No image found for '{product_name}'")

    thread = threading.Thread(target=_fetch_and_update, daemon=True)
    thread.start()
