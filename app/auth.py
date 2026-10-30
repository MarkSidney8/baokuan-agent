"""认证模块：bcrypt 密码 + itsdangerous 签名会话 cookie"""
import os
import bcrypt
from fastapi import Request, Depends
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from sqlalchemy.orm import Session
from .database import get_db
from .models import User

SECRET_KEY = os.environ.get("SECRET_KEY", "baokuan-dev-secret-change-me")
COOKIE_NAME = "bk_session"
MAX_AGE = 7 * 24 * 3600  # 会话有效期 7 天

_signer = URLSafeTimedSerializer(SECRET_KEY, salt="baokuan-session")


# ---------- 密码 ----------

def hash_password(password: str) -> str:
    """bcrypt 加密（直接用 bcrypt 库，避开 passlib 版本兼容坑）"""
    return bcrypt.hashpw(password.encode("utf-8")[:72], bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8")[:72], password_hash.encode("utf-8"))
    except Exception:
        return False


# ---------- 会话 cookie ----------

def create_session_token(user_id: int) -> str:
    return _signer.dumps({"uid": user_id})


def parse_session_token(token: str) -> int | None:
    try:
        data = _signer.loads(token, max_age=MAX_AGE)
        return int(data.get("uid"))
    except (BadSignature, SignatureExpired, Exception):
        return None


# ---------- 登录态 ----------

class AuthRedirect(Exception):
    """需要跳转的认证异常（未登录 -> /login，无权限 -> /）"""
    def __init__(self, url: str):
        self.url = url


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """依赖：当前登录用户，未登录则抛 AuthRedirect 跳转到登录页"""
    token = request.cookies.get(COOKIE_NAME)
    if token:
        uid = parse_session_token(token)
        if uid:
            user = db.query(User).filter(User.id == uid).first()
            if user:
                return user
    raise AuthRedirect("/login")


def require_admin(user: User = Depends(get_current_user)) -> User:
    """依赖：仅管理员"""
    if user.role != "admin":
        raise AuthRedirect("/?err=only_admin")
    return user


def redirect_msg(url: str, msg: str = "", err: str = ""):
    """PRG 跳转：msg/err 做 URL 编码后拼到查询参数"""
    from urllib.parse import urlencode
    from fastapi.responses import RedirectResponse
    params = {}
    if msg:
        params["msg"] = msg
    if err:
        params["err"] = err
    q = ("?" + urlencode(params)) if params else ""
    return RedirectResponse(url + q, status_code=303)


def template_ctx(request: Request, user: User | None, **kwargs) -> dict:
    """模板公共上下文：request + user + 页面变量"""
    ctx = {"request": request, "user": user}
    ctx.update(kwargs)
    return ctx


def log_action(db: Session, who: str, action: str, detail: str = ""):
    """记录关键写操作到操作日志"""
    from .models import OperationLog
    db.add(OperationLog(who=who, action=action, detail=detail))
    db.commit()
