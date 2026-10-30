"""团队管理（仅 admin）：用户增删改密 + 操作日志"""
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import os
from ..database import get_db
from ..models import User, OperationLog
from ..auth import require_admin, template_ctx, log_action, redirect_msg, hash_password

router = APIRouter(prefix="/team")
from ..tpl import templates


@router.get("", response_class=HTMLResponse)
def team_page(request: Request, user: User = Depends(require_admin),
              db: Session = Depends(get_db)):
    users = db.query(User).order_by(User.id).all()
    logs = db.query(OperationLog).order_by(OperationLog.id.desc()).limit(50).all()
    return templates.TemplateResponse(request, "team.html",
        template_ctx(request, user, users=users, logs=logs,
                     msg=request.query_params.get("msg", ""),
                     err=request.query_params.get("err", "")))


@router.post("/add")
def team_add(username: str = Form(...), password: str = Form(...),
             role: str = Form("member"), user: User = Depends(require_admin),
             db: Session = Depends(get_db)):
    username = username.strip()
    if not username or len(password) < 6:
        return redirect_msg("/team", err="用户名不能为空，密码至少6位")
    if role not in ("admin", "member"):
        role = "member"
    if db.query(User).filter(User.username == username).first():
        return redirect_msg("/team", err="用户名已存在")
    db.add(User(username=username, password_hash=hash_password(password), role=role))
    db.commit()
    log_action(db, user.username, "新增成员", f"{username}({role})")
    return redirect_msg("/team", msg="created")


@router.post("/{uid}/reset")
def team_reset(uid: int, new_password: str = Form(...),
               user: User = Depends(require_admin), db: Session = Depends(get_db)):
    target = db.query(User).filter(User.id == uid).first()
    if not target:
        return redirect_msg("/team", err="用户不存在")
    if len(new_password) < 6:
        return redirect_msg("/team", err="密码至少6位")
    target.password_hash = hash_password(new_password)
    target.must_change_pw = 1  # 重置后要求对方首次登录改密码
    db.commit()
    log_action(db, user.username, "重置密码", target.username)
    return redirect_msg("/team", msg="pw_reset")


@router.post("/{uid}/delete")
def team_delete(uid: int, user: User = Depends(require_admin),
                db: Session = Depends(get_db)):
    target = db.query(User).filter(User.id == uid).first()
    if not target:
        return redirect_msg("/team", err="用户不存在")
    if target.id == user.id:
        return redirect_msg("/team", err="不能删除自己")
    log_action(db, user.username, "删除成员", target.username)
    db.delete(target)
    db.commit()
    return redirect_msg("/team", msg="deleted")
