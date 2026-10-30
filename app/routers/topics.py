"""选题中心"""
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import os
from ..database import get_db
from ..models import User, Topic, Persona
from ..auth import get_current_user, template_ctx, log_action, redirect_msg
from ..ai import ai_topics, AiNotConfigured, AiCallFailed

router = APIRouter(prefix="/topics")
from ..tpl import templates
STATUSES = ["待拍", "制作中", "已发布"]


@router.get("", response_class=HTMLResponse)
def topic_list(request: Request, status: str = "", user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    q = db.query(Topic)
    if status in STATUSES:
        q = q.filter(Topic.status == status)
    topics = q.order_by(Topic.id.desc()).all()
    personas = db.query(Persona).all()
    persona_map = {p.id: p.name for p in personas}
    return templates.TemplateResponse(request, "topics.html",
        template_ctx(request, user, topics=topics, personas=personas, persona_map=persona_map,
                     cur_status=status, statuses=STATUSES,
                     msg=request.query_params.get("msg", ""),
                     err=request.query_params.get("err", "")))


@router.get("/new", response_class=HTMLResponse)
def topic_new_page(request: Request, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    personas = db.query(Persona).all()
    return templates.TemplateResponse(request, "topic_form.html", template_ctx(request, user, topic=None, personas=personas,
                                        statuses=STATUSES))


@router.post("/new")
def topic_create(request: Request, title: str = Form(...), category: str = Form(""),
                 persona_id: str = Form(""), season_tag: str = Form(""),
                 status: str = Form("待拍"), notes: str = Form(""),
                 user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    pid = int(persona_id) if persona_id.strip().isdigit() else None
    db.add(Topic(title=title.strip(), category=category.strip(), persona_id=pid,
                 season_tag=season_tag.strip(), status=status, notes=notes.strip(),
                 created_by=user.username))
    db.commit()
    log_action(db, user.username, "新建选题", title.strip())
    return RedirectResponse("/topics?msg=created", status_code=303)


@router.post("/ai")
async def topic_ai(request: Request, category: str = Form(...), count: str = Form("5"),
                   audience: str = Form(""), user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    """AI 批量生成选题：存入待拍"""
    try:
        n = max(1, min(int(count), 20))
    except ValueError:
        n = 5
    try:
        items = await ai_topics(category.strip(), n, audience.strip(), db)
    except AiNotConfigured as e:
        return redirect_msg("/topics", err=str(e))
    except (AiCallFailed, Exception):
        return redirect_msg("/topics", err="AI调用失败，请稍后重试")
    for it in items:
        if isinstance(it, dict) and it.get("title"):
            db.add(Topic(title=str(it["title"]).strip(), category=category.strip(),
                         season_tag=str(it.get("season_tag", "")).strip(),
                         notes=str(it.get("notes", "")).strip(),
                         status="待拍", created_by=user.username))
    db.commit()
    log_action(db, user.username, "AI批量生成选题", f"{category} x{len(items)}")
    return RedirectResponse(f"/topics?msg=ai_ok_{len(items)}", status_code=303)


@router.get("/{tid}/edit", response_class=HTMLResponse)
def topic_edit_page(tid: int, request: Request, user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    topic = db.query(Topic).filter(Topic.id == tid).first()
    if not topic:
        return RedirectResponse("/topics?err=not_found", status_code=303)
    personas = db.query(Persona).all()
    return templates.TemplateResponse(request, "topic_form.html", template_ctx(request, user, topic=topic, personas=personas,
                                        statuses=STATUSES))


@router.post("/{tid}/edit")
def topic_update(tid: int, request: Request, title: str = Form(...), category: str = Form(""),
                 persona_id: str = Form(""), season_tag: str = Form(""),
                 status: str = Form("待拍"), notes: str = Form(""),
                 user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    topic = db.query(Topic).filter(Topic.id == tid).first()
    if not topic:
        return RedirectResponse("/topics?err=not_found", status_code=303)
    topic.title, topic.category = title.strip(), category.strip()
    topic.persona_id = int(persona_id) if persona_id.strip().isdigit() else None
    topic.season_tag, topic.status, topic.notes = season_tag.strip(), status, notes.strip()
    db.commit()
    log_action(db, user.username, "编辑选题", title.strip())
    return RedirectResponse("/topics?msg=updated", status_code=303)


@router.post("/{tid}/status")
def topic_status(tid: int, status: str = Form(...), user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    """快捷改状态"""
    topic = db.query(Topic).filter(Topic.id == tid).first()
    if topic and status in STATUSES:
        topic.status = status
        db.commit()
        log_action(db, user.username, "选题改状态", f"{topic.title} -> {status}")
    return RedirectResponse("/topics?msg=status_ok", status_code=303)


@router.post("/{tid}/delete")
def topic_delete(tid: int, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    topic = db.query(Topic).filter(Topic.id == tid).first()
    if topic:
        log_action(db, user.username, "删除选题", topic.title)
        db.delete(topic)
        db.commit()
    return RedirectResponse("/topics?msg=deleted", status_code=303)
