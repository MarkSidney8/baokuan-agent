"""自动化任务：定时/手动批量跑选题生成与爆款拆解。

由 APScheduler 每天定时触发，也可在 /automation 页面手动立即执行。
无 Key 时走演示模式（后台系统设置可开关），有 Key 走真实 AI。
"""
import asyncio
from datetime import datetime
from .database import SessionLocal
from .models import Topic, Persona, ViralVideo, Template, Setting
from .ai import ai_topics, ai_breakdown, AiNotConfigured


def _stamp(db, key: str, text: str):
    s = db.query(Setting).filter(Setting.key == key).first()
    val = datetime.now().strftime("%m-%d %H:%M") + "｜" + text
    if s:
        s.value = val
    else:
        db.add(Setting(key=key, value=val))
    db.commit()


def run_daily_topics() -> str:
    """每日自动选题：为每个有人设的类目各生成 5 条，存入待拍（标题去重）"""
    db = SessionLocal()
    try:
        cats: dict[str, str] = {}
        for p in db.query(Persona).all():
            if p.category and p.category not in cats:
                cats[p.category] = p.audience or ""
        if not cats:
            return "没有人设类目，请先去人设管理添加"
        existed = {t[0] for t in db.query(Topic.title).all()}
        total = 0
        for cat, aud in list(cats.items())[:5]:
            try:
                items = asyncio.run(ai_topics(cat, 5, aud, db))
            except AiNotConfigured:
                return "未配置 Key 且演示模式已关闭，请先配置"
            except Exception:
                continue
            for it in items or []:
                title = str(it.get("title", "")).strip()[:250] if isinstance(it, dict) else ""
                if title and title not in existed:
                    db.add(Topic(title=title, category=cat,
                                 season_tag=str(it.get("season_tag", ""))[:60],
                                 notes=str(it.get("notes", ""))[:500],
                                 status="待拍", created_by="自动化任务"))
                    existed.add(title)
                    total += 1
        db.commit()
        msg = f"生成选题 {total} 条（{len(cats)} 个类目）"
        _stamp(db, "automation_last_topics", msg)
        return msg
    finally:
        db.close()


def run_auto_breakdown() -> str:
    """自动拆解：把待拆解的爆款逐条拆解，存入模板库"""
    db = SessionLocal()
    try:
        videos = db.query(ViralVideo).filter(
            ViralVideo.status == "待拆解").limit(10).all()
        if not videos:
            return "没有待拆解的爆款"
        n = 0
        for v in videos:
            if not (v.transcript or "").strip():
                continue
            try:
                bd = asyncio.run(ai_breakdown(v.transcript, db))
            except AiNotConfigured:
                return "未配置 Key 且演示模式已关闭，请先配置"
            except Exception:
                continue
            if isinstance(bd, dict):
                db.add(Template(
                    name=((v.title or v.product_name)[:40] or "爆款") + "·拆解",
                    source_desc=f"来源：{v.author}《{v.title}》播放{v.play_count}",
                    hook=str(bd.get("hook", "")), pain=str(bd.get("pain", "")),
                    demo=str(bd.get("demo", "")),
                    price_anchor=str(bd.get("price_anchor", "")),
                    cta=str(bd.get("cta", "")),
                    created_by="自动化任务"))
                v.status = "已拆解"
                n += 1
        db.commit()
        msg = f"自动拆解 {n} 条爆款，已存入模板库"
        _stamp(db, "automation_last_breakdown", msg)
        return msg
    finally:
        db.close()
