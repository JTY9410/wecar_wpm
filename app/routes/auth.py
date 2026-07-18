from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required, login_user, logout_user

from app.extensions import db
from app.models import User

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            if user.role != "ADMIN" and not user.is_approved:
                flash("관리자 승인 대기 중인 계정입니다. 승인 후 로그인할 수 있습니다.", "warning")
                return render_template("login.html")
            login_user(user)
            flash(f"환영합니다, {user.username}님!", "success")
            if user.is_admin:
                return redirect(url_for("admin.dashboard"))
            return redirect(url_for("market.index"))
        flash("아이디 또는 비밀번호가 올바르지 않습니다.", "danger")
    return render_template("login.html")


@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        affiliation = request.form.get("affiliation", "").strip()
        if not username or not password:
            flash("아이디와 비밀번호를 입력해주세요.", "danger")
            return render_template("signup.html", form=request.form)
        if User.query.filter_by(username=username).first():
            flash("이미 사용 중인 아이디입니다.", "danger")
            return render_template("signup.html", form=request.form)
        user = User(
            username=username, role="USER", name=name, phone=phone,
            affiliation=affiliation, is_approved=False,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash("회원가입이 완료되었습니다. 관리자 승인 후 로그인할 수 있습니다.", "success")
        return redirect(url_for("auth.login"))
    return render_template("signup.html", form={})


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("로그아웃되었습니다.", "info")
    return redirect(url_for("auth.login"))
