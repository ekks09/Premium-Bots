import os
from typing import Dict, List

class ProductService:
    def __init__(self):
        self.products = {
            '1': {
                'id': '1',
                'name': 'Spotify Premium',
                'description': 'Complete software package with all features',
                'price': 250,
                'pixeldrain_link': 'https://pixeldrain.com/u/your-file-id-1'
            },
            '2': {
                'id': '2', 
                'name': 'Basic Software Package',
                'description': 'Essential features for beginners',
                'price': 250,
                'pixeldrain_link': 'https://pixeldrain.com/u/your-file-id-2'
            },
            '3': {
                'id': '3',
                'name': 'Advanced Tools Bundle',
                'description': 'Professional tools for power users',
                'price': 750,
                'pixeldrain_link': 'https://pixeldrain.com/u/your-file-id-3'
            }
        }
    
    def get_products(self) -> List[Dict]:
        """Get all available products"""
        return list(self.products.values())
    
    def get_product(self, product_id: str) -> Dict:
        """Get specific product by ID"""
        return self.products.get(product_id)
    
    def generate_download_link(self, product_id: str) -> str:
        """Generate PixelDrain download link for purchased product"""
        product = self.get_product(product_id)
        if product:
            return product['pixeldrain_link']
        return "Product not found"
    
    def add_product(self, product_data: Dict):
        """Add new product (for admin use)"""
        product_id = str(len(self.products) + 1)
        product_data['id'] = product_id
        self.products[product_id] = product_data
        return product_id