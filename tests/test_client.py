"""统一认证流程的离线测试。"""

import base64
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs

from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from hebuee_auth import AuthenticationError, CaptchaRequired, Client, encrypt_password
from hebuee_auth.client import LoginForm, validate_url


FORM = """<form id="casLoginForm" action="/authserver/login?service=example">
<input type="hidden" name="execution" value="e1s1">
<input type="hidden" id="pwdDefaultEncryptSalt" value="0123456789abcdef">
</form>"""
ENTRY = "https://ehall.hebuee.edu.cn/app"
LOGIN = "https://authserver.hebuee.edu.cn/authserver/login?service=example"


class ClientTests(unittest.TestCase):
    """验证密码格式、表单处理及认证过程。"""

    def test_encrypt_password(self):
        with patch("hebuee_auth.client.secrets.choice", return_value="a"):
            encrypted = base64.b64decode(encrypt_password("密码", "0123456789abcdef"))
        decryptor = Cipher(algorithms.AES(b"0123456789abcdef"), modes.CBC(b"a" * 16)).decryptor()
        padded = decryptor.update(encrypted) + decryptor.finalize()
        unpadder = padding.PKCS7(128).unpadder()
        self.assertEqual((unpadder.update(padded) + unpadder.finalize()).decode(), "a" * 64 + "密码")

    def test_parse_form(self):
        form = LoginForm()
        form.feed(FORM)
        self.assertEqual(form.fields["execution"], "e1s1")
        self.assertEqual(form.salt, "0123456789abcdef")

    def test_login_submits_dynamic_fields(self):
        client = Client({"ehall.hebuee.edu.cn"})
        with patch.object(client, "request", side_effect=[(LOGIN, FORM), (LOGIN, "false"), (ENTRY, "ok")]) as request:
            self.assertEqual(client.login(ENTRY, "student", "secret"), (ENTRY, "ok"))
        fields = parse_qs(request.call_args.args[1].decode())
        self.assertEqual(fields["execution"], ["e1s1"])
        self.assertEqual(fields["username"], ["student"])
        self.assertNotEqual(fields["password"], ["secret"])

    def test_captcha_stops_submission(self):
        client = Client({"ehall.hebuee.edu.cn"})
        with patch.object(client, "request", side_effect=[(LOGIN, FORM), (LOGIN, "true::::new-salt")]) as request:
            with self.assertRaises(CaptchaRequired):
                client.login(ENTRY, "student", "secret")
        self.assertEqual(request.call_count, 2)

    def test_unknown_captcha_response_stops(self):
        client = Client({"ehall.hebuee.edu.cn"})
        with patch.object(client, "request", side_effect=[(LOGIN, FORM), (LOGIN, "error")]):
            with self.assertRaises(AuthenticationError):
                client.login(ENTRY, "student", "secret")

    def test_rejects_untrusted_urls(self):
        for url in ("http://ehall.hebuee.edu.cn/", "https://evil.example/", "https://user@ehall.hebuee.edu.cn/"):
            with self.subTest(url=url), self.assertRaises(AuthenticationError):
                validate_url(url, {"ehall.hebuee.edu.cn"})

    def test_rejects_untrusted_form_action(self):
        client = Client({"ehall.hebuee.edu.cn"})
        form = FORM.replace("/authserver/login?service=example", "https://evil.example/login")
        with patch.object(client, "request", side_effect=[(LOGIN, form), (LOGIN, "false")]):
            with self.assertRaises(AuthenticationError):
                client.login(ENTRY, "student", "secret")

    def test_login_form_after_post_is_failure(self):
        client = Client({"ehall.hebuee.edu.cn"})
        with patch.object(client, "request", side_effect=[(LOGIN, FORM), (LOGIN, "false"), (LOGIN, FORM)]):
            with self.assertRaises(AuthenticationError):
                client.login(ENTRY, "student", "bad")


if __name__ == "__main__":
    unittest.main()
