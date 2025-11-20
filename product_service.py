from typing import List, Dict, Optional

class ProductService:
    def __init__(self):
        self.products = {
            '1': {
                'id': '1',
                'name': '🎵 Spotify Premium Account',
                'description': 'Premium Spotify account with full features - 6 months warranty',
                'price': 250,
                'pixeldrain_link': 'https://pixeldrain.com/u/spotify-premium-account',
                'category': 'Entertainment'
            },
            '2': {
                'id': '2',
                'name': '💼 Basic Software Suite',
                'description': 'Essential software tools for productivity and daily use',
                'price': 350,
                'pixeldrain_link': 'https://pixeldrain.com/u/basic-software-suite',
                'category': 'Software'
            },
            '3': {
                'id': '3',
                'name': '🚀 Advanced Tools Bundle',
                'description': 'Professional tools bundle for power users and developers',
                'price': 750,
                'pixeldrain_link': 'https://pixeldrain.com/u/advanced-tools-bundle',
                'category': 'Software'
            },
            '4': {
                'id': '4',
                'name': '🎬 Video Editing Pack',
                'description': 'Complete video editing software with plugins and assets',
                'price': 500,
                'pixeldrain_link': 'https://pixeldrain.com/u/video-editing-pack',
                'category': 'Creative'
            }
        }

    def get_products(self) -> List[Dict]:
        """Get all available products."""
        return list(self.products.values())

    def get_product(self, product_id: str) -> Optional[Dict]:
        """Get a specific product by ID."""
        return self.products.get(str(product_id))

    def get_products_by_category(self, category: str) -> List[Dict]:
        """Get products filtered by category."""
        return [product for product in self.products.values() if product.get('category') == category]

    def generate_download_link(self, product_id: str) -> str:
        """Generate download link for purchased product."""
        product = self.get_product(product_id)
        if product:
            return product['pixeldrain_link']
        return "Product not found"

    def add_product(self, product_data: Dict) -> str:
        """Add a new product (admin function)."""
        new_id = str(max(int(pid) for pid in self.products.keys()) + 1)
        product_data['id'] = new_id
        self.products[new_id] = product_data
        return new_id

    def update_product(self, product_id: str, updates: Dict) -> bool:
        """Update an existing product (admin function)."""
        if product_id in self.products:
            self.products[product_id].update(updates)
            return True
        return False
