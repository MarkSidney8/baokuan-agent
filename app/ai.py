"""AI 接入：httpx 调用 DeepSeek API。

配置优先级：数据库 Settings 表 > 环境变量。
无 key 时抛 AiNotConfigured，路由层捕获后展示友好中文提示（不 500）。
"""
import json
import os
import httpx

DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-chat"


class AiNotConfigured(Exception):
    """未配置 API Key"""
    pass


class AiCallFailed(Exception):
    """API 调用失败（网络/鉴权/解析等）"""
    pass


# 统一 system prompt：所有 AI 生成都遵守下沉市场 + 普通人语气 + 禁AI味 + 30秒结构
SYSTEM_PROMPT = (
    "你是专为中国下沉市场（县城、小镇用户）服务的短视频带货文案专家。\n"
    "硬性要求：\n"
    "1. 所有口播文案必须用普通人说话的语气，像邻居熟人聊天，禁用说教口吻；\n"
    "2. 禁用AI味总结句，绝不使用\"把规矩立住\"\"问题不在你而在…\"\"说到底\""
    "\"归根结底\"\"归根到底\"这类句式；\n"
    "3. 严格遵循30秒短视频口播结构：0-3秒钩子（痛点/悬念）、3-15秒演示（展示效果）、"
    "15-25秒价格对比（原价vs现价）、25-30秒催单（限时限量话术）；\n"
    "4. 用词接地气，多用口语，少用书面语；\n"
    "5. 需要返回结构化数据时，只返回纯 JSON，不要 markdown 代码块，不要多余解释。"
)


def get_ai_config(db=None):
    """读取 AI 配置，返回 (api_key, base_url, model)。

    优先级：数据库 Settings 表 > 环境变量 DEEPSEEK_API_KEY / DEEPSEEK_BASE_URL / DEEPSEEK_MODEL。
    无 key 时抛 AiNotConfigured。
    """
    key = base = model = ""
    if db is not None:
        try:
            from .models import Setting
            rows = {s.key: s.value for s in db.query(Setting).all()}
            key = (rows.get("deepseek_api_key") or "").strip()
            base = (rows.get("deepseek_base_url") or "").strip()
            model = (rows.get("deepseek_model") or "").strip()
        except Exception:
            pass  # 表不存在等异常时降级走环境变量
    key = key or os.environ.get("DEEPSEEK_API_KEY", "").strip()
    base = base or os.environ.get("DEEPSEEK_BASE_URL", "").strip() or DEFAULT_BASE_URL
    model = model or os.environ.get("DEEPSEEK_MODEL", "").strip() or DEFAULT_MODEL
    if not key:
        raise AiNotConfigured(
            "未配置 DeepSeek API Key，请在后台「系统设置」页填写，"
            "或在服务器环境变量中配置 DEEPSEEK_API_KEY 后重启")
    return key, base, model


