from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.mysql import DECIMAL
import pyotp


db = SQLAlchemy()


class Organization(db.Model):
    __tablename__ = "organizations"
    org_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    org_name = db.Column(db.String(100), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())


class User(db.Model):
    __tablename__ = "users"
    user_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, index=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    org_id = db.Column(db.Integer, db.ForeignKey("organizations.org_id", ondelete="CASCADE"), nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    needs_password_change = db.Column(db.Boolean, default=True)
    failed_login_attempts = db.Column(db.Integer, default=0)
    is_locked = db.Column(db.Boolean, default=False)
    lockout_time = db.Column(db.DateTime, nullable=True)
    otp_secret = db.Column(db.String(16), nullable=True)

    organization = db.relationship("Organization", backref=db.backref("users", passive_deletes=True))

    @property
    def is_authenticated(self): return True
    @property
    def is_active(self): return True
    @property
    def is_anonymous(self): return False
    def get_id(self): return str(self.user_id)


class Brand(db.Model):
    __tablename__ = "brands"
    brand_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    brand_name = db.Column(db.String(100), unique=True, nullable=False)


class AlcoholCategory(db.Model):
    __tablename__ = "alcohol_categories"
    category_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    category_name = db.Column(db.String(100), unique=True, nullable=False)


class BottleVolume(db.Model):
    __tablename__ = "bottle_volumes"
    volume_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    volume_ml = db.Column(db.Integer, nullable=False, unique=True)


class Product(db.Model):
    __tablename__ = "products"
    product_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    product_name = db.Column(db.String(200), nullable=False, index=True)
    brand_id = db.Column(db.Integer, db.ForeignKey("brands.brand_id", ondelete="CASCADE"), nullable=False, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey("alcohol_categories.category_id", ondelete="CASCADE"), nullable=False)
    volume_id = db.Column(db.Integer, db.ForeignKey("bottle_volumes.volume_id", ondelete="CASCADE"), nullable=False)
    org_id = db.Column(db.Integer, db.ForeignKey("organizations.org_id", ondelete="CASCADE"), nullable=False)

    __table_args__ = (
        db.UniqueConstraint("product_name", "brand_id", "category_id", "volume_id", "org_id", name="uq_product_combination"),
    )

    organization = db.relationship("Organization", backref=db.backref("products", passive_deletes=True))
    brand = db.relationship("Brand", backref=db.backref("products", passive_deletes=True))
    category = db.relationship("AlcoholCategory", backref=db.backref("products", passive_deletes=True))
    volume = db.relationship("BottleVolume", backref=db.backref("products", passive_deletes=True))


class Stock(db.Model):
    __tablename__ = "stock"
    stock_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.product_id", ondelete="CASCADE"), nullable=False)
    org_id = db.Column(db.Integer, db.ForeignKey("organizations.org_id", ondelete="CASCADE"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=0)
    last_updated = db.Column(db.DateTime, default=db.func.current_timestamp())
    last_updated_by = db.Column(db.Integer, db.ForeignKey("users.user_id", ondelete="SET NULL"))

    product = db.relationship("Product", backref=db.backref("stock", passive_deletes=True))
    organization = db.relationship("Organization", backref=db.backref("stock_entries", passive_deletes=True))
    user = db.relationship("User", backref=db.backref("stock_updates", passive_deletes=True))


class StockUpdate(db.Model):
    __tablename__ = "stock_updates"
    update_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.product_id", ondelete="CASCADE"), nullable=False)
    previous_quantity = db.Column(db.Integer, nullable=False)
    new_quantity = db.Column(db.Integer, nullable=False)
    update_time = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_by = db.Column(db.Integer, db.ForeignKey("users.user_id", ondelete="SET NULL"))

    product = db.relationship("Product", backref=db.backref("stock_updates", passive_deletes=True))
    user = db.relationship("User", backref=db.backref("stock_change_logs", passive_deletes=True))


class Sale(db.Model):
    __tablename__ = "sales"
    sale_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.product_id", ondelete="CASCADE"), nullable=False)
    org_id = db.Column(db.Integer, db.ForeignKey("organizations.org_id", ondelete="CASCADE"), nullable=False)
    quantity_sold = db.Column(db.Integer, nullable=False)
    total_price = db.Column(DECIMAL(10, 2), nullable=False)
    sale_date = db.Column(db.Date, default=db.func.current_date(), index=True)
    sold_by = db.Column(db.Integer, db.ForeignKey("users.user_id", ondelete="SET NULL"))

    product = db.relationship("Product", backref=db.backref("sales", passive_deletes=True))
    organization = db.relationship("Organization", backref=db.backref("sales_records", passive_deletes=True))
    user = db.relationship("User", backref=db.backref("sales_made", passive_deletes=True))


class Price(db.Model):
    __tablename__ = "prices"
    price_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.product_id", ondelete="CASCADE"), nullable=False)
    price = db.Column(DECIMAL(10, 2), nullable=False)
    effective_date = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_by = db.Column(db.Integer, db.ForeignKey("users.user_id", ondelete="SET NULL"))

    product = db.relationship("Product", backref=db.backref("price_history", passive_deletes=True))
    user = db.relationship("User", backref=db.backref("price_updates", passive_deletes=True))


class UserActionLog(db.Model):
    __tablename__ = "user_action_logs"
    log_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, nullable=True)
    action = db.Column(db.String(255), nullable=False)
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())
