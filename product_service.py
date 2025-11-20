# product_service.py
class ProductService:
    def __init__(self):
        self.products = {
            "1": {"id": "1", "name": "Spotify Premium", "description": "Complete software package with all features", "price": 250, "pixeldrain_link": "https://pixeldrain.com/u/your-file-id-1"},
            "2": {"id": "2", "name": "Basic Software Package", "description": "Essential features for beginners", "price": 250, "pixeldrain_link": "https://pixeldrain.com/u/your-file-id-2"},
            "3": {"id": "3", "name": "Advanced Tools Bundle", "description": "Professional tools for power users", "price": 750, "pixeldrain_link": "https://pixeldrain.com/u/your-file-id-3"}
        }

    def get_products(self):
        return list(self.products.values())

    def get_product(self, product_id):
        return self.products.get(str(product_id))
