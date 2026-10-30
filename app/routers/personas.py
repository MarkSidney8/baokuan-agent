"""人设管理"""
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import os
from ..database import get_db
from ..models import User, Persona
from ..auth import get_current_user, template_ctx, log_action, redirect_msg
from ..ai import ai_persona, AiNotConfigured, AiCallFailed

router = APIRouter(prefix="/personas")
from ..tpl import templates


@router.get("", response_class=HTMLResponse)
def persona_list(request: Request, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    personas = db.query(Persona).order_by(Persona.id.desc()).all()
    return templates.TemplateResponse(request, "personas.html",
        template_ctx(request, user, personas=personas,
                     msg=request.query_params.get("msg", ""),
                     err=request.query_params.get("err", "")))


@router.get("/new", response_class=HTMLResponse)
def persona_new_page(request: Request, user: User = Depends(get_current_user)):
    return templates.TemplateResponse(request, "persona_form.html", template_ctx(request, user, persona=None))


@router.post("/new")
def persona_create(request: Request, name: str = Form(...), category: str = Form(""),
                   audience: str = Form(""), tone: str = Form(""),
                   persona_desc: str = Form(""), selling_style: str = Form(""),
                   user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.add(Persona(name=name.strip(), category=category.strip(), audience=audience.strip(),
                   tone=tone.strip(), persona_desc=persona_desc.strip(),
                   selling_style=selling_style.strip(), created_by=user.username))
    db.commit()
    log_action(db, user.username, "新建人设", name.strip())
    return RedirectResponse("/personas?msg=created", status_code=303)


@router.post("/ai")
async def persona_ai(request: Request, category: str = Form(...), audience: str = Form(...),
                     user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """AI 生成人设：直接存入列表"""
    try:
        data = await ai_persona(category.strip(), audience.strip(), db)
    except AiNotConfigured as e:
        return redirect_msg("/personas", err=str(e))
    except (AiCallFailed, Exception):
        return redirect_msg("/personas", err="AI调用失败，请稍后重试")
    name = str(data.get("name", "未命名人设"))
    db.add(Persona(name=name, category=category.strip(),
                   audience=str(data.get("audience", audience.strip())),
                   tone=str(data.get("tone", "")), persona_desc=str(data.get("persona_desc", "")),
                   selling_style=str(data.get("selling_style", "")), created_by=user.username))
    db.commit()
    log_action(db, user.username, "AI生成人设", name)
    return RedirectResponse("/personas?msg=ai_ok", status_code=303)


@router.get("/{pid}/edit", response_class=HTMLResponse)
def persona_edit_page(pid: int, request: Request, user: User = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    persona = db.query(Persona).filter(Persona.id == pid).first()
    if not persona:
        return RedirectResponse("/personas?err=not_found", status_code=303)
    return templates.TemplateResponse(request, "persona_form.html", template_ctx(request, user, persona=persona))


@router.post("/{pid}/edit")
def persona_update(pid: int, request: Request, name: str = Form(...), category: str = Form(""),
                   audience: str = Form(""), tone: str = Form(""),
                   persona_desc: str = Form(""), selling_style: str = Form(""),
                   user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    persona = db.query(Persona).filter(Persona.id == pid).first()
    if not persona:
        return RedirectResponse("/personas?err=not_found", status_code=303)
    persona.name, persona.category, persona.audience = name.strip(), category.strip(), audience.strip()
    persona.tone, persona.persona_desc = tone.strip(), persona_desc.strip()
    persona.selling_style = selling_style.strip()
    db.commit()
    log_action(db, user.username, "编辑人设", name.strip())
    return RedirectResponse("/personas?msg=updated", status_code=303)


@router.post("/{pid}/delete")
def persona_delete(pid: int, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    persona = db.query(Persona).filter(Persona.id == pid).first()
    if persona:
        log_action(db, user.username, "删除人设", persona.name)
        db.delete(persona)
        db.commit()
    return RedirectResponse("/personas?msg=deleted", status_code=303)
