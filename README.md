# 河北环境工程学院统一身份认证

本项目梳理了河北环境工程学院统一身份认证的认证流程与协议细节，并提供 Python 客户端实现。开发者可通过脚本自动提交登录表单、维护 Cookie 会话，并直接访问接入统一认证的各类校内业务系统，无需手动操作浏览器。

## 运行登录示例

运行登录示例需要 Python 3.11 或更高版本、[uv](https://github.com/astral-sh/uv) 以及能够访问学校认证服务器的网络环境。克隆仓库后，在项目根目录运行：

```powershell
uv sync
uv run python scripts/login.py
```

运行后按提示输入学号或工号及密码（输入密码时不回显）。脚本将通过服务大厅课表入口发起统一认证，随后请求用户信息接口以验证会话有效性。验证通过后，终端会提示登录成功；若接口返回了用户姓名，也会一并输出。

若服务端触发了验证码机制，脚本会给出提示并退出。本项目暂不支持验证码的自动识别与提交。

## 在 Python 项目中使用

可通过本地目录直接安装客户端。请将下方命令中的路径替换为本项目的实际本地路径：

```bash
python -m pip install /path/to/hebuee-unified-auth
```

以下示例演示了如何通过服务大厅入口发起登录，并复用同一个客户端实例请求用户信息接口：

```python
import getpass
import json
import urllib.error

from hebuee_auth import AuthenticationError, CaptchaRequired, Client

service_url = "https://ehall.hebuee.edu.cn/qljfwappnew/sys/lwPsMyCurriculum/*default/index.do"
user_info_url = "https://ehall.hebuee.edu.cn/jsonp/userInfo.json"

username = input("学号或工号：").strip()
password = getpass.getpass("密码（输入时不会显示）：")
client = Client(service_hosts={"ehall.hebuee.edu.cn"})

try:
    client.login(service_url, username, password)
    _, response = client.request(user_info_url)
    user_info = json.loads(response)
except CaptchaRequired:
    print("服务端要求输入验证码，请稍后重试。")
except (AuthenticationError, urllib.error.URLError, TimeoutError, OSError, ValueError):
    print("登录或会话验证未完成。")
else:
    if isinstance(user_info, dict) and user_info.get("hasLogin") is True:
        print("服务大厅会话验证成功。")
    else:
        print("服务大厅未确认当前会话已登录。")
```

`Client.login()` 返回认证跳转后的最终 URL 与页面内容；`Client.request()` 返回请求完成后的 URL 与响应文本。两者共用当前客户端实例内的 Cookie 容器。若需处理多个用户，请为每个用户分别创建独立的 `Client` 实例。

创建客户端时，`service_hosts` 应包含认证链路中涉及的业务系统域名。客户端已默认内置统一认证服务器域名，并将初始请求与重定向严格限制在指定的 HTTPS 域名范围内。不同业务系统可能需要额外的会话初始化步骤；接入其他系统前，请先确认该系统的入口地址、重定向跳转逻辑以及会话验证方式。

## 协议文档

如需使用其他编程语言实现该认证流程，可参考以下协议与接入文档：

- [统一身份认证协议](docs/统一身份认证协议.md)：请求流程、表单字段规范、密码加密算法、验证码处理及 Cookie 会话机制。
- [业务系统接入](docs/业务系统接入.md)：服务大厅登录与会话验证，以及 WebVPN 等系统的接入线索。

## 运行测试

执行离线测试：

```bash
uv run python -m unittest discover -s tests
```

离线测试采用 Mock 模拟响应，不会向学校服务器发送真实网络请求，亦不会提交任何账号与密码。

## 凭据安全

账号、密码、Cookie、Ticket 票据、加密密文以及携带敏感参数的 URL 均属于敏感凭据，应妥善保管。请勿将其写入日志或提交至代码仓库，同时请合理控制登录重试频率，避免触发验证码或导致账号被临时锁定。

客户端仅将 Cookie 保存在当前进程的内存中。登录示例仅在终端输出接口返回的姓名，不会将任何敏感信息持久化到本地文件。
