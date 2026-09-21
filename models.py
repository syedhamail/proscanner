from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()


class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(180), unique=True, nullable=False, index=True)

    # Nullable because Google/GitHub sign-ins don't set a password.
    password_hash = db.Column(db.String(255), nullable=True)

    # Email verification
    is_verified = db.Column(db.Boolean, default=False, nullable=False)
    verification_token = db.Column(db.String(64), unique=True, nullable=True)
    verification_sent_at = db.Column(db.DateTime, nullable=True)
    # Where to send the user after they verify (e.g. they were trying to open /signals).
    signup_next = db.Column(db.String(255), nullable=True)

    # OAuth (Google / GitHub)
    oauth_provider = db.Column(db.String(20), nullable=True)   # 'google' | 'github'
    oauth_id = db.Column(db.String(120), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login_at = db.Column(db.DateTime, nullable=True)

    # Plan / subscription (set by the Paddle webhook once payment succeeds)
    plan = db.Column(db.String(20), nullable=True)   # 'basic' | 'advanced' | 'premium'
    plan_started_at = db.Column(db.DateTime, nullable=True)
    paddle_customer_id = db.Column(db.String(120), nullable=True)
    paddle_subscription_id = db.Column(db.String(120), nullable=True)

    # Scan usage — rolling window for basic/advanced plans
    scan_count = db.Column(db.Integer, default=0, nullable=False)
    scan_window_start = db.Column(db.DateTime, nullable=True)
