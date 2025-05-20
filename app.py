from flask import Flask, render_template, request, redirect, url_for, flash
from models import db, User
from auth import auth_bp, login_manager
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from utils import log_action  # Import the log_action function
from inventory import inventory_bp  # ✅ Add this line
from admin_inventory import admin_inventory_bp
from sales import sales_bp

app = Flask(__name__)
app.config.from_object('config')  # Load configuration from config.py

db.init_app(app)
login_manager.init_app(app)

app.register_blueprint(auth_bp, url_prefix='/auth')

@app.before_request
def enforce_password_change():
    if current_user.is_authenticated:
        if current_user.needs_password_change:
            allowed_paths = ['auth.logout', 'auth.change_password', 'static']
            if request.endpoint not in allowed_paths:
                flash("Please change your password to continue.")
                return redirect(url_for('auth.change_password'))

@app.route("/")
def home():
    return render_template('home.html')

@app.route("/dashboard")
@login_required
def dashboard():
    return render_template('dashboard.html')

@app.route("/admin/users", methods=['GET', 'POST'])
@login_required
def manage_users():
    if current_user.role != 'admin':
        flash('Access denied: Admins only')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role')

        # Check if user already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Email address already registered')
            return redirect(url_for('manage_users'))

        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(name=name, email=email, password_hash=hashed_password, role=role, org_id=current_user.org_id, needs_password_change=True)
        
        try:
            db.session.add(new_user)
            db.session.commit()
            flash('User created successfully')
        except Exception as e:
            db.session.rollback()
            flash('An error occurred while creating the user')

    users = User.query.filter_by(org_id=current_user.org_id).all()
    return render_template('manage_users.html', users=users)

@app.route("/admin/reset_password/<int:user_id>", methods=['POST'])
@login_required
def reset_password(user_id):
    if current_user.role != 'admin':
        flash('Access denied: Admins only')
        return redirect(url_for('dashboard'))

    user = User.query.get(user_id)
    if user:
        new_password = request.form.get('new_password')
        hashed_password = generate_password_hash(new_password, method='pbkdf2:sha256')
        user.password_hash = hashed_password
        user.needs_password_change = True
        db.session.commit()
        flash('Password reset successfully')
    else:
        flash('User not found')
    return redirect(url_for('manage_users'))

@app.route("/admin/delete_user/<int:user_id>", methods=['POST'])
@login_required
def delete_user(user_id):
    if current_user.role != 'admin':
        flash('Access denied: Admins only')
        return redirect(url_for('dashboard'))

    user = User.query.get(user_id)
    if user:
    # Prevent user from deleting themselves if others exist
        if user.user_id == current_user.user_id:
            other_users = User.query.filter(
                User.org_id == current_user.org_id, 
                User.user_id != current_user.user_id
            ).count()
            if other_users > 0:
                flash('Cannot delete your own account while other users exist in the organization')
                return redirect(url_for('manage_users'))

        # Log the action BEFORE deleting the user
        if current_user.is_authenticated and current_user.user_id is not None:
            log_action(current_user.user_id, f"Deleted user {user.email}")

        db.session.delete(user)
        db.session.commit()
        flash('User deleted successfully')
    else:
        flash('User not found')
    return redirect(url_for('manage_users'))

app.register_blueprint(inventory_bp)
app.register_blueprint(admin_inventory_bp)
app.register_blueprint(sales_bp)

if __name__ == "__main__":
    app.run(debug=True)
