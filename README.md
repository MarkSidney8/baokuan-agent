# 爆款带货智能体工作台

面向中国下沉市场的短视频带货团队协作工具：人设管理、选题中心、爆款拆解、
**爆款库一键复刻**、制作台（口播脚本/分镜/生图与视频提示词）、数据复盘、
**自动化任务**，全部接入可配置的 AI 模型一键生成（DeepSeek / OpenAI / 通义千问 / Kimi / 智谱 / 豆包等）。

## 核心链路（半自动流水线）

1. **爆款库**（`/viral`）：把全网热门带货视频入库（标题/账号/播放/口播文案），
也可点「载入演示爆款」直接体验。第三方数据 API（蝉妈妈/飞瓜）对接位已预留。
2. **一键复刻**（爆款库 → ⚡一键复刻）：完整保留原爆款的五段结构与话术节奏，
只替换商品元素——比如把卖衣服的爆款改成卖裤子：填新商品名/类目/价格/卖点，
一键生成新口播脚本 + 分镜 + 生图/视频提示词，自动存为制作单。
3. **自动化任务**（`/automation`）：每天 08:00 自动为每个类目生成选题、
08:30 自动拆解待拆解爆款入库模板库；也可手动「立即执行」。
4. **演示模式**：未配置 AI Key 时，所有 AI 功能返回带标记的
模板化输出，可完整跑通全流程；配置真实 Key 后自动切换为 AI 真实生成。
开关在「系统设置」页。

## 本地运行

```bash
python3 -m venv.venv &&.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
# 或激活虚拟环境后：pip install -r requirements.txt && uvicorn app.main:app --host 0.0.0.0 --port 8000
```

浏览器打开 http://localhost:8000 ，用种子管理员登录：

- 用户名：`admin`
- 密码：`admin123`

首次登录会强制要求修改密码。团队管理页（仅 admin 可见）可新增成员、重置密码。

## AI 配置（可选）

支持多服务商可配：DeepSeek / OpenAI / 通义千问 / Kimi / 智谱 GLM /
豆包 / 自定义（任意 OpenAI 兼容接口），全部走 `/chat/completions`。

推荐在后台「系统设置」页配置：选服务商 → 填 API Key → Base URL
和模型名自动填好（也可手动改任意模型）→ 点「测试连接」验证，保存即生效。

也可用服务器环境变量配置（优先级低于后台设置）：

```bash
export AI_PROVIDER=deepseek        # deepseek/openai/qwen/moonshot/zhipu/doubao/custom
export AI_API_KEY=sk-xxxx
export AI_BASE_URL=https://api.deepseek.com   # 可选，默认取服务商预设
export AI_MODEL=deepseek-chat                 # 可选，默认取服务商预设
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

旧版 `DEEPSEEK_API_KEY` / `DEEPSEEK_BASE_URL` / `DEEPSEEK_MODEL`
环境变量和数据库旧键仍兼容，会自动迁移读取。

未配置时演示模式兜底（输出带标记），不会 500 报错。

## 前端样式

样式为 Tailwind 编译后的本地文件 `app/static/css/app.css`（不依赖 CDN，
国内服务器也能正常加载）。改动模板里的 Tailwind 类名后，重新编译一次：

```bash
# 下载 tailwindcss standalone（只需一次）
curl -sL -o /tmp/tailwindcss \
https://github.com/tailwindlabs/tailwindcss/releases/download/v3.4.16/tailwindcss-linux-x64
chmod +x /tmp/tailwindcss
# 编译
/tmp/tailwindcss -i app/static/css/input.css -o app/static/css/app.css \
--content "./app/templates/**/*.html" --minify
```

## 目录结构

```
app/
main.py # 应用组装、建表、种子管理员、异常处理、自动化定时任务
database.py # SQLAlchemy 引擎/会话/Base
models.py # 数据模型（User/Persona/Topic/Template/Script/VideoStat/OperationLog/ViralVideo/CloneJob）
auth.py # bcrypt 密码、itsdangerous 会话 cookie、登录依赖
ai.py # 多服务商 AI 调用封装（httpx，OpenAI 兼容）+ 连接测试 + 演示模式降级 + 一键复刻
automation.py # 每日自动选题 / 爆款自动拆解
routers/ # auth/dashboard/personas/topics/breakdown/viral/scripts/stats/team/settings/automation
templates/ # Jinja2 模板（layout.html 侧边导航 + 设计系统）
static/css/ # input.css（源码）/ app.css（编译后，提交到仓库）
```
