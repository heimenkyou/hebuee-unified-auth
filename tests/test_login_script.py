"""交互式登录示例的离线测试。"""

import importlib.util
import pathlib
import unittest
from unittest.mock import patch

from hebuee_auth import AuthenticationError

path = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "login.py"
spec = importlib.util.spec_from_file_location("login_script", path)
login = importlib.util.module_from_spec(spec)
spec.loader.exec_module(login)


class LoginScriptTests(unittest.TestCase):
    """验证服务大厅会话判断和终端提示。"""

    def test_verified_session_returns_name(self):
        client = unittest.mock.Mock()
        client.request.return_value = (login.USER_INFO_URL, '{"hasLogin":true,"userName":"测试用户"}')
        self.assertEqual(login.verify_session(client), "测试用户")
        client.request.assert_called_once_with(login.USER_INFO_URL)

    def test_unverified_responses_fail(self):
        for text in ('{"hasLogin":false}', '{"hasLogin":"true"}', '[]', '<html>'):
            with self.subTest(text=text):
                client = unittest.mock.Mock()
                client.request.return_value = (login.USER_INFO_URL, text)
                with self.assertRaises(AuthenticationError):
                    login.verify_session(client)

    def test_success_without_name(self):
        client = unittest.mock.Mock()
        client.request.return_value = (login.USER_INFO_URL, '{"hasLogin":true}')
        self.assertIsNone(login.verify_session(client))

    def test_main_displays_verified_name(self):
        with patch("builtins.input", return_value="student"), \
             patch.object(login.getpass, "getpass", return_value="secret") as password, \
             patch.object(login, "Client") as client, \
             patch("builtins.print") as output:
            client.return_value.request.return_value = (login.USER_INFO_URL, '{"hasLogin":true,"userName":"测试用户"}')
            self.assertEqual(login.main(), 0)
        password.assert_called_once_with("密码（输入时不会显示）：")
        output.assert_called_once_with("统一身份认证登录成功，已通过服务大厅验证：测试用户")

    def test_main_rejects_unverified_session(self):
        with patch("builtins.input", return_value="student"), \
             patch.object(login.getpass, "getpass", return_value="secret"), \
             patch.object(login, "Client") as client, \
             patch("builtins.print") as output:
            client.return_value.request.return_value = (login.USER_INFO_URL, '{"hasLogin":false}')
            self.assertEqual(login.main(), 1)
        output.assert_called_once_with("登录未完成：服务大厅未确认当前会话已登录。")


if __name__ == "__main__":
    unittest.main()
