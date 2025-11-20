from typing import Dict, List

class ProductService:
    def __init__(self):
        self.products = {
            "1": {
                "id": "1",
                "name": "Spotify Premium",
                "description": "Complete software package with all features",
                "price": 250,
                "pixeldrain_link": "https://pixeldrain.com/u/your-file-id-1"
            },
            "2": {
                "id": "2",
                "name": "Basic Software Package",
                "description": "Essential features for beginners",
                "price": 250,
                "pixeldrain_link": "https://pixeldrain.com/u/your-file-id-2"
            },
            "3": {
                "id": "3",
                "name": "Advanced Tools Bundle",
                "description": "Professional tools for power users",
                "price": 750,
                "pixeldrain_link": "https://pixeldrain.com/u/your-file-id-3"
            }
        }

    def get_products(self) -> List[Dict]:
        return list(self.products.values())

    def get_product(self, product_id: str) -> Dict:
        return self.products.get(str(product_id))

    def generate_download_link(self, product_id: str) -> str | None:
        product = self.get_product(product_id)
        if not product:
            return None
        return product["pixeldrain_link"]

    def add_product(self, product_data: Dict):
        new_id = str(len(self.products) + 1)
        product_data["id"] = new_id
        self.products[new_id] = product_data
        return new_id
