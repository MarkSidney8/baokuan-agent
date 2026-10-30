"""数据复盘：录入视频数据 -> AI 诊断 -> 列表展示"""
from datetime import date
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import os
from ..database import get_db
from ..models import User, VideoStat, Script
from ..auth import get_current_user, template_ctx, log_action, redirect_msg
from ..ai import ai_diagnose, AiNotConfigured, AiCallFailed

router = APIRouter(prefix="/stats")
from ..tpl import templates


def _f(v: str, default: float = 0.0) -> float:
    try:
        return float(v)
    except (ValueError, TypeError):
        return default


def _i(v: str, default: int = 0) -> int:
    try:
        return int(float(v))
    except (ValueError, TypeError):
        return default


@router.get("", response_class=HTMLResponse)
def stat_list(request: Request, user: User = Depends(get_current_user),
              db: Session = Depends(get_db)):
    stats = db.query(VideoStat).order_by(VideoStat.id.desc()).all()
    return templates.TemplateResponse(request, "stats.html",
        template_ctx(request, user, stats=stats,
                     msg=request.query_params.get("msg", ""),
                     err=request.query_params.get("err", "")))


@router.get("/new", response_class=HTMLResponse)
def stat_new_page(request: Request, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    scripts = db.query(Script).order_by(Script.id.desc()).all()
    return templates.TemplateResponse(request, "stat_form.html",
        template_ctx(request, user, scripts=scripts, today=date.today().isoformat()))


@router.post("/new")
async def stat_create(request: Request, script_id: str = Form(""),
                      play_count: str = Form("0"), finish_rate: str = Form("0"),
                      click_rate: str = Form("0"), orders: str = Form("0"),
                      gpm: str = Form("0"), stat_date: str = Form(""),
                      action: str = Form("save"),
                      user: User = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    """action=save 直接保存；action=diagnose 先 AI 诊断再保存"""
    metrics = {
        "play_count": _i(play_count), "finish_rate": _f(finish_rate),
        "click_rate": _f(click_rate), "orders": _i(orders), "gpm": _f(gpm),
    }
    ai_advice = ""
    if action == "diagnose":
        try:
            ai_advice = await ai_diagnose(metrics, db)
        except AiNotConfigured as e:
            return redirect_msg("/stats/new", err=str(e))
        except (AiCallFailed, Exception):
            return redirect_msg("/stats/new", err="AI调用失败，请稍后重试")
    st = VideoStat(
        script_id=int(script_id) if script_id.strip().isdigit() else None,
        stat_date=stat_date.strip() or date.today().isoformat(),
        ai_advice=ai_advice, created_by=user.username, **metrics)
    db.add(st)
    db.commit()
    log_action(db, user.username, "录入复盘数据" + ("+AI诊断" if ai_advice else ""),
               f"播放{metrics['play_count']} 完播{metrics['finish_rate']}%")
    return redirect_msg("/stats", msg="ai_ok" if ai_advice else "created")


@router.post("/{stid}/delete")
def stat_delete(stid: int, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    st = db.query(VideoStat).filter(VideoStat.id == stid).first()
    if st:
        log_action(db, user.username, "删除复盘数据", f"记录#{stid}")
        db.delete(st)
        db.commit()
    return redirect_msg("/stats", msg="deleted")
