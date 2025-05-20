from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, Stock, Product, Brand, AlcoholCategory, StockUpdate
from datetime import datetime
from sqlalchemy.orm import joinedload

inventory_bp = Blueprint('inventory', __name__)

@inventory_bp.route("/inventory", methods=["GET"])
@login_required
def inventory():
    org_id = current_user.org_id  # Get user's organization

    brands = Brand.query.all()
    categories = AlcoholCategory.query.all()

    search = request.args.get("search", "")
    category_id = request.args.get("category", "")
    brand_id = request.args.get("brand", "")

    query = db.session.query(Product).options(
        joinedload(Product.brand),
        joinedload(Product.category),
        joinedload(Product.volume),
        joinedload(Product.stock)
    ).filter(Product.org_id == org_id)  # 🔒 Filter by org_id

    if search:
        query = query.filter(Product.product_name.ilike(f"%{search}%"))
    if category_id:
        query = query.filter(Product.category_id == int(category_id))
    if brand_id:
        query = query.filter(Product.brand_id == int(brand_id))

    products = query.all()

    return render_template(
        "inventory.html",
        stock_items=products,
        brands=brands,
        categories=categories
    )


@inventory_bp.route("/inventory/bulk_update", methods=["POST"])
@login_required
def bulk_update_inventory():
    if current_user.role not in ["admin", "manager"]:
        flash("Permission denied.")
        return redirect(url_for("inventory.inventory"))

    user_id = current_user.user_id
    org_id = current_user.org_id

    try:
        if "update_single" in request.form:
            # Individual update
            product_id = int(request.form["update_single"])
            field_name = f"quantity[{product_id}]"
            new_quantity = int(request.form.get(field_name, 0))

            product = Product.query.filter_by(product_id=product_id, org_id=org_id).first()
            if not product:
                flash("❌ Unauthorized product access.")
                return redirect(url_for("inventory.inventory"))

            stock = Stock.query.filter_by(product_id=product_id, org_id=org_id).first()
            previous_quantity = stock.quantity if stock else 0

            if stock:
                stock.quantity = new_quantity
                stock.last_updated = datetime.now()
                stock.last_updated_by = user_id
            else:
                stock = Stock(
                    product_id=product_id,
                    org_id=org_id,
                    quantity=new_quantity,
                    last_updated=datetime.now(),
                    last_updated_by=user_id
                )
                db.session.add(stock)

            update_log = StockUpdate(
                product_id=product_id,
                previous_quantity=previous_quantity,
                new_quantity=new_quantity,
                updated_by=user_id
            )
            db.session.add(update_log)
            db.session.commit()
            flash(f"✅ Stock updated for product ID {product_id}.")

        elif "update_all" in request.form:
            # Bulk update
            for field_name, value in request.form.items():
                if field_name.startswith("quantity["):
                    product_id = int(field_name.split("[")[1].split("]")[0])
                    new_quantity = int(value)

                    product = Product.query.filter_by(product_id=product_id, org_id=org_id).first()
                    if not product:
                        continue  # Skip products not belonging to current org

                    stock = Stock.query.filter_by(product_id=product_id, org_id=org_id).first()
                    previous_quantity = stock.quantity if stock else 0

                    if stock:
                        if stock.quantity != new_quantity:
                            stock.quantity = new_quantity
                            stock.last_updated = datetime.now()
                            stock.last_updated_by = user_id
                    else:
                        stock = Stock(
                            product_id=product_id,
                            org_id=org_id,
                            quantity=new_quantity,
                            last_updated=datetime.now(),
                            last_updated_by=user_id
                        )
                        db.session.add(stock)

                    update_log = StockUpdate(
                        product_id=product_id,
                        previous_quantity=previous_quantity,
                        new_quantity=new_quantity,
                        updated_by=user_id
                    )
                    db.session.add(update_log)

            db.session.commit()
            flash("✅ Bulk stock update successful.")

    except Exception as e:
        db.session.rollback()
        flash("❌ Error updating stock.")
        print(f"[Stock Update Error] {e}")

    return redirect(url_for("inventory.inventory"))
