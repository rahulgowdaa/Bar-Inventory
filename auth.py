from flask import Blueprint, request, redirect, url_for, render_template, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Organization
from utils import log_action
from datetime import datetime, timedelta
import pyotp
import re

auth_bp = Blueprint('auth', __name__)

login_manager = LoginManager()
login_manager.login_view = 'auth.login'

LOCKOUT_THRESHOLD = 5
LOCKOUT_DURATION = timedelta(minutes=15)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()

        if user:
            # Check if the account is locked
            if user.is_locked:
                if datetime.now() > user.lockout_time + LOCKOUT_DURATION:
                    # Unlock the account after the lockout duration
                    user.is_locked = False
                    user.failed_login_attempts = 0
                else:
                    flash('Account is locked. Please try again later.')
                    return redirect(url_for('auth.login'))

            if check_password_hash(user.password_hash, password):
                login_user(user)
                user.failed_login_attempts = 0  # Reset on successful login
                db.session.commit()

                # Redirect to 2FA verification only if 2FA is set up
                if user.otp_secret:
                    return redirect(url_for('auth.verify_2fa'))

                # Log the login action
                log_action(user.user_id, "User logged in")
                
                if user.needs_password_change:
                    flash("Please change your password before continuing.")
                    return redirect(url_for('auth.change_password'))
                
                return redirect(url_for('dashboard'))
            else:
                user.failed_login_attempts += 1
                if user.failed_login_attempts >= LOCKOUT_THRESHOLD:
                    user.is_locked = True
                    user.lockout_time = datetime.now()
                    flash('Account locked due to too many failed login attempts.')
                else:
                    flash('Invalid email or password')
                db.session.commit()
        else:
            flash('Invalid email or password')
    return render_template('login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

def is_strong_password(password):
    return (
        len(password) >= 8 and
        re.search(r"[A-Z]", password) and
        re.search(r"[a-z]", password) and
        re.search(r"[0-9]", password) and
        re.search(r"[!@#$%^&*(),.?\":{}|<>]", password)
    )

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        org_name = request.form.get('org_name')

        # Check if organization already exists
        existing_org = Organization.query.filter_by(org_name=org_name).first()
        if existing_org:
            flash('Organization name already taken')
            return redirect(url_for('auth.register'))

        # Check if email already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Email address already registered')
            return redirect(url_for('auth.register'))

        # Create new organization
        new_org = Organization(org_name=org_name)
        db.session.add(new_org)
        db.session.commit()

        # Create new user as admin of the new organization
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(name=name, email=email, password_hash=hashed_password, role='admin', org_id=new_org.org_id, otp_secret=None)
        
        try:
            db.session.add(new_user)
            db.session.commit()
            flash('User registered successfully')
            return redirect(url_for('auth.login'))
        except Exception as e:
            db.session.rollback()
            flash('An error occurred while creating the user and organization')
            print(f"Error: {e}")
            return redirect(url_for('auth.register'))
    return render_template('register.html')

@auth_bp.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        old_password = request.form.get('old_password')
        new_password = request.form.get('new_password')

        # Check if the old password is correct
        if not check_password_hash(current_user.password_hash, old_password):
            flash('Old password is incorrect')
            return redirect(url_for('auth.change_password'))

        # Check if the new password is different from the old password
        if check_password_hash(current_user.password_hash, new_password):
            flash('New password cannot be the same as the old password')
            return redirect(url_for('auth.change_password'))

        # Update the password
        hashed_password = generate_password_hash(new_password, method='pbkdf2:sha256')
        current_user.password_hash = hashed_password
        current_user.needs_password_change = False
        db.session.commit()

        # Log the password change action
        log_action(current_user.user_id, "Password changed")

        flash('Password changed successfully')
        return redirect(url_for('dashboard'))
    return render_template('change_password.html')

@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    otp_uri = None

    if request.method == 'POST':
        # Handle 2FA setup initiation
        if 'setup_2fa' in request.form:
            if not current_user.otp_secret:
                current_user.otp_secret = pyotp.random_base32()
                db.session.commit()
            otp_uri = pyotp.totp.TOTP(current_user.otp_secret).provisioning_uri(
                current_user.email, issuer_name="MyApp"
            )
        
        # Handle 2FA verification
        elif 'otp' in request.form:
            otp = request.form.get('otp')
            totp = pyotp.TOTP(current_user.otp_secret)
            if totp.verify(otp):
                flash('2FA setup complete. Your account is now protected with 2FA.')
            else:
                flash('Invalid OTP. Please try again.')
        
        # Handle 2FA disabling
        elif 'disable_2fa' in request.form:
            current_user.otp_secret = None
            db.session.commit()
            flash('2FA has been disabled.')

        # Update user name
        new_name = request.form.get('name')
        if new_name:
            current_user.name = new_name

        # Update password if provided
        old_password = request.form.get('old_password')
        new_password = request.form.get('new_password')

        if old_password and new_password:
            # Check if the old password is correct
            if not check_password_hash(current_user.password_hash, old_password):
                flash('Old password is incorrect')
                return redirect(url_for('auth.profile'))

            # Check if the new password is different from the old password
            if old_password == new_password:
                flash('New password cannot be the same as the old password')
                return redirect(url_for('auth.profile'))

            # Update the password
            hashed_password = generate_password_hash(new_password, method='pbkdf2:sha256')
            current_user.password_hash = hashed_password

        db.session.commit()

        # Log the profile update action
        log_action(current_user.user_id, "Profile updated")

        flash('Profile updated successfully')
        return redirect(url_for('auth.profile'))

    return render_template('profile.html', user=current_user, otp_uri=otp_uri)

@auth_bp.route('/setup_2fa', methods=['GET', 'POST'])
@login_required
def setup_2fa():
    otp_uri = None

    # Generate a new OTP secret if not already set
    if not current_user.otp_secret:
        current_user.otp_secret = pyotp.random_base32()
        otp_uri = pyotp.totp.TOTP(current_user.otp_secret).provisioning_uri(
            current_user.email, issuer_name="MyApp"
        )
        db.session.commit()  # Ensure the secret is saved

    if request.method == 'POST':
        otp = request.form.get('otp')
        totp = pyotp.TOTP(current_user.otp_secret)
        print(f"Verifying OTP: {otp} with secret: {current_user.otp_secret}")
        if totp.verify(otp):
            print("OTP verified successfully")
            flash('2FA setup complete. Your account is now protected with 2FA.')
            return redirect(url_for('auth.profile'))
        else:
            print("Invalid OTP")
            flash('Invalid OTP. Please try again.')

    return render_template('setup_2fa.html', otp_uri=otp_uri)

@auth_bp.route('/verify_2fa', methods=['GET', 'POST'])
@login_required
def verify_2fa():
    if request.method == 'POST':
        otp = request.form.get('otp')
        totp = pyotp.TOTP(current_user.otp_secret)
        if totp.verify(otp):
            flash('2FA verification successful.')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid OTP. Please try again.')
    return render_template('verify_2fa.html') 