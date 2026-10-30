"""仪表盘"""
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import os
from ..database import get_db
from ..models import User, Persona, Topic, Template, Script
from ..auth import get_current_user, template_ctx

router = APIRouter()
from ..tpl import templates


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, user: User = Depends(get_current_user),
              db: Session = Depends(get_db)):
    msg = request.query_params.get("msg", "")
    err = request.query_params.get("err", "")
    counts = {
        "人设": db.query(Persona).count(),
        "选题": db.query(Topic).count(),
        "制作单": db.query(Script).count(),
        "模板": db.query(Template).count(),
    }
    recent_topics = db.query(Topic).order_by(Topic.id.desc()).limit(5).all()
    todo_topics = db.query(Topic).filter(Topic.status == "待拍").order_by(Topic.id.desc()).limit(10).all()
    return templates.TemplateResponse(request, "dashboard.html",
        template_ctx(request, user, counts=counts, recent_topics=recent_topics,
                     todo_topics=todo_topics, msg=msg, err=err))
