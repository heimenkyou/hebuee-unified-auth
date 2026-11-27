"""统一身份认证的表单提交和会话管理。"""

import base64
import html.parser
import http.cookiejar
import secrets
import string
import urllib.parse
import urllib.request

from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

AUTH_HOST = "authserver.hebuee.edu.cn"


class AuthenticationError(Exception):
    """认证流程或响应不符合预期。"""


class CaptchaRequired(AuthenticationError):
    """认证服务器要求输入验证码。"""


class LoginForm(html.parser.HTMLParser):
    """提取认证页面的动态表单字段。"""

    def __init__(self):
        super().__init__()
        self.active = False
        self.action = ""
        self.fields = {}
        self.salt = ""

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "form" and attrs.get("id") == "casLoginForm":
            self.active = True
            self.action = attrs.get("action", "")
        elif tag == "input" and self.active:
            if attrs.get("type") == "hidden" and attrs.get("name"):
                self.fields[attrs["name"]] = attrs.get("value", "")
            if attrs.get("id") == "pwdDefaultEncryptSalt":
                self.salt = attrs.get("value", "")

    def handle_endtag(self, tag):
        if tag == "form":
            self.active = False


def encrypt_password(password, salt):
    """使用登录页面的 AES-CBC 算法生成密码字段。"""
    alphabet = string.ascii_letters + string.digits
    prefix = "".join(secrets.choice(alphabet) for _ in range(64))
    iv = "".join(secrets.choice(alphabet) for _ in range(16)).encode()
    padder = padding.PKCS7(128).padder()
    padded = padder.update((prefix + password).encode()) + padder.finalize()
    encryptor = Cipher(algorithms.AES(salt.strip().encode()), modes.CBC(iv)).encryptor()
    return base64.b64encode(encryptor.update(padded) + encryptor.finalize()).decode()


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    """仅允许会话跳转到明确指定的 HTTPS 主机。"""

    def __init__(self, allowed_hosts):
        super().__init__()
        self.allowed_hosts = allowed_hosts

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        url = urllib.parse.urljoin(req.full_url, newurl)
        validate_url(url, self.allowed_hosts)
        return super().redirect_request(req, fp, code, msg, headers, url)


def validate_url(url, allowed_hosts):
    """限制携带会话的请求目标。"""
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in allowed_hosts or parsed.username or parsed.password:
        raise AuthenticationError("请求地址不在允许的 HTTPS 主机范围内。")


class Client:
    """为单个用户维护统一认证及业务系统的 Cookie 会话。"""

    def __init__(self, service_hosts):
        self.allowed_hosts = frozenset({AUTH_HOST, *service_hosts})
        self.cookies = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cookies),
            SafeRedirect(self.allowed_hosts),
        )
        self.opener.addheaders = [("User-Agent", "Mozilla/5.0")]

    def request(self, url, data=None):
        """使用当前会话发送请求，返回最终地址和响应文本。"""
        validate_url(url, self.allowed_hosts)
        with self.opener.open(url, data=data, timeout=20) as response:
            return response.url, response.read().decode("utf-8", "replace")

    def login(self, service_url, username, password):
        """从业务入口发起认证，返回跳转后的地址和页面。"""
        page_url, text = self.request(service_url)
        if urllib.parse.urlsplit(page_url).hostname != AUTH_HOST:
            raise AuthenticationError("业务入口未跳转到统一认证页面。")
        form = LoginForm()
        form.feed(text)
        if not form.action or not form.salt:
            raise AuthenticationError("无法读取统一认证表单或密码盐值。")

        captcha_url = urllib.parse.urljoin(page_url, "needCaptcha.html") + "?" + urllib.parse.urlencode({
            "username": username, "pwdEncrypt2": "pwdEncryptSalt",
        })
        _, captcha = self.request(captcha_url)
        status = captcha.strip().split("::::", 1)[0].lower()
        if status == "true":
            raise CaptchaRequired("统一认证要求验证码。")
        if status != "false":
            raise AuthenticationError("无法识别验证码状态。")

        action = urllib.parse.urljoin(page_url, form.action)
        validate_url(action, {AUTH_HOST})
        fields = dict(form.fields)
        fields.update(username=username, password=encrypt_password(password, form.salt))
        url, text = self.request(action, urllib.parse.urlencode(fields).encode())
        if "casLoginForm" in text:
            raise AuthenticationError("认证未完成，请检查凭据或登录页面提示。")
        if urllib.parse.urlsplit(url).hostname == AUTH_HOST:
            raise AuthenticationError("认证后未跳转到业务系统。")
        return url, text
