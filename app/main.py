"""应用入口：组装路由、建表、种子管理员、异常处理"""
import os
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from .database import Base, engine, SessionLocal
from . import models  # noqa: F401 触发模型注册
from .auth import AuthRedirect, hash_password
from .routers import auth, dashboard, personas, topics, breakdown, scripts, stats, team, settings

app = FastAPI(title="爆款带货智能体工作台")

# 静态资源
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")),
          name="static")


@app.exception_handler(AuthRedirect)
async def auth_redirect_handler(request: Request, exc: AuthRedirect):
    return RedirectResponse(exc.url, status_code=303)


def init_db():
    """建表 + 种子管理员 admin/admin123（首次登录强制改密码）"""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if not db.query(models.User).filter(models.User.username == "admin").first():
            db.add(models.User(username="admin", password_hash=hash_password("admin123"),
                               role="admin", must_change_pw=1))
            db.commit()
            print("[init] 已创建种子管理员 admin / admin123（首次登录需改密码）")
    finally:
        db.close()


init_db()

# 路由组装
app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(personas.router)
app.include_router(topics.router)
app.include_router(breakdown.router)
app.include_router(scripts.router)
app.include_router(stats.router)
app.include_router(team.router)
app.include_router(settings.router)
