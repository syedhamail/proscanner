import os
import hmac
import hashlib
import secrets
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
load_dotenv()

import requests
from flask import Flask, jsonify, request, render_template, redirect, url_for, flash, session, send_from_directory
from flask_cors import CORS
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from authlib.integrations.flask_client import OAuth

from scanner_engine import run_scan
from models import db, User
from plans import PLAN_LIMITS, plan_config, scan_status, register_scan

app = Flask(__name__)
CORS(app)

app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")

# ------------------------------------------------------------------
# Database (PostgreSQL). Set DATABASE_URL in your environment
# (Northflank provides one automatically for its Postgres add-on).
# Falls back to a local SQLite file so the app still runs without
# a database configured, e.g. for quick local UI checks.
# ------------------------------------------------------------------
db_url = (os.environ.get("DATABASE_URL") or "").strip() or "sqlite:///local.db"
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = "Please log in to continue."


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


@login_manager.unauthorized_handler
def unauthorized():
    # API calls (fetch from JS) get JSON back so the frontend can redirect itself
    # instead of following a 302 into an HTML login page.
    if request.path.startswith("/api/"):
        return jsonify({
            "status": "redirect",
            "redirect_url": url_for("login", next=url_for("signals")),
            "reason": "auth_required",
        }), 401
    return redirect(url_for("login", next=request.path))


with app.app_context():
    db.create_all()

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
CONTACT_TO_EMAIL = os.environ.get("CONTACT_TO_EMAIL", "you@example.com")
CONTACT_FROM_EMAIL = os.environ.get("CONTACT_FROM_EMAIL", "Pro Scanner <onboarding@resend.dev>")

ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")

PADDLE_CLIENT_TOKEN = os.environ.get("PADDLE_CLIENT_TOKEN", "")
PADDLE_ENV = os.environ.get("PADDLE_ENV", "sandbox")  # "sandbox" or "production"
PADDLE_WEBHOOK_SECRET = os.environ.get("PADDLE_WEBHOOK_SECRET", "")
PADDLE_PRICE_IDS = {
    "basic": os.environ.get("PADDLE_BASIC_PRICE_ID", ""),
    "advanced": os.environ.get("PADDLE_ADVANCED_PRICE_ID", ""),
    "premium": os.environ.get("PADDLE_PREMIUM_PRICE_ID", ""),
}

PKT = ZoneInfo("Asia/Karachi")

# ------------------------------------------------------------------
# SEO: canonical domain, robots.txt, sitemap.xml
# ------------------------------------------------------------------
SITE_URL = os.environ.get("SITE_URL", "https://proscanner.com.pk").rstrip("/")


@app.context_processor
def inject_seo_defaults():
    return dict(
        site_url=SITE_URL,
        canonical_url=f"{SITE_URL}{request.path}",
        default_og_image=f"{SITE_URL}/static/img/og-image.png",
    )


@app.route("/robots.txt")
def robots_txt():
    return send_from_directory(os.path.join(app.root_path, "static", "seo"), "robots.txt", mimetype="text/plain")


@app.route("/sitemap.xml")
def sitemap_xml():
    return send_from_directory(os.path.join(app.root_path, "static", "seo"), "sitemap.xml", mimetype="application/xml")


@app.template_filter("pkt")
def pkt_filter(dt):
    """Render a stored UTC datetime as Pakistan time, for the admin panel."""
    if not dt:
        return "—"
    return dt.replace(tzinfo=ZoneInfo("UTC")).astimezone(PKT).strftime("%d %b %Y, %I:%M %p PKT")


@app.template_filter("dt")
def dt_filter(dt):
    if not dt:
        return "—"
    return dt.strftime("%d %b %Y")


# ------------------------------------------------------------------
# OAuth (Google + GitHub)
# ------------------------------------------------------------------
oauth = OAuth(app)

