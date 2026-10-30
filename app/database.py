"""数据库连接层：SQLite + SQLAlchemy 2.0"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

# 数据库文件放在项目根目录，方便备份与迁移
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "baokuan.db")

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},  # SQLite 多线程需要
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    """所有模型的基类"""
    pass


def get_db():
    """FastAPI 依赖：每个请求一个会话，请求结束自动关闭"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
