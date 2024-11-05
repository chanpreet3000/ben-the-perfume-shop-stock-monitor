from typing import List


class ProductOptions:
    def __init__(self, name: str, stock_level: int, is_in_stock: bool, stock_status: str, product_code: str,
                 formatted_price: str):
        self.name = name
        self.stock_level = stock_level
        self.is_in_stock = is_in_stock
        self.stock_status = stock_status
        self.product_code = product_code
        self.formatted_price = formatted_price

    def to_dict(self):
        return {
            'name': self.name,
            'stock_level': self.stock_level,
            'is_in_stock': self.is_in_stock,
            'stock_status': self.stock_status,
            'product_code': self.product_code,
            'formatted_price': self.formatted_price
        }


class ProductData:
    def __init__(self, ean: str, name: str, product_code: str, options: List[ProductOptions],
                 product_url: str):
        self.ean = ean
        self.name = name
        self.product_code = product_code
        self.options = options
        self.product_url = product_url

    def to_dict(self):
        return {
            'ean': self.ean,
            'name': self.name,
            'product_code': self.product_code,
            'options': [option.to_dict() for option in self.options],
            'product_url': self.product_url
        }
