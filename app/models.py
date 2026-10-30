"""数据模型定义"""
from datetime import datetime
from sqlalchemy import String, Integer, Float, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base


def _now():
    return datetime.now()


class User(Base):
    """系统用户：admin 管理员 / member 普通成员"""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(16), default="member")  # admin / member
    must_change_pw: Mapped[int] = mapped_column(Integer, default=0)  # 1=首次登录强制改密码
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Persona(Base):
    """人设：账号定位"""
    __tablename__ = "personas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    category: Mapped[str] = mapped_column(String(64), default="")      # 类目：厨房日用等
    audience: Mapped[str] = mapped_column(String(128), default="")     # 目标人群
    tone: Mapped[str] = mapped_column(String(64), default="")          # 语气风格
    persona_desc: Mapped[str] = mapped_column(Text, default="")        # 人设描述
    selling_style: Mapped[str] = mapped_column(Text, default="")       # 带货风格
    created_by: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Topic(Base):
    """选题"""
    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(64), default="")
    persona_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("personas.id"), nullable=True
    )
    season_tag: Mapped[str] = mapped_column(String(64), default="")    # 季节/热点标签
    status: Mapped[str] = mapped_column(String(16), default="待拍")     # 待拍/制作中/已发布
    notes: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    persona: Mapped["Persona | None"] = relationship("Persona")


class Template(Base):
    """拆解模板：爆款视频的结构化拆解"""
    __tablename__ = "templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    source_desc: Mapped[str] = mapped_column(Text, default="")   # 爆款来源描述
    hook: Mapped[str] = mapped_column(Text, default="")          # 钩子 0-3秒
    pain: Mapped[str] = mapped_column(Text, default="")          # 痛点
    demo: Mapped[str] = mapped_column(Text, default="")          # 演示 3-15秒
    price_anchor: Mapped[str] = mapped_column(Text, default="")  # 价格锚点 15-25秒
    cta: Mapped[str] = mapped_column(Text, default="")           # 催单 25-30秒
    full_structure: Mapped[str] = mapped_column(Text, default="{}")  # 完整结构 JSON 文本
    created_by: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Script(Base):
    """制作单：选题+模板+商品 -> 口播脚本/分镜/提示词"""
    __tablename__ = "scripts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    topic_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("topics.id"), nullable=True
    )
    template_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("templates.id"), nullable=True
    )
    product_name: Mapped[str] = mapped_column(String(128), default="")
    product_price: Mapped[str] = mapped_column(String(32), default="")
    product_high_price: Mapped[str] = mapped_column(String(32), default="")  # 原价/对比价
    commission: Mapped[str] = mapped_column(String(32), default="")
    script_text: Mapped[str] = mapped_column(Text, default="")    # 口播脚本
    shots: Mapped[str] = mapped_column(Text, default="[]")        # 分镜 JSON 文本
    image_prompts: Mapped[str] = mapped_column(Text, default="")  # 生图提示词
    video_prompts: Mapped[str] = mapped_column(Text, default="")  # 视频提示词
    status: Mapped[str] = mapped_column(String(16), default="草稿")  # 草稿/已确认
    created_by: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    topic: Mapped["Topic | None"] = relationship("Topic")
    template: Mapped["Template | None"] = relationship("Template")


class VideoStat(Base):
    """数据复盘：单条视频的数据录入与 AI 诊断"""
    __tablename__ = "video_stats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    script_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("scripts.id"), nullable=True
    )
    play_count: Mapped[int] = mapped_column(Integer, default=0)
    finish_rate: Mapped[float] = mapped_column(Float, default=0.0)   # 完播率 %
    click_rate: Mapped[float] = mapped_column(Float, default=0.0)    # 商品点击率 %
    orders: Mapped[int] = mapped_column(Integer, default=0)          # 成交单数
    gpm: Mapped[float] = mapped_column(Float, default=0.0)           # 千次播放成交额
    ai_advice: Mapped[str] = mapped_column(Text, default="")         # AI 诊断建议
    stat_date: Mapped[str] = mapped_column(String(32), default="")
    created_by: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    script: Mapped["Script | None"] = relationship("Script")


class OperationLog(Base):
    """操作日志：关键写操作记录"""
    __tablename__ = "operation_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    who: Mapped[str] = mapped_column(String(64), default="")
    action: Mapped[str] = mapped_column(String(64), default="")  # 如：新建人设
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Setting(Base):
    """系统设置：键值对（如 AI 服务商 / API Key / 模型名），后台可改"""
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    value: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_now, onupdate=_now)


class ViralVideo(Base):
    """爆款库：热门带货视频（手动入库 / 第三方数据API拉取预留）"""
    __tablename__ = "viral_videos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), default="")        # 视频标题
    author: Mapped[str] = mapped_column(String(128), default="")       # 发布账号
    source_url: Mapped[str] = mapped_column(String(512), default="")   # 原视频链接
    category: Mapped[str] = mapped_column(String(64), default="")      # 原品类：如 服装
    product_name: Mapped[str] = mapped_column(String(128), default="") # 原商品名
    play_count: Mapped[str] = mapped_column(String(32), default="")    # 播放量（文本，如 120万）
    like_count: Mapped[str] = mapped_column(String(32), default="")    # 点赞数
    transcript: Mapped[str] = mapped_column(Text, default="")          # 口播文案/描述
    status: Mapped[str] = mapped_column(String(16), default="待拆解")   # 待拆解/已拆解/已复刻
    source: Mapped[str] = mapped_column(String(32), default="手动")     # 手动/蝉妈妈/飞瓜
    created_by: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class CloneJob(Base):
    """一键复刻任务：爆款结构保留 + 商品元素替换"""
    __tablename__ = "clone_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    viral_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("viral_videos.id"), nullable=True)
    old_product: Mapped[str] = mapped_column(String(128), default="")  # 原商品
    new_product: Mapped[str] = mapped_column(String(128), default="")  # 新商品
    new_category: Mapped[str] = mapped_column(String(64), default="")  # 新类目
    new_price: Mapped[str] = mapped_column(String(32), default="")     # 新价格
    new_high_price: Mapped[str] = mapped_column(String(32), default="")  # 新对比价
    selling_points: Mapped[str] = mapped_column(Text, default="")      # 新卖点
    script_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("scripts.id"), nullable=True)               # 生成的制作单
    status: Mapped[str] = mapped_column(String(16), default="已完成")
    created_by: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    viral: Mapped["ViralVideo | None"] = relationship("ViralVideo")
    script: Mapped["Script | None"] = relationship("Script")
