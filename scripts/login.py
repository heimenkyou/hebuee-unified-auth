"""以业务系统入口演示统一认证登录流程。

这是参考实现，不是对外 SDK。需要验证码或重复登录处理时，可以按需复制本文件
中的函数到自己项目里修改；``Client.login`` 本身仍然保持最小行为。
"""

import getpass
import html
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from time import monotonic

# 示例故意不把本仓库当作可安装依赖，直接从仓库根目录导入示例模块。
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hebuee_auth import AuthenticationError, CaptchaRequired, Client
from hebuee_auth.client import AUTH_HOST, LoginForm, encrypt_password

SERVICE_URL = "https://ehall.hebuee.edu.cn/qljfwappnew/sys/lwPsMyCurriculum/*default/index.do"
MAX_CAPTCHA_ATTEMPTS = 3
CAPTCHA_MESSAGES = ("无效的验证码", "请输入验证码")
KICKOUT_MESSAGE = "踢出会话"
_recognizer = None


def solve_captcha(image):
    """参考实现：直接用 ddddocr 识别，可替换成其他 OCR 或人工输入。"""
    global _recognizer
    if _recognizer is None:
        try:
            import ddddocr
        except ImportError as error:
            raise AuthenticationError("未安装 ddddocr，需使用 uv run --with ddddocr 运行本示例。") from error
        _recognizer = ddddocr.DdddOcr(show_ad=False)
    return _recognizer.classification(image).strip()


def login_with_captcha(client, service_url, username, password):
    """登录入口：自动处理验证码和同账号旧会话，返回跳转后的地址与页面。"""
    page_url, text = client.request(service_url)
    if urllib.parse.urlsplit(page_url).hostname != AUTH_HOST:
        raise AuthenticationError("业务入口未跳转到统一认证页面。")
    if _is_kickout(text):
        page_url, text = _continue_kickout(client, page_url, text)
        if urllib.parse.urlsplit(page_url).hostname != AUTH_HOST:
            return page_url, text

    for attempt in range(MAX_CAPTCHA_ATTEMPTS):
        form = LoginForm()
        form.feed(text)
        if not form.action or not form.salt:
            raise AuthenticationError(_message(text) or "无法读取统一认证表单或密码盐值。")
        required, salt = _captcha_status(client, page_url, username)
        if salt:
            form.salt = salt
        fields = dict(form.fields)
        fields.update(username=username, password=encrypt_password(password, form.salt))
        if required:
            fields["captchaResponse"] = _read_captcha(client, page_url, attempt)
        action = urllib.parse.urljoin(page_url, form.action)
        url, text = client.request(action, urllib.parse.urlencode(fields).encode())
        if _is_kickout(text):
            url, text = _continue_kickout(client, url, text)
            if urllib.parse.urlsplit(url).hostname != AUTH_HOST:
                return url, text
        if urllib.parse.urlsplit(url).hostname != AUTH_HOST:
            return url, text
        page_url = url
        if "casLoginForm" in text:
            message = _message(text)
            if any(keyword in message for keyword in CAPTCHA_MESSAGES):
                continue
            raise AuthenticationError(message or "认证未完成，请检查凭据或登录页面提示。")
        raise AuthenticationError(_message(text) or "认证后未跳转到业务系统。")
    raise CaptchaRequired("验证码连续识别失败，请稍后重试")


def main():
    """交互读取凭据并完成统一认证登录。"""
    username = input("学号或工号：").strip()
    password = getpass.getpass("密码（输入时不会显示）：")
    client = Client(service_hosts={"ehall.hebuee.edu.cn"})
    try:
        url, _ = login_with_captcha(client, SERVICE_URL, username, password)
    except (AuthenticationError, urllib.error.URLError, TimeoutError, OSError) as exc:
        print(f"登录未完成：{exc}")
        return 1
    print(f"统一身份认证登录成功，最终地址：{url}")
    return 0


def _captcha_status(client, page_url, username):
    """返回是否需要验证码，以及服务端可能更新的密码盐值。"""
    url = urllib.parse.urljoin(page_url, "needCaptcha.html") + "?" + urllib.parse.urlencode({
        "username": username, "pwdEncrypt2": "pwdEncryptSalt",
    })
    _, body = client.request(url)
    status, _, salt = body.strip().partition("::::")
    if status.lower() == "true":
        return True, salt.strip()
    if status.lower() == "false":
        return False, salt.strip()
    raise AuthenticationError("无法识别验证码状态。")


def _read_captcha(client, page_url, attempt):
    """读取验证码图片并识别；示例里直接使用页面同源的 Cookie 会话。"""
    url = urllib.parse.urljoin(page_url, f"captcha.html?ts={int(monotonic() * 1000) + attempt}")
    request = urllib.request.Request(url, headers={"Referer": page_url, "User-Agent": "Mozilla/5.0"})
    with client.opener.open(request, timeout=20) as response:
        answer = solve_captcha(response.read())
    if not answer:
        raise CaptchaRequired("验证码识别结果为空")
    return answer


def _continue_kickout(client, page_url, page):
    """注销同账号的其他会话并继续本次登录。"""
    form = re.search(r'<form[^>]*id="continue"[^>]*>(.*?)</form>', page, re.S)
    execution = re.search(r'name="execution"[^>]*value="([^"]+)"', form.group(1)) if form else None
    if not execution:
        raise AuthenticationError("检测到账号已在其他位置登录，但无法读取注销表单。")
    print("检测到同账号旧会话，正在注销后继续登录。")
    body = urllib.parse.urlencode({"execution": execution.group(1), "_eventId": "continue"}).encode()
    return client.request(page_url, body)


def _is_kickout(page):
    return KICKOUT_MESSAGE in page


def _message(page):
    """提取认证页顶部的错误提示。"""
    match = re.search(r'<span id="msg"[^>]*>(.*?)</span>', page, re.S)
    return html.unescape(re.sub(r"<[^>]+>|\s+", " ", match.group(1))).strip() if match else ""


if __name__ == "__main__":
    raise SystemExit(main())
