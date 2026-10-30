"""Pydantic 校验模型（表单/AI 输出校验）"""
from pydantic import BaseModel, Field


class PersonaIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    category: str = ""
    audience: str = ""
    tone: str = ""
    persona_desc: str = ""
    selling_style: str = ""


class TopicIn(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    category: str = ""
    persona_id: int | None = None
    season_tag: str = ""
    status: str = "待拍"
    notes: str = ""


class TemplateIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    source_desc: str = ""
    hook: str = ""
    pain: str = ""
    demo: str = ""
    price_anchor: str = ""
    cta: str = ""


class ScriptIn(BaseModel):
    topic_id: int | None = None
    template_id: int | None = None
    product_name: str = ""
    product_price: str = ""
    product_high_price: str = ""
    commission: str = ""


class VideoStatIn(BaseModel):
    script_id: int | None = None
    play_count: int = 0
    finish_rate: float = 0.0
    click_rate: float = 0.0
    orders: int = 0
    gpm: float = 0.0
    stat_date: str = ""
