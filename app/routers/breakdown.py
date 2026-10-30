"""爆款拆解：粘贴文案 -> AI 拆解 -> 存为模板"""
import json
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import os
from ..database import get_db
from ..models import User, Template
from ..auth import get_current_user, template_ctx, log_action, redirect_msg
from ..ai import ai_breakdown, AiNotConfigured, AiCallFailed

router = APIRouter(prefix="/breakdown")
from ..tpl import templates
FIELDS = [("hook", "钩子（0-3秒）"), ("pain", "痛点"), ("demo", "演示（3-15秒）"),
          ("price_anchor", "价格锚点（15-25秒）"), ("cta", "催单（25-30秒）")]


@router.get("", response_class=HTMLResponse)
def breakdown_page(request: Request, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    saved = db.query(Template).order_by(Template.id.desc()).limit(8).all()
    return templates.TemplateResponse(request, "breakdown.html",
        template_ctx(request, user, result=None, source_text="", saved=saved,
                     fields=FIELDS, msg=request.query_params.get("msg", ""),
                     err=request.query_params.get("err", "")))


@router.post("/analyze", response_class=HTMLResponse)
async def breakdown_analyze(request: Request, source_text: str = Form(...),
                            user: User = Depends(get_current_user),
                            db: Session = Depends(get_db)):
    """AI 拆解：结果直接渲染在页面上，下方有"存为模板"表单"""
    saved = db.query(Template).order_by(Template.id.desc()).limit(8).all()
    try:
        data = await ai_breakdown(source_text, db)
    except AiNotConfigured as e:
        return templates.TemplateResponse(request, "breakdown.html",
            template_ctx(request, user, result=None, source_text=source_text,
                         saved=saved, fields=FIELDS, err=str(e)), status_code=200)
    except (AiCallFailed, Exception):
        return templates.TemplateResponse(request, "breakdown.html",
            template_ctx(request, user, result=None, source_text=source_text,
                         saved=saved, fields=FIELDS, err="AI调用失败，请稍后重试"),
            status_code=200)
    result = {k: str(data.get(k, "")) for k, _ in FIELDS}
    return templates.TemplateResponse(request, "breakdown.html",
        template_ctx(request, user, result=result, source_text=source_text,
                     saved=saved, fields=FIELDS, msg="ai_ok"))


@router.post("/save")
def breakdown_save(request: Request, name: str = Form(...), source_desc: str = Form(""),
                   hook: str = Form(""), pain: str = Form(""), demo: str = Form(""),
                   price_anchor: str = Form(""), cta: str = Form(""),
                   user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    full = {"hook": hook, "pain": pain, "demo": demo,
            "price_anchor": price_anchor, "cta": cta}
    db.add(Template(name=name.strip(), source_desc=source_desc.strip(), hook=hook.strip(),
                    pain=pain.strip(), demo=demo.strip(), price_anchor=price_anchor.strip(),
                    cta=cta.strip(), full_structure=json.dumps(full, ensure_ascii=False),
                    created_by=user.username))
    db.commit()
    log_action(db, user.username, "拆解存为模板", name.strip())
    return redirect_msg("/breakdown", msg="saved")
