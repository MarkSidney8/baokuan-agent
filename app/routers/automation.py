"""自动化任务页面：查看定时任务状态 + 手动立即执行"""
from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse, HTMLResponse
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import User, Setting, ViralVideo, Persona
from ..auth import get_current_user, template_ctx, log_action, redirect_msg
from ..automation import run_daily_topics, run_auto_breakdown
from ..tpl import templates

router = APIRouter(prefix="/automation")


def _get(db: Session, key: str, default: str = "") -> str:
    s = db.query(Setting).filter(Setting.key == key).first()
    return s.value if s else default


@router.get("", response_class=HTMLResponse)
def automation_page(request: Request, user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    pending = db.query(ViralVideo).filter(ViralVideo.status == "待拆解").count()
    cat_count = db.query(Persona.category).distinct().count()
    tasks = [
        {"key": "daily_topics", "name": "每日自动选题",
         "desc": f"每天 08:00 为每个有人设的类目（当前 {cat_count} 个）各生成 5 条选题，存入待拍",
         "last": _get(db, "automation_last_topics", "尚未运行")},
        {"key": "auto_breakdown", "name": "爆款自动拆解",
         "desc": f"每天 08:30 自动拆解待拆解的爆款（当前 {pending} 条），拆解结果存入模板库",
         "last": _get(db, "automation_last_breakdown", "尚未运行")},
    ]
    return templates.TemplateResponse(request, "automation.html",
        template_ctx(request, user, tasks=tasks,
                     demo=_get(db, "demo_mode", "1") == "1",
                     msg=request.query_params.get("msg", ""),
                     err=request.query_params.get("err", "")))


@router.post("/run/{name}")
def automation_run(name: str, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    if name == "daily_topics":
        result = run_daily_topics()
    elif name == "auto_breakdown":
        result = run_auto_breakdown()
    else:
        return RedirectResponse("/automation?err=not_found", status_code=303)
    log_action(db, user.username, "手动执行自动化任务", f"{name}：{result}")
    return redirect_msg("/automation", msg=f"auto_done_{result}")
