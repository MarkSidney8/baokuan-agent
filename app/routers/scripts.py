"""制作台：制作单 -> AI 生成脚本/分镜/提示词 -> 编辑保存 -> 确认"""
import json
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import os
from ..database import get_db
from ..models import User, Script, Topic, Template
from ..auth import get_current_user, template_ctx, log_action, redirect_msg
from ..ai import ai_script, AiNotConfigured, AiCallFailed

router = APIRouter(prefix="/scripts")
from ..tpl import templates


def _shots_text(shots_json: str) -> str:
    """分镜 JSON 转可读文本"""
    try:
        shots = json.loads(shots_json or "[]")
    except Exception:
        return shots_json or ""
    if isinstance(shots, list):
        return "\n".join(
            f"[{s.get('time', '')}] {s.get('shot', '')}｜字幕：{s.get('caption', '')}"
            if isinstance(s, dict) else str(s) for s in shots)
    return shots_json


@router.get("", response_class=HTMLResponse)
def script_list(request: Request, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    scripts = db.query(Script).order_by(Script.id.desc()).all()
    return templates.TemplateResponse(request, "scripts.html",
        template_ctx(request, user, scripts=scripts,
                     msg=request.query_params.get("msg", ""),
                     err=request.query_params.get("err", "")))


@router.get("/new", response_class=HTMLResponse)
def script_new_page(request: Request, user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    topics = db.query(Topic).order_by(Topic.id.desc()).all()
    tmpls = db.query(Template).order_by(Template.id.desc()).all()
    return templates.TemplateResponse(request, "script_form.html", template_ctx(request, user, script=None,
                                         topics=topics, templates=tmpls))


@router.post("/new")
def script_create(request: Request, topic_id: str = Form(""), template_id: str = Form(""),
                  product_name: str = Form(...), product_price: str = Form(""),
                  product_high_price: str = Form(""), commission: str = Form(""),
                  user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    s = Script(
        topic_id=int(topic_id) if topic_id.strip().isdigit() else None,
        template_id=int(template_id) if template_id.strip().isdigit() else None,
        product_name=product_name.strip(), product_price=product_price.strip(),
        product_high_price=product_high_price.strip(), commission=commission.strip(),
        created_by=user.username)
    db.add(s)
    db.commit()
    # 选题进入制作中
    if s.topic_id:
        t = db.query(Topic).filter(Topic.id == s.topic_id).first()
        if t and t.status == "待拍":
            t.status = "制作中"
            db.commit()
    log_action(db, user.username, "新建制作单", product_name.strip())
    return RedirectResponse(f"/scripts/{s.id}", status_code=303)


@router.get("/{sid}", response_class=HTMLResponse)
def script_detail(sid: int, request: Request, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    s = db.query(Script).filter(Script.id == sid).first()
    if not s:
        return redirect_msg("/scripts", err="制作单不存在")
    return templates.TemplateResponse(request, "script_detail.html",
        template_ctx(request, user, script=s, shots_text=_shots_text(s.shots),
                     msg=request.query_params.get("msg", ""),
                     err=request.query_params.get("err", "")))


@router.post("/{sid}/generate")
async def script_generate(sid: int, request: Request,
                          user: User = Depends(get_current_user),
                          db: Session = Depends(get_db)):
    """AI 生成脚本/分镜/提示词并回填"""
    s = db.query(Script).filter(Script.id == sid).first()
    if not s:
        return redirect_msg("/scripts", err="制作单不存在")
    tmpl = {"hook": "", "pain": "", "demo": "", "price_anchor": "", "cta": ""}
    if s.template:
        tmpl = {"hook": s.template.hook, "pain": s.template.pain, "demo": s.template.demo,
                "price_anchor": s.template.price_anchor, "cta": s.template.cta}
    try:
        data = await ai_script(
            s.topic.title if s.topic else "",
            tmpl,
            {"name": s.product_name, "price": s.product_price,
             "high_price": s.product_high_price, "commission": s.commission},
            db)
    except AiNotConfigured as e:
        return redirect_msg(f"/scripts/{sid}", err=str(e))
    except (AiCallFailed, Exception):
        return redirect_msg(f"/scripts/{sid}", err="AI调用失败，请稍后重试")
    s.script_text = str(data.get("script_text", ""))
    shots = data.get("shots", [])
    s.shots = json.dumps(shots, ensure_ascii=False) if not isinstance(shots, str) else shots
    s.image_prompts = str(data.get("image_prompts", ""))
    s.video_prompts = str(data.get("video_prompts", ""))
    db.commit()
    log_action(db, user.username, "AI生成脚本", f"制作单#{sid} {s.product_name}")
    return redirect_msg(f"/scripts/{sid}", msg="ai_ok")


@router.post("/{sid}/save")
def script_save(sid: int, request: Request, script_text: str = Form(""),
                image_prompts: str = Form(""), video_prompts: str = Form(""),
                user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """保存人工编辑后的脚本/提示词"""
    s = db.query(Script).filter(Script.id == sid).first()
    if not s:
        return redirect_msg("/scripts", err="制作单不存在")
    s.script_text, s.image_prompts, s.video_prompts = script_text, image_prompts, video_prompts
    db.commit()
    log_action(db, user.username, "编辑制作单", f"制作单#{sid}")
    return redirect_msg(f"/scripts/{sid}", msg="saved")


@router.post("/{sid}/confirm")
def script_confirm(sid: int, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    s = db.query(Script).filter(Script.id == sid).first()
    if s:
        s.status = "已确认"
        db.commit()
        log_action(db, user.username, "确认制作单", f"制作单#{sid} {s.product_name}")
    return redirect_msg(f"/scripts/{sid}", msg="confirmed")


@router.post("/{sid}/delete")
def script_delete(sid: int, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    s = db.query(Script).filter(Script.id == sid).first()
    if s:
        log_action(db, user.username, "删除制作单", f"制作单#{sid} {s.product_name}")
        db.delete(s)
        db.commit()
    return redirect_msg("/scripts", msg="deleted")
