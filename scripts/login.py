"""以服务大厅为入口交互式验证统一认证。"""

import getpass
import json
import urllib.error

from hebuee_auth import AuthenticationError, Client

SERVICE_URL = "https://ehall.hebuee.edu.cn/qljfwappnew/sys/lwPsMyCurriculum/*default/index.do"
USER_INFO_URL = "https://ehall.hebuee.edu.cn/jsonp/userInfo.json"


def verify_session(client):
    """通过服务大厅用户信息确认当前会话并返回姓名。"""
    _, text = client.request(USER_INFO_URL)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AuthenticationError("无法解析服务大厅的会话验证响应。") from exc
    if not isinstance(data, dict) or data.get("hasLogin") is not True:
        raise AuthenticationError("服务大厅未确认当前会话已登录。")
    name = data.get("userName")
    return name.strip() if isinstance(name, str) and name.strip() else None


def main():
    """交互读取凭据并验证服务大厅的认证跳转。"""
    username = input("学号或工号：").strip()
    password = getpass.getpass("密码（输入时不会显示）：")
    client = Client(service_hosts={"ehall.hebuee.edu.cn"})
    try:
        client.login(SERVICE_URL, username, password)
        name = verify_session(client)
    except (AuthenticationError, urllib.error.URLError, TimeoutError, OSError) as exc:
        print(f"登录未完成：{exc}")
        return 1
    print(f"统一身份认证登录成功，已通过服务大厅验证{'：' + name if name else '。'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
