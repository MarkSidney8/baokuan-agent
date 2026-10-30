"""系统设置（仅 admin）：DeepSeek API Key / Base URL / 模型名，后台可配入库"""
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import User, Setting
from ..auth import require_admin, template_ctx, log_action, redirect_msg
from ..tpl import templates
from ..ai import DEFAULT_BASE_URL, DEFAULT_MODEL

router = APIRouter(prefix="/settings")

KEY_FIELDS = [
    ("deepseek_api_key", "DeepSeek API Key", "password", "sk- 开头的密钥，留空则不修改"),
    ("deepseek_base_url", "API Base URL", "text", DEFAULT_BASE_URL),
    ("deepseek_model", "模型名", "text", DEFAULT_MODEL),
]


def _get_settings(db: Session) -> dict:
    return {s.key: s.value for s in db.query(Setting).all()}


def _set_setting(db: Session, key: str, value: str):
    s = db.query(Setting).filter(Setting.key == key).first()
    if s:
        s.value = value
    else:
        db.add(Setting(key=key, value=value))
    db.commit()


@router.get("", response_class=HTMLResponse)
def settings_page(request: Request, user: User = Depends(require_admin),
                  db: Session = Depends(get_db)):
    vals = _get_settings(db)
    masked_key = "已配置（" + "*" * 4 + (vals.get("deepseek_api_key", "")[-4:] or "") + "）" \
        if vals.get("deepseek_api_key") else "未配置"
    return templates.TemplateResponse(request, "settings.html",
        template_ctx(request, user, fields=KEY_FIELDS, vals=vals, masked_key=masked_key,
                     msg=request.query_params.get("msg", ""),
                     err=request.query_params.get("err", "")))


@router.post("")
def settings_save(request: Request,
                  deepseek_api_key: str = Form(""),
                  deepseek_base_url: str = Form(""),
                  deepseek_model: str = Form(""),
                  user: User = Depends(require_admin),
                  db: Session = Depends(get_db)):
    # Key 为 password 框：留空表示不修改，避免页面回显泄露
    if deepseek_api_key.strip():
        _set_setting(db, "deepseek_api_key", deepseek_api_key.strip())
    _set_setting(db, "deepseek_base_url",
                 deepseek_base_url.strip() or DEFAULT_BASE_URL)
    _set_setting(db, "deepseek_model", deepseek_model.strip() or DEFAULT_MODEL)
    log_action(db, user.username, "修改系统设置", "DeepSeek API 配置")
    return redirect_msg("/settings", msg="saved")