oauth.register(
    name="google",
    client_id=os.environ.get("GOOGLE_CLIENT_ID", ""),
    client_secret=os.environ.get("GOOGLE_CLIENT_SECRET", ""),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

oauth.register(
    name="github",
    client_id=os.environ.get("GITHUB_CLIENT_ID", ""),
    client_secret=os.environ.get("GITHUB_CLIENT_SECRET", ""),
    access_token_url="https://github.com/login/oauth/access_token",
    authorize_url="https://github.com/login/oauth/authorize",
    api_base_url="https://api.github.com/",
    client_kwargs={"scope": "read:user user:email"},
)


def login_and_redirect(user, default_endpoint="dashboard"):
    """Shared post-auth step: mark last login, honor a pending `next`, else go to dashboard."""
    user.last_login_at = datetime.utcnow()
    next_url = request.args.get("next") or user.signup_next
    user.signup_next = None
    db.session.commit()
    login_user(user)
    if next_url:
        return redirect(next_url)
    return redirect(url_for(default_endpoint))


# ------------------------------------------------------------------
# Page routes
# ------------------------------------------------------------------
@app.route("/")
def home():
    return render_template("index.html")


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/signals")
def signals():
    return render_template("signals.html")


@app.route("/pricing")
def pricing():
    return render_template(
        "pricing.html",
        plans=PLAN_LIMITS,
        paddle_client_token=PADDLE_CLIENT_TOKEN,
        paddle_env=PADDLE_ENV,
        paddle_price_ids=PADDLE_PRICE_IDS,
    )


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


@app.route("/dashboard")
@login_required
def dashboard():
    status = scan_status(current_user)
    return render_template("dashboard.html", status=status, plan_cfg=plan_config(current_user.plan))


# ------------------------------------------------------------------
# Email verification
# ------------------------------------------------------------------
def send_verification_email(user):
    verify_url = url_for("verify_email", token=user.verification_token, _external=True)
    html_body = f"""
    <div style="font-family: Arial, Helvetica, sans-serif; background:#0D0E12; padding:40px 20px;">
      <div style="max-width:480px; margin:0 auto; background:#1A1D26; border-radius:16px; overflow:hidden; border:1px solid #262b38;">
        <div style="background:linear-gradient(135deg,#2962FF,#6c8dff); padding:36px 32px; text-align:center;">
          <div style="width:52px;height:52px;border-radius:14px;background:rgba(255,255,255,0.18);display:inline-flex;align-items:center;justify-content:center;font-size:24px;color:#fff;font-weight:700;margin-bottom:14px;">P</div>
          <h1 style="margin:0; color:#fff; font-size:20px;">Verify your email</h1>
        </div>
        <div style="padding:32px; color:#E0E0E0; text-align:center;">
          <p style="margin:0 0 24px 0; font-size:15px; line-height:1.6; color:#B7BCC9;">
            Hi {user.name}, thanks for signing up for Pro Scanner. Click the button below to verify
            your email and activate your account.
          </p>
          <a href="{verify_url}" style="display:inline-block; background:#2962FF; color:#fff; text-decoration:none; padding:14px 32px; border-radius:10px; font-weight:600; font-size:15px;">
            Verify Email Address
          </a>
          <p style="margin:24px 0 0 0; font-size:12.5px; color:#5c6270;">
            This link expires in 24 hours. If you didn't create this account, you can ignore this email.
          </p>
        </div>
      </div>
    </div>
    """

    if not RESEND_API_KEY:
        # Dev convenience: no email service configured, so print the link to the console.
        print(f"[DEV] Verification link for {user.email}: {verify_url}")
        return

    try:
        requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"},
            json={
                "from": CONTACT_FROM_EMAIL,
                "to": [user.email],
                "subject": "Verify your email — Pro Scanner",
                "html": html_body,
            },
            timeout=10,
        )
    except Exception as e:
        print(f"[WARN] Could not send verification email: {e}")


@app.route("/verify-email/<token>")
def verify_email(token):
    user = User.query.filter_by(verification_token=token).first()
    if not user:
        flash("That verification link is invalid or has already been used.", "err")
        return redirect(url_for("login"))

    if user.verification_sent_at and datetime.utcnow() - user.verification_sent_at > timedelta(hours=24):
        flash("That verification link has expired. Please sign up again or request a new link.", "err")
        return redirect(url_for("resend_verification", email=user.email))

    user.is_verified = True
    user.verification_token = None
    db.session.commit()
    flash("Email verified! Welcome to Pro Scanner.", "ok")
    return login_and_redirect(user)


@app.route("/resend-verification", methods=["GET", "POST"])
def resend_verification():
    email = (request.values.get("email") or "").strip().lower()
    if request.method == "POST" and email:
        user = User.query.filter_by(email=email).first()
        if user and not user.is_verified:
            user.verification_token = secrets.token_urlsafe(32)
            user.verification_sent_at = datetime.utcnow()
            db.session.commit()
            send_verification_email(user)
        flash("If that email exists and isn't verified yet, a new link has been sent.", "ok")
        return redirect(url_for("login"))
    return render_template("resend_verification.html", email=email)


