# 河北环境工程学院统一身份认证

本项目梳理了河北环境工程学院统一身份认证的认证流程与协议细节，并提供可运行的 Python 示例。开发者可通过脚本自动提交登录表单、维护 Cookie 会话，并直接访问接入统一认证的各类校内业务系统，无需手动操作浏览器。

仓库提供协议文档与可运行示例。使用时直接复制 `hebuee_auth/client.py` 与 `scripts/login.py` 中需要的代码到自己的项目，按实际结构调整；仓库不发布安装包，也不承诺公共 API 兼容性。

## 运行登录示例

运行登录示例需要 Python 3.11 或更高版本、[uv](https://github.com/astral-sh/uv) 以及能够访问学校认证服务器的网络环境。克隆仓库后，在项目根目录运行：

```powershell
uv sync
uv run --with ddddocr python scripts/login.py
```

运行后按提示输入学号或工号及密码（输入密码时不回显）。脚本将通过服务大厅课表入口发起统一认证，随后请求用户信息接口以验证会话有效性。验证通过后，终端会提示登录成功；若接口返回了用户姓名，也会一并输出。

服务端要求验证码时，脚本会读取验证码图片并调用 [`ddddocr`](https://github.com/sml2h3/ddddocr) 识别，失败时换图重试。`Client.login()` 负责最小登录流程；验证码和重复登录的处理都在 `scripts/login.py` 中，方便按需复制。

## 在其他项目中参考

`hebuee_auth/client.py` 提供最小客户端 `Client`，`scripts/login.py` 中的 `login_with_captcha` 演示了验证码取图、识别、换图重试和踢出旧会话的完整写法。复制需要的文件到自己的项目，按项目的导入结构调用即可。

最小调用示例：

```python
client = Client(service_hosts={"ehall.hebuee.edu.cn"})
client.login(service_url, username, password)
```

`Client.login()` 返回认证跳转后的最终 URL 与页面内容（遇到验证码时直接抛出 `CaptchaRequired`）；`Client.request()` 返回请求完成后的 URL 与响应文本。两者共用当前实例内的 Cookie 容器，需要为多个用户维护会话时，分别创建独立的 `Client` 实例。

创建客户端时，`service_hosts` 应包含认证链路中涉及的业务系统域名。客户端已默认内置统一认证服务器域名，并将初始请求与重定向限制在指定的 HTTPS 域名范围内。不同业务系统可能需要额外的会话初始化步骤；接入前先确认入口地址、重定向逻辑和会话验证方式。

## 协议文档

如需使用其他编程语言实现该认证流程，可参考以下协议与接入文档：

- [统一身份认证协议](docs/统一身份认证协议.md)：请求流程、表单字段规范、密码加密算法、验证码处理及 Cookie 会话机制。
- [业务系统接入](docs/业务系统接入.md)：服务大厅登录与会话验证，以及 WebVPN 等系统的接入线索。

## 运行测试

执行离线测试：

```bash
uv run python -m unittest discover -s tests
```

离线测试采用 Mock 模拟响应，不会向学校服务器发送真实网络请求，也不会提交任何账号或密码。

## 凭据安全

账号、密码、Cookie、Ticket 票据、加密密文以及携带敏感参数的 URL 均属于敏感凭据，应妥善保管，不应写入日志或提交至代码仓库。登录重试频率过高会触发验证码，或导致账号被临时锁定。

客户端仅将 Cookie 保存在当前进程的内存中。登录示例仅在终端输出接口返回的姓名，不会将任何敏感信息持久化到本地文件。
