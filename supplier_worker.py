# supplier_worker.py

import os
import time
import random
import redis
from agents.supplier_agent import register_supplier, list_suppliers, generate_product

# Possible tags for products
TAGS = [
    "eco-friendly", "quiet", "budget", "fast-delivery",
    "premium", "limited-edition", "new-arrival"
]

# Read Redis connection info from env
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)

# ───────────────────────────────────────────────────────────────────────────────
# Supplier Classes and Initial Product Definitions
# ───────────────────────────────────────────────────────────────────────────────
SUPPLIER_CLASSES = [
    "Travel",
    "Electronics",
    "Events",
    "Financial Services",
    "Clothing",
    "Home",
    "Books",
    "Food",
    "Health",
    "Automotive"
]

PRODUCTS_BY_CLASS = {
    "Travel": [
        "Flight to Paris", "Hotel in Tokyo", "Car Rental California",
        "Cruise Caribbean", "Travel Insurance", "Tour Guide Italy",
        "Rail Pass Europe", "Theme Park Tickets", "Airport Lounge Access",
        "City Sightseeing Bus"
    ],
    "Electronics": [
        "Smartphone X12", "Laptop Pro 15", "Wireless Earbuds",
        "Smartwatch Series 5", "4K OLED TV", "Bluetooth Speaker",
        "Drone Aerial", "Gaming Console Z", "Portable Charger",
        "Action Camera"
    ],
    "Events": [
        "Concert Ticket", "Festival Pass", "Theater Matinee",
        "Sports Game VIP", "Conference Admission", "Art Expo Entry",
        "Workshop Workshop", "Film Premiere", "Charity Gala",
        "Networking Meetup"
    ],
    "Financial Services": [
        "Savings Account", "Home Loan", "Car Insurance",
        "Credit Card Platinum", "Investment Portfolio",
        "Retirement Plan", "Tax Advisory", "Mortgage Refinance",
        "Student Loan", "Health Insurance"
    ],
    "Clothing": [
        "Designer T-Shirt", "Jeans Classic", "Running Shoes",
        "Leather Jacket", "Summer Dress", "Winter Coat",
        "Baseball Cap", "Sneakers", "Sunglasses", "Scarf"
    ],
    "Home": [
        "Sofa Set", "Dining Table", "Queen Bed",
        "LED Lamp", "Rug 5x8", "Wardrobe",
        "Kitchen Mixer", "Coffee Maker", "Vacuum Cleaner",
        "Air Purifier"
    ],
    "Books": [
        "Bestseller Novel", "Science Textbook", "Children's Book",
        "Cookbook Gourmet", "History Biography", "Graphic Novel",
        "Language Guide", "Photography Book", "Poetry Collection",
        "Travel Guide"
    ],
    "Food": [
        "Organic Coffee Beans", "Gourmet Chocolate", "Artisan Bread",
        "Premium Olive Oil", "Spice Set", "Cheese Sampler",
        "Exotic Tea", "Wine Bottle", "Canned Truffles", "Fruit Basket"
    ],
    "Health": [
        "Vitamin D Supplements", "Yoga Mat", "Fitness Tracker",
        "Protein Powder", "First Aid Kit", "Thermometer",
        "Massage Oil", "Healthy Meal Plan", "Blood Pressure Monitor",
        "Prescription Delivery"
    ],
    "Automotive": [
        "Car Wash Pass", "Oil Change Service", "Tire Rotation",
        "GPS Navigation Unit", "Dash Cam", "Seat Covers",
        "Bluetooth Car Kit", "Roof Rack", "Motor Oil 5W-30",
        "Jump Starter"
    ]
}

# Generate one supplier ID per class
SUPPLIERS = [f"supplier_{cls.lower().replace(' ', '_')}" for cls in SUPPLIER_CLASSES]

# How often (seconds) to generate additional products
PRODUCT_INTERVAL = 10

# ───────────────────────────────────────────────────────────────────────────────
# Initialization: register suppliers and seed initial products
# ───────────────────────────────────────────────────────────────────────────────
for sup, cls in zip(SUPPLIERS, SUPPLIER_CLASSES):
    register_supplier(sup)
    # Seed ten products for this supplier/class
    for product_name in PRODUCTS_BY_CLASS[cls]:
        attrs = {
            "name": product_name,
            "category": cls,
            "price": round(random.uniform(10, 500), 2),
            "tags": random.sample(TAGS, k=2)
        }
        prod = generate_product(sup, attrs)
        print(f"• [Seed] {sup} -> {prod['product_id']} ({product_name})")

print(f"▶️ Seeded {len(SUPPLIERS)*10} products from {len(SUPPLIERS)} suppliers.")


# ───────────────────────────────────────────────────────────────────────────────
# Main loop: optionally generate additional random products
# ───────────────────────────────────────────────────────────────────────────────
def run_supplier_worker():
    while True:
        suppliers = list_suppliers()
        if not suppliers:
            print("No suppliers registered; skipping product generation")
        else:
            sup = random.choice(suppliers)
            cls = SUPPLIER_CLASSES[SUPPLIERS.index(sup)]
            product_name = random.choice(PRODUCTS_BY_CLASS[cls])
            attrs = {
                "name": product_name,
                "category": cls,
                "price": round(random.uniform(10, 500), 2),
                "tags": random.sample(TAGS, k=2)
            }
            prod = generate_product(sup, attrs)
            print(f"• [Rand] {sup} -> {prod['product_id']} ({product_name})")
        time.sleep(PRODUCT_INTERVAL)


if __name__ == "__main__":
    run_supplier_worker()