# ------------------------------------------------------------------
# Auth: signup / login / logout
# ------------------------------------------------------------------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    next_url = request.args.get("next") or request.form.get("next")

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not name or not email or not password:
            flash("Please fill in all fields.", "err")
        elif len(password) < 6:
            flash("Password must be at least 6 characters.", "err")
        elif User.query.filter_by(email=email).first():
            flash("An account with that email already exists.", "err")
        else:
            user = User(
                name=name,
                email=email,
                password_hash=generate_password_hash(password),
                is_verified=False,
                verification_token=secrets.token_urlsafe(32),
                verification_sent_at=datetime.utcnow(),
                signup_next=next_url,
            )
            db.session.add(user)
            db.session.commit()
            send_verification_email(user)
            return render_template("verify_sent.html", email=email)

    return render_template("signup.html", next=next_url)


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    next_url = request.args.get("next") or request.form.get("next")

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()

        if not user or not user.password_hash or not check_password_hash(user.password_hash, password):
            flash("Invalid email or password.", "err")
        elif not user.is_verified:
            flash("Please verify your email before logging in — check your inbox.", "err")
        else:
            return login_and_redirect(user)

    return render_template("login.html", next=next_url)


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("home"))


# ------------------------------------------------------------------
# OAuth routes
# ------------------------------------------------------------------
@app.route("/auth/<provider>")
def oauth_login(provider):
    if provider not in ("google", "github"):
        return redirect(url_for("login"))
    session["oauth_next"] = request.args.get("next", "")
    redirect_uri = url_for("oauth_callback", provider=provider, _external=True)
    return oauth.create_client(provider).authorize_redirect(redirect_uri)


@app.route("/auth/<provider>/callback")
def oauth_callback(provider):
    if provider not in ("google", "github"):
        return redirect(url_for("login"))

    client = oauth.create_client(provider)
    token = client.authorize_access_token()

    if provider == "google":
        info = token.get("userinfo") or client.userinfo()
        oauth_id = info["sub"]
        email = info["email"].lower()
        name = info.get("name") or email.split("@")[0]
    else:  # github
        profile = client.get("user").json()
        oauth_id = str(profile["id"])
        name = profile.get("name") or profile.get("login")
        email = profile.get("email")
        if not email:
            emails = client.get("user/emails").json()
            primary = next((e for e in emails if e.get("primary")), emails[0] if emails else None)
            email = (primary or {}).get("email")
        email = (email or f"{oauth_id}@users.noreply.github.com").lower()

    user = User.query.filter_by(oauth_provider=provider, oauth_id=oauth_id).first()
    if not user:
        user = User.query.filter_by(email=email).first()

    if not user:
        user = User(
            name=name,
            email=email,
            oauth_provider=provider,
            oauth_id=oauth_id,
            is_verified=True,  # Google/GitHub already verified the email
        )
        db.session.add(user)
    else:
        user.oauth_provider = user.oauth_provider or provider
        user.oauth_id = user.oauth_id or oauth_id
        user.is_verified = True

    db.session.commit()

    next_url = session.pop("oauth_next", "") or None
    if next_url:
        user.signup_next = next_url
        db.session.commit()

    return login_and_redirect(user)


# ------------------------------------------------------------------
# Dashboard actions
# ------------------------------------------------------------------
@app.route("/dashboard/change-password", methods=["POST"])
@login_required
def change_password():
    current_password = request.form.get("current_password", "")
    new_password = request.form.get("new_password", "")
    confirm_password = request.form.get("confirm_password", "")

    if current_user.password_hash and not check_password_hash(current_user.password_hash, current_password):
        flash("Current password is incorrect.", "err")
    elif len(new_password) < 6:
        flash("New password must be at least 6 characters.", "err")
    elif new_password != confirm_password:
        flash("New passwords don't match.", "err")
    else:
        current_user.password_hash = generate_password_hash(new_password)
        db.session.commit()
        flash("Password updated.", "ok")

    return redirect(url_for("dashboard"))


# ------------------------------------------------------------------
# Scanner API — untouched strategy logic, gated by plan + usage limits
# ------------------------------------------------------------------
@app.route("/api/scan", methods=["GET"])
@login_required
def api_scan():
    status = scan_status(current_user)
    if not status["allowed"]:
        return jsonify({
            "status": "redirect",
            "redirect_url": url_for("pricing"),
            "reason": status["reason"],
        }), 403

    register_scan(current_user)
    db.session.commit()

    limit = int(request.args.get("limit", 50))
    mode = request.args.get("mode", "full")
    entry_type = request.args.get("entry_type", "relaxed")

    try:
        results = run_scan(limit=limit, mode=mode, entry_type=entry_type)
        return jsonify({
            "status": "success",
            "count": len(results),
            "mode": mode,
            "entry_type": entry_type,
            "data": results
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e), "data": []}), 500