def _parse_json(text):
    """容错解析：去掉可能的代码块围栏后解析 JSON"""
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`").strip()
        if t.startswith("json"):
            t = t[4:].strip()
    return json.loads(t)


async def _chat(system, user_prompt, db=None):
    key, base_url, model = get_ai_config(db)
    url = base_url.rstrip("/") + "/chat/completions"
    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post(
                url,
                headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.8,
                },
            )
        if resp.status_code != 200:
            raise AiCallFailed("AI 接口返回 %s：%s" % (resp.status_code, resp.text[:200]))
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except (AiNotConfigured, AiCallFailed):
        raise
    except Exception as e:
        raise AiCallFailed("AI 调用失败：%s" % e)


async def ai_persona(category, audience, db=None):
    """AI 生成人设，返回 {name, audience, tone, persona_desc, selling_style}"""
    prompt = (
        "为短视频带货账号设计一个人设。\n类目：%s\n目标人群：%s\n"
        "返回 JSON，字段：name（账号名，4-8字，接地气）、audience（目标人群描述）、"
        "tone（语气风格）、persona_desc（人设描述，100字内）、selling_style（带货风格，80字内）。"
        % (category, audience)
    )
    return _parse_json(await _chat(SYSTEM_PROMPT, prompt, db))


async def ai_topics(category, count, audience, db=None):
    """AI 批量生成选题，返回 [{title, season_tag, notes}]"""
    count = max(1, min(count, 20))
    prompt = (
        "为短视频带货账号批量生成选题。\n类目：%s\n目标人群：%s\n数量：%s 条\n"
        "每条选题要具体、可拍、带钩子角度，适合下沉市场用户。\n"
        "返回 JSON 数组，每项字段：title（选题标题）、season_tag（季节/热点标签）、"
        "notes（拍摄要点一句话）。" % (category, audience, count)
    )
    result = _parse_json(await _chat(SYSTEM_PROMPT, prompt, db))
    return result if isinstance(result, list) else []


async def ai_breakdown(text, db=None):
    """AI 拆解爆款文案，返回 {hook, pain, demo, price_anchor, cta}"""
    prompt = (
        "把下面这条爆款带货短视频的口播文案/描述，按结构拆解。\n"
        "返回 JSON，字段：hook（0-3秒钩子原文或提炼）、pain（痛点）、"
        "demo（3-15秒演示环节）、price_anchor（15-25秒价格对比话术）、"
        "cta（25-30秒催单话术）。\n文案如下：\n%s" % text[:4000]
    )
    return _parse_json(await _chat(SYSTEM_PROMPT, prompt, db))


async def ai_script(topic_title, template, product, db=None):
    """AI 生成制作脚本，返回 {script_text, shots, image_prompts, video_prompts}"""
    prompt = (
        "为一条30秒带货短视频生成完整制作脚本。\n"
        "选题：%s\n"
        "爆款结构参考：钩子=%s；痛点=%s；演示=%s；价格对比=%s；催单=%s\n"
        "商品：%s，现价%s元，原价/对比价%s元，佣金%s。\n"
        "返回 JSON，字段：\n"
        "1. script_text：30秒口播全文，按【0-3秒钩子】【3-15秒演示】"
        "【15-25秒价格对比】【25-30秒催单】分段；\n"
        "2. shots：分镜数组，每项 {time（时间段）, shot（画面描述）, "
        "caption（字幕/口播对应句）}，4-6镜；\n"
        "3. image_prompts：生图提示词（封面+关键帧，中文描述）；\n"
        "4. video_prompts：图生视频提示词（每镜一句话，中文描述运镜和动作）。"
        % (topic_title, template.get("hook", ""), template.get("pain", ""),
           template.get("demo", ""), template.get("price_anchor", ""),
           template.get("cta", ""), product.get("name", ""), product.get("price", ""),
           product.get("high_price", ""), product.get("commission", ""))
    )
    return _parse_json(await _chat(SYSTEM_PROMPT, prompt, db))


async def ai_diagnose(metrics, db=None):
    """AI 诊断视频数据，返回中文优化建议纯文本"""
    prompt = (
        "分析下面这条带货短视频的数据，给出优化建议。\n"
        "播放量：%s，完播率：%s%%，商品点击率：%s%%，成交单数：%s，"
        "GPM（千次播放成交额）：%s。\n"
        "参考基准：完播率低于15%说明前3秒钩子有问题；有点击无转化说明价格/信任话术有问题；"
        "GPM 达标（类目相关）可放大投放。\n"
        "用中文分点输出：【诊断结论】【核心问题】【优化动作】三部分，每部分2-4条，"
        "语言直白、可执行。"
        % (metrics.get("play_count", 0), metrics.get("finish_rate", 0),
           metrics.get("click_rate", 0), metrics.get("orders", 0), metrics.get("gpm", 0))
    )
    try:
        return await _chat(SYSTEM_PROMPT, prompt, db)
    except AiNotConfigured:
        if _demo_enabled(db):
            return _demo_diagnose(metrics)
        raise


# ---------------------------------------------------------------- 演示模式
# 无 Key 时的降级：后台「系统设置」可开关 demo_mode（默认开）。
# 所有演示输出均带【演示数据】标记，配置真实 Key 后自动走 AI。

DEMO_NOTE = "【演示数据】当前为演示模式（未配置 DeepSeek Key），配置后将由 AI 真实生成。"


def _demo_enabled(db=None) -> bool:
    if db is None:
        return True
    try:
        from .models import Setting
        s = db.query(Setting).filter(Setting.key == "demo_mode").first()
        return (s.value if s else "1") == "1"
    except Exception:
        return True


def _demo_wrap(func):
    """给 ai_* 函数包一层演示降级"""
    import functools

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        db = kwargs.get("db")
        try:
            return await func(*args, **kwargs)
        except AiNotConfigured:
            if _demo_enabled(db):
                demo_fn = globals().get("_demo_" + func.__name__[3:])
                if demo_fn:
                    return demo_fn(*args, **kwargs)
            raise
    return wrapper


def _demo_persona(category, audience, db=None):
    return {
        "name": f"【演示】{category}严选官",
        "audience": audience or "县城30-50岁女性",
        "tone": "邻家大姐口语",
        "persona_desc": f"专注{category}的实在人，只讲真实体验。" + DEMO_NOTE,
        "selling_style": "先演示再报价，不说教，只讲真实体验。" + DEMO_NOTE,
    }


def _demo_topics(category, count, audience, db=None):
    seeds = [
        ("爆款实测", "把最火的那款拆开给你看，值不值这个价"),
        ("避坑指南", "买{cat}最容易踩的3个坑，第2个最多人中招"),
        ("价格对比", "超市卖{high}，我这{low}，同样的东西"),
        ("真实体验", "用了7天，说点大实话"),
        ("场景种草", "有了它，{aud}都说方便"),
    ]
    out = []
    for i in range(count):
        k, note = seeds[i % len(seeds)]
        out.append({
            "title": f"【演示】{category}{k}#{i + 1}",
            "season_tag": "演示",
            "notes": note.format(cat=category or "好物", high="29.9", low="9.9",
                                 aud=audience or "邻居") + "。" + DEMO_NOTE,
        })
    return out


def _demo_breakdown(text, db=None):
    head = (text or "")[:24]
    return {
        "hook": f"【演示】钩子提炼：{head}…" if head else "【演示】钩子：前3秒抛痛点/悬念" + DEMO_NOTE,
        "pain": "【演示】痛点：说出目标人群最扎心的日常麻烦。" + DEMO_NOTE,
        "demo": "【演示】演示：上手实拍，3个镜头展示效果对比。" + DEMO_NOTE,
        "price_anchor": "【演示】价格锚点：原价XX vs 现价XX，限时。" + DEMO_NOTE,
        "cta": "【演示】催单：今天下单送赠品，库存不多。" + DEMO_NOTE,
    }


def _swap(text, old_p, new_p, old_price, new_price):
    t = text or ""
    if old_p:
        t = t.replace(old_p, new_p)
    if old_price and new_price and old_price != new_price:
        t = t.replace(old_price, new_price)
    return t


def _demo_clone(viral, new, db=None):
    """演示版一键复刻：规则式元素替换（保留结构，只换商品元素）"""
    old_p = viral.get("product_name") or "原商品"
    new_p = new.get("name") or "新商品"
    new_c = new.get("category") or ""
    price = new.get("price") or "9.9"
    high = new.get("high_price") or "29.9"
    points = new.get("selling_points") or "好用不贵"

    hook = _swap(viral.get("hook") or f"你家还在用{old_p}吗？看看这个！", old_p, new_p, "", "")
    pain = _swap(viral.get("pain") or f"{old_p}不好用，问题一大堆。", old_p, new_p, "", "")
    demo = _swap(viral.get("demo") or f"看我上手演示{old_p}，效果立竿见影。", old_p, new_p, "", "")
    price_a = f"超市同款卖{high}，我这条{new_p}只要{price}，{points}。"
    cta = f"今天下单立减，{new_p}仅剩最后几十件，点下方小黄车。"

    script_text = (
        f"【0-3秒钩子】{hook}\n【3-15秒演示】{pain}{demo}\n"
        f"【15-25秒价格对比】{price_a}\n【25-30秒催单】{cta}\n{DEMO_NOTE}"
    )
    shots = [
        {"time": "0-3秒", "shot": f"{new_p}特写+痛点字幕", "caption": hook},
        {"time": "3-8秒", "shot": f"手持{new_p}展示细节", "caption": pain},
        {"time": "8-15秒", "shot": f"{new_p}使用效果对比", "caption": demo},
        {"time": "15-25秒", "shot": "价格对比字幕卡", "caption": price_a},
        {"time": "25-30秒", "shot": "小黄车指引+催单口播", "caption": cta},
    ]
    return {
        "script_text": script_text,
        "shots": shots,
        "image_prompts": f"【演示】{new_c}{new_p}产品特写，暖光，电商质感。" + DEMO_NOTE,
        "video_prompts": f"【演示】手持{new_p}缓慢旋转展示，3秒。" + DEMO_NOTE,
    }


def _demo_diagnose(metrics, db=None):
    return (
        f"【诊断结论】{DEMO_NOTE}\n"
        f"播放{metrics.get('play_count', 0)}，完播率{metrics.get('finish_rate', 0)}%。"
        "完播率低于15%先改前3秒钩子；有点击无转化改价格话术。\n"
        "【核心问题】演示数据，仅供看流程。\n【优化动作】配置 Key 后由 AI 按真实数据诊断。"
    )


async def ai_clone(viral: dict, new: dict, db=None):
    """一键复刻：保留原爆款五段结构与话术节奏，只替换商品元素。

    viral: {product_name, category, hook, pain, demo, price_anchor, cta}
    new: {name, category, price, high_price, selling_points}
    返回 {script_text, shots, image_prompts, video_prompts}
    """
    prompt = (
        "你是爆款带货视频复刻专家。任务：完整保留原爆款视频的五段结构、节奏、"
        "话术套路和钩子风格，只把其中与商品相关的元素替换成新商品。\n"
        "【原爆款】\n原商品：%(old_p)s（原品类：%(old_c)s）\n"
        "钩子：%(hook)s\n痛点：%(pain)s\n演示：%(demo)s\n"
        "价格对比：%(price_a)s\n催单：%(cta)s\n"
        "【新商品】\n商品名：%(new_p)s（新品类：%(new_c)s）\n"
        "现价：%(price)s元，对比价：%(high)s元\n卖点：%(points)s\n"
        "【硬性要求】\n"
        "1. 五段结构一比一对应，钩子的话术套路原样保留，只替换其中的商品词；\n"
        "2. 所有价格、品名、卖点、演示动作、画面中的商品都换成新商品；\n"
        "3. 口播用普通人说话语气，禁用说教和AI味总结句；\n"
        "4. 返回纯 JSON：script_text（按【0-3秒钩子】【3-15秒演示】"
        "【15-25秒价格对比】【25-30秒催单】分段）、shots（4-6镜，每镜 "
        "{time, shot, caption}）、image_prompts（封面+关键帧中文描述）、"
        "video_prompts（每镜运镜动作中文描述）。"
        % {"old_p": viral.get("product_name", ""), "old_c": viral.get("category", ""),
           "hook": viral.get("hook", ""), "pain": viral.get("pain", ""),
           "demo": viral.get("demo", ""), "price_a": viral.get("price_anchor", ""),
           "cta": viral.get("cta", ""), "new_p": new.get("name", ""),
           "new_c": new.get("category", ""), "price": new.get("price", ""),
           "high": new.get("high_price", ""), "points": new.get("selling_points", "")}
    )
    try:
        return _parse_json(await _chat(SYSTEM_PROMPT, prompt, db))
    except AiNotConfigured:
        if _demo_enabled(db):
            return _demo_clone(viral, new, db)
        raise


# 给无人值守的自动化任务用的同步包装（内部复用同一套演示降级）
for _fn in ("ai_persona", "ai_topics", "ai_breakdown", "ai_script", "ai_diagnose"):
    globals()[_fn] = _demo_wrap(globals()[_fn])
