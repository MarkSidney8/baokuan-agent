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
    return await _chat(SYSTEM_PROMPT, prompt, db)
