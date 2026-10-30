"""爆款库：一键复刻爆款视频（保留结构，只替换商品元素）"""
import json
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from sqlalchemy.orm import Session
from ..database import get_db, SessionLocal
from ..models import User, ViralVideo, CloneJob, Script, Template
from ..auth import get_current_user, template_ctx, log_action, redirect_msg
from ..ai import ai_breakdown, ai_clone, AiNotConfigured, AiCallFailed
from ..tpl import templates

router = APIRouter(prefix="/viral")
STATUSES = ["待拆解", "已拆解", "已复刻"]


def _breakdown_of(viral: ViralVideo, db: Session) -> dict:
    """取爆款的五段结构：优先用已拆解模板，否则现场拆解 transcript"""
    return {
        "hook": "", "pain": "", "demo": "",
        "price_anchor": "", "cta": "",
        "product_name": viral.product_name or "",
        "category": viral.category or "",
    }


@router.get("", response_class=HTMLResponse)
def viral_list(request: Request, status: str = "", user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    q = db.query(ViralVideo)
    if status in STATUSES:
        q = q.filter(ViralVideo.status == status)
    videos = q.order_by(ViralVideo.id.desc()).all()
    return templates.TemplateResponse(request, "viral.html",
        template_ctx(request, user, videos=videos, cur_status=status, statuses=STATUSES,
                     msg=request.query_params.get("msg", ""),
                     err=request.query_params.get("err", "")))


@router.get("/new", response_class=HTMLResponse)
def viral_new_page(request: Request, user: User = Depends(get_current_user)):
    return templates.TemplateResponse(request, "viral_form.html",
                                      template_ctx(request, user))


@router.post("/new")
def viral_create(request: Request, title: str = Form(""), author: str = Form(""),
                 source_url: str = Form(""), category: str = Form(""),
                 product_name: str = Form(""), play_count: str = Form(""),
                 like_count: str = Form(""), transcript: str = Form(""),
                 user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.add(ViralVideo(title=title.strip(), author=author.strip(),
                      source_url=source_url.strip(), category=category.strip(),
                      product_name=product_name.strip(), play_count=play_count.strip(),
                      like_count=like_count.strip(), transcript=transcript.strip(),
                      status="待拆解", source="手动", created_by=user.username))
    db.commit()
    log_action(db, user.username, "爆款入库", title.strip() or product_name.strip())
    return RedirectResponse("/viral?msg=created", status_code=303)


@router.post("/seed")
def viral_seed(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """载入演示爆款（2条），方便直接体验一键复刻"""
    demos = [
        {
            "title": "加绒加厚卫衣，29块9包邮，卖爆320万播放",
            "author": "县城穿搭老王", "category": "服装",
            "product_name": "加绒加厚卫衣", "play_count": "320万", "like_count": "18万",
            "transcript": ("还穿那种起球的旧卫衣呢？我这件加绒加厚卫衣，里外两层，"
                           "绒密得抓一把都攥不住！看这做工，针脚细密，帽子立体，"
                           "穿上身版型多正。商场同款卖129，今天直播间只要29块9，"
                           "还包邮！今天下单再送一双袜子，库存就剩200件，"
                           "点小黄车赶紧的！"),
        },
        {
            "title": "免打孔置物架，厨房神器，19块9",
            "author": "巧媳妇收纳", "category": "厨房日用",
            "product_name": "免打孔置物架", "play_count": "180万", "like_count": "9万",
            "transcript": ("厨房调料瓶摆得到处都是？这个免打孔置物架，贴墙一挂就行，"
                           "承重20斤不掉！三层大容量，油盐酱醋全收纳，"
                           "304不锈钢不生锈。超市卖39，今晚19块9带回家！"
                           "前100名再送挂钩一排，点下方链接！"),
        },
    ]
    n = 0
    for d in demos:
        if not db.query(ViralVideo).filter(
                ViralVideo.title == d["title"]).first():
            db.add(ViralVideo(**d, status="待拆解", source="演示",
                              created_by=user.username))
            n += 1
    db.commit()
    log_action(db, user.username, "载入演示爆款", f"{n}条")
    return RedirectResponse(f"/viral?msg=seed_ok_{n}", status_code=303)


@router.get("/{vid}/clone", response_class=HTMLResponse)
async def clone_page(vid: int, request: Request,
                     user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    """一键复刻表单：左原爆款结构（可改），右填新商品元素"""
    viral = db.query(ViralVideo).filter(ViralVideo.id == vid).first()
    if not viral:
        return RedirectResponse("/viral?err=not_found", status_code=303)
    struct = _breakdown_of(viral, db)
    # 预填：现场拆解一次 transcript（演示模式/有Key均可）
    if viral.transcript:
        try:
            bd = await ai_breakdown(viral.transcript, db)
            for k in ("hook", "pain", "demo", "price_anchor", "cta"):
                if isinstance(bd, dict) and bd.get(k):
                    struct[k] = bd[k]
        except (AiNotConfigured, AiCallFailed, Exception):
            pass
    return templates.TemplateResponse(request, "clone_form.html",
        template_ctx(request, user, viral=viral, struct=struct,
                     msg=request.query_params.get("msg", ""),
                     err=request.query_params.get("err", "")))


@router.post("/{vid}/clone")
async def clone_run(vid: int, request: Request,
                    hook: str = Form(""), pain: str = Form(""), demo: str = Form(""),
                    price_anchor: str = Form(""), cta: str = Form(""),
                    new_product: str = Form(...), new_category: str = Form(""),
                    new_price: str = Form(""), new_high_price: str = Form(""),
                    selling_points: str = Form(""),
                    user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    """执行一键复刻：结构保留 + 元素替换 -> 生成制作单"""
    viral = db.query(ViralVideo).filter(ViralVideo.id == vid).first()
    if not viral:
        return RedirectResponse("/viral?err=not_found", status_code=303)
    viral_struct = {"product_name": viral.product_name, "category": viral.category,
                    "hook": hook.strip(), "pain": pain.strip(), "demo": demo.strip(),
                    "price_anchor": price_anchor.strip(), "cta": cta.strip()}
    new_info = {"name": new_product.strip(), "category": new_category.strip(),
                "price": new_price.strip(), "high_price": new_high_price.strip(),
                "selling_points": selling_points.strip()}
    try:
        result = await ai_clone(viral_struct, new_info, db)
    except AiNotConfigured as e:
        return redirect_msg(f"/viral/{vid}/clone", err=str(e))
    except (AiCallFailed, Exception):
        return redirect_msg(f"/viral/{vid}/clone", err="AI调用失败，请稍后重试")

    script = Script(
        product_name=new_info["name"], product_price=new_info["price"],
        product_high_price=new_info["high_price"],
        script_text=result.get("script_text", "") if isinstance(result, dict) else "",
        shots=json.dumps(result.get("shots", []), ensure_ascii=False) if isinstance(result, dict) else "[]",
        image_prompts=result.get("image_prompts", "") if isinstance(result, dict) else "",
        video_prompts=result.get("video_prompts", "") if isinstance(result, dict) else "",
        status="草稿", created_by=user.username)
    db.add(script)
    db.flush()
    db.add(CloneJob(viral_id=viral.id, old_product=viral.product_name,
                    new_product=new_info["name"], new_category=new_info["category"],
                    new_price=new_info["price"], new_high_price=new_info["high_price"],
                    selling_points=new_info["selling_points"],
                    script_id=script.id, created_by=user.username))
    viral.status = "已复刻"
    db.commit()
    log_action(db, user.username, "一键复刻",
               f"{viral.product_name} -> {new_info['name']}")
    return RedirectResponse(f"/scripts/{script.id}?msg=clone_ok", status_code=303)


@router.post("/{vid}/delete")
def viral_delete(vid: int, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    viral = db.query(ViralVideo).filter(ViralVideo.id == vid).first()
    if viral:
        log_action(db, user.username, "删除爆款", viral.title or viral.product_name)
        db.delete(viral)
        db.commit()
    return RedirectResponse("/viral?msg=deleted", status_code=303)
