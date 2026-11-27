"""交互式登录示例的离线测试。"""

import importlib.util
import pathlib
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs

path = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "login.py"
spec = importlib.util.spec_from_file_location("login_script", path)
login = importlib.util.module_from_spec(spec)
spec.loader.exec_module(login)

AUTH_URL = "https://authserver.hebuee.edu.cn/authserver/login?service=example"
ENTRY = "https://ehall.hebuee.edu.cn/app"
FORM = """<form id="casLoginForm" action="/authserver/login?service=example">
<input type="hidden" name="execution" value="e1s1">
<input type="hidden" id="pwdDefaultEncryptSalt" value="0123456789abcdef">
</form>"""
KICKOUT = """
<h3>踢出会话</h3>
<form method="post" id="continue">
<input type="hidden" name="execution" value="e1s2">
<input type="hidden" name="_eventId" value="continue">
</form>
"""


class LoginScriptTests(unittest.TestCase):
    """验证验证码重试、旧会话处理和终端提示。"""

    def test_solves_captcha_and_retries(self):
        client = login.Client({"ehall.hebuee.edu.cn"})
        invalid = FORM + '<span id="msg" class="auth_error">无效的验证码</span>'
        with patch.object(
            client,
            "request",
            side_effect=[(AUTH_URL, FORM), (AUTH_URL, "true"), (AUTH_URL, invalid), (AUTH_URL, "true"), (ENTRY, "ok")],
        ) as request, patch.object(login, "_read_captcha", side_effect=["abcd", "efgh"]) as captcha:
            self.assertEqual(login.login_with_captcha(client, ENTRY, "student", "secret"), (ENTRY, "ok"))
        self.assertEqual(captcha.call_count, 2)
        first = parse_qs(request.call_args_list[2].args[1].decode())
        second = parse_qs(request.call_args_list[4].args[1].decode())
        self.assertEqual(first["captchaResponse"], ["abcd"])
        self.assertEqual(second["captchaResponse"], ["efgh"])

    def test_kickout_is_continued(self):
        client = login.Client({"ehall.hebuee.edu.cn"})
        with patch.object(
            client,
            "request",
            side_effect=[(AUTH_URL, FORM), (AUTH_URL, "false"), (AUTH_URL, KICKOUT), (ENTRY, "ok")],
        ) as request, patch("builtins.print"):
            self.assertEqual(login.login_with_captcha(client, ENTRY, "student", "secret"), (ENTRY, "ok"))
        fields = parse_qs(request.call_args_list[3].args[1].decode())
        self.assertEqual(fields["_eventId"], ["continue"])

    def test_main_reports_final_url(self):
        with patch("builtins.input", return_value="student"), \
             patch.object(login.getpass, "getpass", return_value="secret") as password, \
             patch.object(login, "login_with_captcha", return_value=(ENTRY, "ok")) as authenticate, \
             patch.object(login, "Client"), \
             patch("builtins.print") as output:
            self.assertEqual(login.main(), 0)
        password.assert_called_once_with("密码（输入时不会显示）：")
        authenticate.assert_called_once()
        output.assert_called_once_with(f"统一身份认证登录成功，最终地址：{ENTRY}")

    def test_main_reports_login_failure(self):
        with patch("builtins.input", return_value="student"), \
             patch.object(login.getpass, "getpass", return_value="secret"), \
             patch.object(login, "login_with_captcha", side_effect=login.AuthenticationError("凭据错误")), \
             patch.object(login, "Client"), \
             patch("builtins.print") as output:
            self.assertEqual(login.main(), 1)
        output.assert_called_once_with("登录未完成：凭据错误")


if __name__ == "__main__":
    unittest.main()
