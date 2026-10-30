# 爆款带货智能体工作台

面向中国下沉市场的短视频带货团队协作工具：人设管理、选题中心、爆款拆解、
制作台（口播脚本/分镜/生图与视频提示词）、数据复盘，全部接入 DeepSeek AI 一键生成。

## 本地运行

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
# 或激活虚拟环境后：pip install -r requirements.txt && uvicorn app.main:app --host 0.0.0.0 --port 8000
```

浏览器打开 http://localhost:8000 ，用种子管理员登录：

- 用户名：`admin`
- 密码：`admin123`

首次登录会强制要求修改密码。团队管理页（仅 admin 可见）可新增成员、重置密码。

## AI 配置（可选）

```bash
export DEEPSEEK_API_KEY=sk-xxxx
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

未配置时所有 AI 按钮会给出友好中文提示，不会 500 报错。

## 目录结构

```
app/
  main.py        # 应用组装、建表、种子管理员、异常处理
  database.py    # SQLAlchemy 引擎/会话/Base
  models.py      # 数据模型（User/Persona/Topic/Template/Script/VideoStat/OperationLog）
  schemas.py     # Pydantic 校验模型
  auth.py        # bcrypt 密码、itsdangerous 会话 cookie、登录依赖
  ai.py          # DeepSeek 调用封装（httpx）
  routers/       # auth/dashboard/personas/topics/breakdown/scripts/stats/team
  templates/     # Jinja2 模板（layout.html 侧边导航）
  static/        # 静态资源
```
