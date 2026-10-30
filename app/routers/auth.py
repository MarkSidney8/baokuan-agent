"""登录/登出/改密码"""
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import os
from ..database import get_db
from ..models import User
from ..auth import (
    hash_password, verify_password, create_session_token,
    COOKIE_NAME, get_current_user, template_ctx, log_action, AuthRedirect,
)

router = APIRouter()
from ..tpl import templates


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if request.cookies.get(COOKIE_NAME):
        return RedirectResponse("/", status_code=303)
    msg = request.query_params.get("msg", "")
    return templates.TemplateResponse(request, "login.html", {"request": request, "msg": msg})


@router.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...),
          db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(request, "login.html", {"request": request, "msg": "用户名或密码错误"}, status_code=401)
    resp = RedirectResponse("/change-password?msg=first" if user.must_change_pw else "/", status_code=303)
    resp.set_cookie(COOKIE_NAME, create_session_token(user.id), httponly=True, max_age=7 * 24 * 3600)
    log_action(db, user.username, "登录", "")
    return resp


@router.get("/logout")
def logout():
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie(COOKIE_NAME)
    return resp


@router.get("/change-password", response_class=HTMLResponse)
def change_password_page(request: Request, user: User = Depends(get_current_user),
                         db: Session = Depends(get_db)):
    msg = request.query_params.get("msg", "")
    first = msg == "first"
    tip = "首次登录，请先修改默认密码" if first else ""
    return templates.TemplateResponse(request, "change_password.html", template_ctx(request, user, tip=tip))


@router.post("/change-password")
def change_password(request: Request, old_password: str = Form(...),
                    new_password: str = Form(...), new_password2: str = Form(...),
                    user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(old_password, user.password_hash):
        return RedirectResponse("/change-password?msg=old_err", status_code=303)
    if len(new_password) < 6:
        return RedirectResponse("/change-password?msg=len_err", status_code=303)
    if new_password != new_password2:
        return RedirectResponse("/change-password?msg=diff_err", status_code=303)
    user.password_hash = hash_password(new_password)
    user.must_change_pw = 0
    db.commit()
    log_action(db, user.username, "修改密码", "")
    return RedirectResponse("/?msg=pw_ok", status_code=303)
