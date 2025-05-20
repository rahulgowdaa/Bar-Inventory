# sales.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, make_response, Response
from flask_login import login_required, current_user
from models import db, Product, Sale, Price, Stock, StockUpdate
from datetime import datetime, date
from sqlalchemy.orm import joinedload
from io import StringIO
from sqlalchemy import func
from datetime import timedelta

import csv

sales_bp = Blueprint("sales", __name__)


def is_admin_or_manager():
    return current_user.is_authenticated and current_user.role in ["admin", "manager"]


@sales_bp.route("/sales", methods=["GET", "POST"])
@login_required
def manage_sales():
    if not is_admin_or_manager():
        flash("Admins and Managers only!")
        return redirect(url_for("inventory.inventory"))

    today = date.today()
    selected_date = request.args.get("date")
    if selected_date:
        try:
            selected_date = datetime.strptime(selected_date, "%Y-%m-%d").date()
        except ValueError:
            flash("Invalid date format. Showing today's sales.")
            selected_date = today
    else:
        selected_date = today

    products = Product.query.filter_by(org_id=current_user.org_id).options(
        joinedload(Product.brand), joinedload(Product.category), joinedload(Product.volume)
    ).all()

    sales = Sale.query.filter_by(org_id=current_user.org_id, sale_date=selected_date).all()
    sales_dict = {sale.product_id: sale for sale in sales}

    return render_template(
        "sales.html",
        products=products,
        sales_dict=sales_dict,
        selected_date=selected_date.strftime("%Y-%m-%d")
    )

@sales_bp.route("/sales/update", methods=["POST"])
@login_required
def update_sales():
    if not is_admin_or_manager():
        flash("Admins and Managers only!")
        return redirect(url_for("inventory.inventory"))

    try:
        sale_date = request.form.get("sale_date") or date.today().strftime("%Y-%m-%d")
        sale_date = datetime.strptime(sale_date, "%Y-%m-%d").date()

        any_updates = False
        errors = []

        for key, value in request.form.items():
            if key.startswith("quantity_"):
                product_id = int(key.split("_")[1])
                quantity = int(value)

                if quantity < 0:
                    continue

                product = Product.query.get(product_id)
                if not product or product.org_id != current_user.org_id:
                    continue

                stock = Stock.query.filter_by(product_id=product_id, org_id=current_user.org_id).first()
                current_stock = stock.quantity if stock else 0

                sale = Sale.query.filter_by(product_id=product_id, sale_date=sale_date, org_id=current_user.org_id).first()
                previous_quantity = sale.quantity_sold if sale else 0
                quantity_diff = quantity - previous_quantity

                if quantity_diff > current_stock:
                    errors.append(f"❌ Not enough stock for '{product.product_name}'. Available: {current_stock}, Tried to sell: {quantity_diff}.")
                    continue

                # Update sale
                price_obj = Price.query.filter_by(product_id=product_id).order_by(Price.effective_date.desc()).first()
                price = float(price_obj.price) if price_obj else 0.00
                total = quantity * price

                if sale:
                    sale.quantity_sold = quantity
                    sale.total_price = total
                    sale.sold_by = current_user.user_id
                else:
                    sale = Sale(
                        product_id=product_id,
                        org_id=current_user.org_id,
                        quantity_sold=quantity,
                        total_price=total,
                        sale_date=sale_date,
                        sold_by=current_user.user_id
                    )
                    db.session.add(sale)

                # Update stock
                if stock:
                    stock.quantity -= quantity_diff
                    stock.last_updated = datetime.now()
                    stock.last_updated_by = current_user.user_id
                else:
                    stock = Stock(
                        product_id=product_id,
                        org_id=current_user.org_id,
                        quantity=max(0 - quantity_diff, 0),
                        last_updated=datetime.now(),
                        last_updated_by=current_user.user_id
                    )
                    db.session.add(stock)

                any_updates = True

        if any_updates:
            db.session.commit()
            flash("✅ Sales updated successfully.")
        if errors:
            for err in errors:
                flash(err)

    except Exception as e:
        db.session.rollback()
        flash("❌ Error updating sales.")
        print(f"[Sales Update Error] {e}")

    return redirect(url_for("sales.manage_sales", date=sale_date.strftime("%Y-%m-%d")))

@sales_bp.route('/sales/download_csv/<selected_date>')
@login_required
def download_csv(selected_date):
    if not is_admin_or_manager():
        flash("Admins and Managers only!")
        return redirect(url_for('inventory.inventory'))

    try:
        selected_date = datetime.strptime(selected_date, "%Y-%m-%d").date()
        org_id = current_user.org_id
        sales = (
            Sale.query
            .filter_by(org_id=org_id, sale_date=selected_date)
            .join(Sale.product)
            .join(Product.category)
            .join(Product.volume)
            .order_by(Product.product_name)
            .all()
        )

        if not sales:
            flash("No sales found for this date.")
            return redirect(url_for("sales.manage_sales"))

        # Create CSV
        si = StringIO()
        writer = csv.writer(si)
        writer.writerow(["Product", "Category", "Volume (ml)", "Previous Stock", "Quantity Sold", "Present Stock", "Total Price ($)"])

        total_amount = 0

        for sale in sales:
            # Get previous day's stock (fallback to current if not found)
            previous_stock_entry = (
                StockUpdate.query
                .filter_by(product_id=sale.product_id)
                .filter(StockUpdate.update_time < selected_date)
                .order_by(StockUpdate.update_time.desc())
                .first()
            )

            previous_stock = previous_stock_entry.new_quantity if previous_stock_entry else sale.quantity_sold + 0  # fallback

            present_stock = previous_stock - sale.quantity_sold
            total_amount += float(sale.total_price)

            writer.writerow([
                sale.product.product_name,
                sale.product.category.category_name,
                sale.product.volume.volume_ml,
                previous_stock,
                sale.quantity_sold,
                present_stock,
                f"{float(sale.total_price):.2f}"
            ])

        writer.writerow([])
        writer.writerow(["", "", "", "", "", "Total", f"{total_amount:.2f}"])

        output = si.getvalue()
        return Response(
            output,
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment;filename=sales_{selected_date}.csv"}
        )
    except Exception as e:
        print(f"[CSV Download Error] {e}")
        flash("Error generating CSV.")
        return redirect(url_for("sales.manage_sales"))