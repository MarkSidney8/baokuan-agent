"""系统设置（仅 admin）：AI 服务商 / API Key / Base URL / 模型名，后台可配入库"""
import json
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import User, Setting
from ..auth import require_admin, template_ctx, log_action, redirect_msg
from ..tpl import templates
from ..ai import PROVIDERS, DEFAULT_PROVIDER, test_ai_connection

router = APIRouter(prefix="/settings")

# 旧版键：保存新配置时自动清理，避免两份配置打架
LEGACY_KEYS = ("deepseek_api_key", "deepseek_base_url", "deepseek_model")


def _get_settings(db: Session) -> dict:
    return {s.key: s.value for s in db.query(Setting).all()}


def _set_setting(db: Session, key: str, value: str):
    s = db.query(Setting).filter(Setting.key == key).first()
    if s:
        s.value = value
    else:
        db.add(Setting(key=key, value=value))
    db.commit()


def _current_provider(vals: dict) -> str:
    p = (vals.get("ai_provider") or "").strip()
    return p if p in PROVIDERS else DEFAULT_PROVIDER


def _current_vals(vals: dict, provider: str) -> dict:
    """表单回填值：新键优先，兼容旧 deepseek_* 键，最后取服务商预设默认。"""
    preset = PROVIDERS[provider]
    key = (vals.get("ai_api_key") or vals.get("deepseek_api_key") or "").strip()
    base = (vals.get("ai_base_url") or vals.get("deepseek_base_url") or "").strip() \
        or preset["base_url"]
    model = (vals.get("ai_model") or vals.get("deepseek_model") or "").strip() \
        or preset["default_model"]
    return {"ai_base_url": base, "ai_model": model, "has_key": bool(key)}


@router.get("", response_class=HTMLResponse)
def settings_page(request: Request, user: User = Depends(require_admin),
                  db: Session = Depends(get_db)):
    vals = _get_settings(db)
    provider = _current_provider(vals)
    cur = _current_vals(vals, provider)
    key_val = (vals.get("ai_api_key") or vals.get("deepseek_api_key") or "").strip()
    masked_key = "已配置（" + "*" * 4 + (key_val[-4:] or "") + "）" \
        if key_val else "未配置"
    demo_mode = vals.get("demo_mode", "1") == "1"
    providers = [(pid, p["label"]) for pid, p in PROVIDERS.items()]
    # 给前端 JS：切换服务商时自动填 Base URL / 模型候选 / Key 提示
    presets = {pid: {"label": p["label"], "base_url": p["base_url"],
                     "default_model": p["default_model"], "models": p["models"],
                     "key_hint": p["key_hint"]}
               for pid, p in PROVIDERS.items()}
    return templates.TemplateResponse(request, "settings.html",
        template_ctx(request, user, providers=providers, provider=provider,
                     presets_json=json.dumps(presets, ensure_ascii=False),
                     cur=cur, masked_key=masked_key, demo_mode=demo_mode,
                     msg=request.query_params.get("msg", ""),
                     err=request.query_params.get("err", "")))


@router.post("")
def settings_save(request: Request,
                  ai_provider: str | None = Form(default=None),
                  ai_api_key: str | None = Form(default=None),
                  ai_base_url: str | None = Form(default=None),
                  ai_model: str | None = Form(default=None),
                  demo_mode: str | None = Form(default=None),
                  user: User = Depends(require_admin),
                  db: Session = Depends(get_db)):
    changed = []
    # 有效服务商：表单值优先，否则用库里已存的（用于判断旧 Key 是否可迁移）
    if ai_provider is not None:
        eff_provider = ai_provider.strip()
        if eff_provider not in PROVIDERS:
            eff_provider = DEFAULT_PROVIDER
        _set_setting(db, "ai_provider", eff_provider)
        changed.append("服务商")
    else:
        s = db.query(Setting).filter(Setting.key == "ai_provider").first()
        eff_provider = ((s.value if s else "") or "").strip()
        if eff_provider not in PROVIDERS:
            eff_provider = DEFAULT_PROVIDER
    # Key 为 password 框：留空（空字符串会被解析成 None）表示不修改，避免页面回显泄露
    if ai_api_key:
        _set_setting(db, "ai_api_key", ai_api_key.strip())
        changed.append("API Key")
    elif eff_provider == "deepseek":
        # 未填新 Key 且服务商仍是 DeepSeek：把旧 deepseek_api_key 的值迁移到新键，
        # 避免已配置的 Key 在旧键清理后丢失；换了别的服务商则不迁移，避免拿
        # DeepSeek 的 Key 去调别的服务商接口导致鉴权失败
        legacy = db.query(Setting).filter(Setting.key == "deepseek_api_key").first()
        existing = db.query(Setting).filter(Setting.key == "ai_api_key").first()
        if (legacy and (legacy.value or "").strip()
                and not (existing and (existing.value or "").strip())):
            _set_setting(db, "ai_api_key", legacy.value.strip())
            changed.append("API Key（旧配置迁移）")
    if ai_base_url is not None:
        _set_setting(db, "ai_base_url", ai_base_url.strip())
        changed.append("Base URL")
    if ai_model is not None:
        _set_setting(db, "ai_model", ai_model.strip())
        changed.append("模型")
    if demo_mode is not None:
        _set_setting(db, "demo_mode", "1" if demo_mode == "on" else "0")
        changed.append("演示模式")
    # 旧 deepseek_* 键已迁移到新键，清理避免两份配置打架
    for k in LEGACY_KEYS:
        s = db.query(Setting).filter(Setting.key == k).first()
        if s:
            db.delete(s)
    db.commit()
    log_action(db, user.username, "修改系统设置", "AI 配置：" + "、".join(changed))
    return redirect_msg("/settings", msg="saved")


@router.post("/test")
async def settings_test(request: Request, user: User = Depends(require_admin),
                        db: Session = Depends(get_db)):
    """测试当前 AI 连接是否可用，结果回到设置页提示。"""
    ok, info = await test_ai_connection(db)
    log_action(db, user.username, "测试 AI 连接", info[:120])
    if ok:
        return redirect_msg("/settings", msg="ai_test_ok:" + info[:120])
    return redirect_msg("/settings", err="ai_test_fail:" + info[:160])
