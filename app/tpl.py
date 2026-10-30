"""共享 Jinja2 模板环境：统一目录 + 中文提示文案映射"""
import os
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

_MSG_TEXT = {
    "created": "✅ 创建成功",
    "updated": "✅ 保存成功",
    "deleted": "🗑️ 删除成功",
    "saved": "✅ 保存成功",
    "ai_ok": "🤖 AI 生成成功",
    "confirmed": "✅ 已确认为终稿",
    "status_ok": "✅ 状态已更新",
    "pw_ok": "✅ 密码修改成功",
    "pw_reset": "✅ 密码已重置，对方下次登录需先改密码",
}


def msg_text(code: str) -> str:
    if code.startswith("ai_ok_"):
        return f"🤖 AI 生成成功，共 {code[6:]} 条，已存入待拍"
    if code.startswith("seed_ok_"):
        return f"📦 演示爆款已载入（{code[8:]} 条），去爆款库一键复刻试试"
    if code == "clone_ok":
        return "⚡ 一键复刻完成，制作单已生成，去制作台确认"
    if code.startswith("auto_done_"):
        return f"🤖 自动化任务执行完毕：{code[10:]}"
    if code.startswith("ai_test_ok:"):
        return "✅ AI 连接测试成功：" + code[len("ai_test_ok:"):]
    return _MSG_TEXT.get(code, code)


def err_text(code: str) -> str:
    if code == "only_admin":
        return "⛔ 仅管理员可访问该页面"
    if code == "not_found":
        return "记录不存在"
    if code.startswith("ai_test_fail:"):
        return "❌ AI 连接测试失败：" + code[len("ai_test_fail:"):]
    return code


templates.env.globals["msg_text"] = msg_text
templates.env.globals["err_text"] = err_text
