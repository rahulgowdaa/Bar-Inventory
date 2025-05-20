import csv
from models import db, Brand, BottleVolume, AlcoholCategory, Product
from sqlalchemy.exc import IntegrityError

def insert_bottles_from_csv(csv_path):
    with open(csv_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        print("CSV Headers:", reader.fieldnames)  # Add this line

        for row in reader:
            name = row["Name"].strip()
            volume_ml = int(row["ML"])
            category_name = row["Category"].strip().capitalize()

            # 1. Add or fetch category
            category = AlcoholCategory.query.filter_by(category_name=category_name).first()
            if not category:
                category = AlcoholCategory(category_name=category_name)
                db.session.add(category)
                db.session.commit()

            # 2. Add or fetch volume
            volume = BottleVolume.query.filter_by(volume_ml=volume_ml).first()
            if not volume:
                volume = BottleVolume(volume_ml=volume_ml)
                db.session.add(volume)
                db.session.commit()

            # 3. Add or fetch brand
            brand = Brand.query.filter_by(brand_name=name).first()
            if not brand:
                brand = Brand(brand_name=name)
                db.session.add(brand)
                db.session.commit()

            # 4. Add product (if not exists)
            product_exists = Product.query.filter_by(
                product_name=name,
                brand_id=brand.brand_id,
                category_id=category.category_id,
                volume_id=volume.volume_id
            ).first()

            if not product_exists:
                product = Product(
                    product_name=name,
                    brand_id=brand.brand_id,
                    category_id=category.category_id,
                    volume_id=volume.volume_id
                )
                db.session.add(product)

    try:
        db.session.commit()
        print("✅ All bottles inserted successfully.")
    except IntegrityError as e:
        db.session.rollback()
        print("❌ Integrity Error:", e)

# Usage
if __name__ == "__main__":
    from app import app  # or from your Flask project entry point
    with app.app_context():
        insert_bottles_from_csv("bottles.csv")
