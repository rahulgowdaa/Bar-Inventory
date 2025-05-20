from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, Product, Brand, AlcoholCategory, BottleVolume, Price
from datetime import datetime
from sqlalchemy.orm import joinedload
import csv
import io

admin_inventory_bp = Blueprint('admin_inventory', __name__)

def is_admin():
    return current_user.is_authenticated and current_user.role == "admin"

@admin_inventory_bp.route("/admin/products")
@login_required
def manage_products():
    if not is_admin():
        flash("Admins only!")
        return redirect(url_for("inventory.inventory"))

    products = Product.query.options(
        joinedload(Product.brand),
        joinedload(Product.category),
        joinedload(Product.volume)
    ).filter(Product.org_id == current_user.org_id).all()

    brands = Brand.query.all()
    categories = AlcoholCategory.query.all()
    volumes = BottleVolume.query.all()

    return render_template("manage_products.html", products=products, brands=brands, categories=categories, volumes=volumes)

@admin_inventory_bp.route("/admin/products/add", methods=["POST"])
@login_required
def add_product():
    if not is_admin():
        flash("Admins only!")
        return redirect(url_for("inventory.inventory"))

    try:
        name = request.form["product_name"].strip()
        price = float(request.form["price"])
        volume_id = int(request.form["volume_id"])

        # Check for new or selected brand
        brand_id = request.form.get("brand_id")
        new_brand_name = request.form.get("new_brand", "").strip()

        if new_brand_name:
            brand = Brand.query.filter_by(brand_name=new_brand_name).first()
            if not brand:
                brand = Brand(brand_name=new_brand_name)
                db.session.add(brand)
                db.session.flush()
            brand_id = brand.brand_id
        elif brand_id:
            brand_id = int(brand_id)
        else:
            flash("Please select or enter a brand.")
            return redirect(url_for("admin_inventory.manage_products"))

        # Check for new or selected category
        category_id = request.form.get("category_id")
        new_cat_name = request.form.get("new_category", "").strip()

        if new_cat_name:
            category = AlcoholCategory.query.filter_by(category_name=new_cat_name).first()
            if not category:
                category = AlcoholCategory(category_name=new_cat_name)
                db.session.add(category)
                db.session.flush()
            category_id = category.category_id
        elif category_id:
            category_id = int(category_id)
        else:
            flash("Please select or enter a category.")
            return redirect(url_for("admin_inventory.manage_products"))

        # Add new product
        new_product = Product(
            product_name=name,
            brand_id=brand_id,
            category_id=category_id,
            volume_id=volume_id,
            org_id=current_user.org_id
        )
        db.session.add(new_product)
        db.session.flush()

        new_price = Price(
            product_id=new_product.product_id,
            price=price,
            updated_by=current_user.user_id
        )
        db.session.add(new_price)
        db.session.commit()
        flash("✅ Product added successfully.")
    except Exception as e:
        db.session.rollback()
        flash("❌ Error adding product.")
        print("[Add Product Error]", e)

    return redirect(url_for("admin_inventory.manage_products"))

@admin_inventory_bp.route("/admin/products/edit/<int:product_id>", methods=["POST"])
@login_required
def edit_product(product_id):
    if not is_admin():
        flash("Admins only!")
        return redirect(url_for("inventory.inventory"))

    try:
        product = Product.query.get_or_404(product_id)
        if product.org_id != current_user.org_id:
            flash("Unauthorized access.")
            return redirect(url_for("inventory.inventory"))

        product.product_name = request.form["product_name"].strip()
        product.brand_id = int(request.form["brand_id"])
        product.category_id = int(request.form["category_id"])
        product.volume_id = int(request.form["volume_id"])

        price_val = request.form.get("price")
        if price_val:
            price = Price.query.filter_by(product_id=product_id).order_by(Price.effective_date.desc()).first()
            if price:
                price.price = float(price_val)
                price.effective_date = datetime.now()
            else:
                new_price = Price(
                    product_id=product_id,
                    price=float(price_val),
                    updated_by=current_user.user_id
                )
                db.session.add(new_price)

        db.session.commit()
        flash("Product updated.")
    except Exception as e:
        db.session.rollback()
        flash("Error updating product.")
        print(e)

    return redirect(url_for("admin_inventory.manage_products"))

@admin_inventory_bp.route("/admin/products/delete/<int:product_id>", methods=["POST"])
@login_required
def delete_product(product_id):
    if not is_admin():
        flash("Admins only!")
        return redirect(url_for("inventory.inventory"))

    try:
        product = Product.query.get_or_404(product_id)
        if product.org_id != current_user.org_id:
            flash("Unauthorized deletion.")
            return redirect(url_for("admin_inventory.manage_products"))

        db.session.delete(product)
        db.session.commit()
        flash("Product deleted.")
    except Exception as e:
        db.session.rollback()
        flash("Error deleting product.")
        print(e)

    return redirect(url_for("admin_inventory.manage_products"))

@admin_inventory_bp.route("/admin/products/upload", methods=["POST"])
@login_required
def upload_products_csv():
    if not is_admin():
        flash("Admins only!")
        return redirect(url_for("inventory.inventory"))

    file = request.files.get("csv_file")
    if not file:
        flash("No file uploaded.")
        return redirect(url_for("admin_inventory.manage_products"))

    try:
        stream = io.StringIO(file.stream.read().decode("UTF8"))
        reader = csv.DictReader(stream)

        for row in reader:
            name = row["Name"].strip()
            ml = int(row["ML"].strip())
            category_name = row["Category"].strip()

            brand = Brand.query.filter_by(brand_name=name).first()
            if not brand:
                brand = Brand(brand_name=name)
                db.session.add(brand)
                db.session.flush()

            category = AlcoholCategory.query.filter_by(category_name=category_name).first()
            if not category:
                category = AlcoholCategory(category_name=category_name)
                db.session.add(category)
                db.session.flush()

            volume = BottleVolume.query.filter_by(volume_ml=ml).first()
            if not volume:
                volume = BottleVolume(volume_ml=ml)
                db.session.add(volume)
                db.session.flush()

            existing_product = Product.query.filter_by(
                product_name=name,
                brand_id=brand.brand_id,
                category_id=category.category_id,
                volume_id=volume.volume_id,
                org_id=current_user.org_id
            ).first()

            if not existing_product:
                product = Product(
                    product_name=name,
                    brand_id=brand.brand_id,
                    category_id=category.category_id,
                    volume_id=volume.volume_id,
                    org_id=current_user.org_id
                )
                db.session.add(product)
                db.session.flush()

                price = Price(
                    product_id=product.product_id,
                    price=0.00,
                    updated_by=current_user.user_id
                )
                db.session.add(price)

        db.session.commit()
        flash("Products uploaded successfully.")
    except Exception as e:
        db.session.rollback()
        flash("Error uploading CSV.")
        print(e)

    return redirect(url_for("admin_inventory.manage_products"))