# ------------------------------------------------------------------
# Paddle billing
# ------------------------------------------------------------------
def verify_paddle_signature(raw_body: bytes, signature_header: str) -> bool:
    if not PADDLE_WEBHOOK_SECRET or not signature_header:
        return False
    try:
        parts = dict(p.split("=", 1) for p in signature_header.split(";") if "=" in p)
        ts, h1 = parts.get("ts"), parts.get("h1")
        if not ts or not h1:
            return False
        signed_payload = f"{ts}:{raw_body.decode('utf-8')}"
        computed = hmac.new(PADDLE_WEBHOOK_SECRET.encode(), signed_payload.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(computed, h1)
    except Exception:
        return False


@app.route("/api/paddle-webhook", methods=["POST"])
def paddle_webhook():
    signature = request.headers.get("Paddle-Signature", "")
    if not verify_paddle_signature(request.data, signature):
        return jsonify({"status": "error", "message": "invalid signature"}), 400

    event = request.get_json(silent=True) or {}
    event_type = event.get("event_type")
    data = event.get("data", {})

    if event_type in ("transaction.completed", "subscription.created", "subscription.activated"):
        custom_data = data.get("custom_data") or {}
        user_id = custom_data.get("user_id")
        plan = custom_data.get("plan")

        if user_id and plan in PLAN_LIMITS:
            user = db.session.get(User, int(user_id))
            if user:
                user.plan = plan
                user.plan_started_at = datetime.utcnow()
                user.scan_count = 0
                user.scan_window_start = None
                user.paddle_subscription_id = data.get("subscription_id") or data.get("id")
                user.paddle_customer_id = data.get("customer_id")
                db.session.commit()

    elif event_type in ("subscription.canceled", "subscription.paused"):
        subscription_id = data.get("id")
        user = User.query.filter_by(paddle_subscription_id=subscription_id).first()
        if user:
            user.plan = None
            db.session.commit()

    return jsonify({"status": "ok"})


# ------------------------------------------------------------------
# Contact form -> email via Resend
# ------------------------------------------------------------------
@app.route("/api/contact", methods=["POST"])
def api_contact():
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    email = (payload.get("email") or "").strip()
    message = (payload.get("message") or "").strip()

    if not name or not email or not message:
        return jsonify({"status": "error", "message": "Name, email aur message zaroori hain."}), 400
    if "@" not in email or "." not in email.split("@")[-1]:
        return jsonify({"status": "error", "message": "Valid email address dein."}), 400

    html_body = f"""
    <div style="font-family: Arial, Helvetica, sans-serif; background:#0D0E12; padding:32px;">
      <div style="max-width:560px; margin:0 auto; background:#1A1D26; border-radius:12px; overflow:hidden; border:1px solid #262b38;">
        <div style="background:#2962FF; padding:20px 28px;">
          <h2 style="margin:0; color:#ffffff; font-size:18px; letter-spacing:0.3px;">New message &mdash; Pro Scanner website</h2>
        </div>
        <div style="padding:28px; color:#E0E0E0;">
          <p style="margin:0 0 14px 0; font-size:14px; color:#9AA1AE;">FROM</p>
          <p style="margin:0 0 20px 0; font-size:16px;">{name} &lt;{email}&gt;</p>
          <p style="margin:0 0 14px 0; font-size:14px; color:#9AA1AE;">MESSAGE</p>
          <p style="margin:0; font-size:15px; line-height:1.6; white-space:pre-wrap;">{message}</p>
        </div>
        <div style="padding:16px 28px; background:#12141b; font-size:12px; color:#5c6270;">
          Sent automatically from the Pro Scanner contact form.
        </div>
      </div>
    </div>
    """

    if not RESEND_API_KEY:
        return jsonify({"status": "success", "message": "Received (email sending not configured yet)."})

    try:
        r = requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"},
            json={
                "from": CONTACT_FROM_EMAIL,
                "to": [CONTACT_TO_EMAIL],
                "reply_to": email,
                "subject": f"New contact form message from {name}",
                "html": html_body,
            },
            timeout=10,
        )
        if r.status_code >= 300:
            print(f"[RESEND ERROR] status={r.status_code} body={r.text}")
            return jsonify({"status": "error", "message": "Email service error.", "detail": r.text}), 502
        return jsonify({"status": "success", "message": "Message sent!"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ------------------------------------------------------------------
# Admin panel — no nav link anywhere; only reachable by typing /admin
# ------------------------------------------------------------------
@app.route("/admin", methods=["GET", "POST"])
def admin():
    if not session.get("is_admin"):
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            if ADMIN_EMAIL and ADMIN_PASSWORD and email == ADMIN_EMAIL.lower() and password == ADMIN_PASSWORD:
                session["is_admin"] = True
                return redirect(url_for("admin"))
            flash("Invalid admin credentials.", "err")
        return render_template("admin_login.html")

    users = User.query.order_by(User.created_at.desc()).all()
    return render_template("admin_dashboard.html", users=users, plans=PLAN_LIMITS)


@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    return redirect(url_for("admin"))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
