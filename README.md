# 诺诺开放平台 Python SDK

青岛欧姆维护的第三方 `nuonuo-sdk`，导入名 `nuonuo`，独立于 Odoo，要求 Python 3.10+。
采用与发票云 SDK 一致的客户端／业务服务风格。诺诺官方也提供 Python 示例；本库在核对该示例协议的基础上提供可安装包、认证、业务方法、错误处理与离线测试，并非官方 SDK。

## 安装与查询

```bash
pip install nuonuo-sdk==0.2.0
```

生产依赖建议固定已验证版本。源码安装也可固定完整提交 SHA。

```python
import os
from nuonuo import Nuonuo, PRODUCTION_URL, SANDBOX_URL

with Nuonuo(
    app_key=os.environ['NUONUO_APP_KEY'],
    app_secret=os.environ['NUONUO_APP_SECRET'],
    access_token=os.environ['NUONUO_ACCESS_TOKEN'],
    tax_number=os.environ.get('NUONUO_TAX_NUMBER', ''),  # 第三方应用必填授权商户税号
    base_url=SANDBOX_URL,  # 正式环境使用 PRODUCTION_URL，凭据也必须匹配环境
) as client:
    pending = client.invoice.pending(extension_num='0')
    # 使用已经持久保存的原业务单号查询；需应用具有此接口权限。
    result = client.invoice.query(order_nos=['your-existing-order-no'])
```

文档标明 `100188` 等部分接口不支持沙箱；不能假定每个方法都能在沙箱联调。
`100075` 是最近 72 小时内的极速开票待开票列表，不是直接开票接口。

## 认证

自用型应用首次获取：

```python
with Nuonuo(app_key='your-app-key', app_secret='your-app-secret') as client:
    token_data = client.get_merchant_token()
    # 将完整 token_data 写入应用自己的安全存储，后续实例使用 access_token 初始化。
```

获取成功后会更新当前实例 token。自用型应用在到期前显式再次调用 `get_merchant_token()`。
官方说明 token 默认有效 24 小时、30 天内调用上限 50 次；可配置永久有效。
本库不猜测永久 token 的 expires_in 表示，不自动申请或刷新。调用方按账号和环境共享持久化令牌、协调刷新锁并根据返回期限调度；勿每个请求重新取 token。

服务商／第三方应用：

```python
url = client.authorization_url('https://your-app.example/callback', state='secure-random-state')
# 让用户完成授权，服务端核验回调 state 后：
token_data = client.exchange_code(code, tax_number, 'https://your-app.example/callback')
# 保存 access_token、refresh_token、userId、expires_in。刷新时 client_id 是 userId：
new_token_data = client.refresh_isv_token(refresh_token, user_id)
```

授权码一次性使用；不要对不确定结果自动重试交换。刷新后安全保存新令牌，保留原 userId（刷新响应可能不返回它）。
每个实例对应一个应用、环境及商户，不跨线程共享实例；重建 ISV 实例时同时传入对应税号。

## 业务接口

所有返回值均为完整字典，保留 `code`、`describe`、`result`。业务错误也原样返回，不凭通用成功码自动抛异常。

| 方法 | 文档 ID | 用途 |
| --- | --- | --- |
| `client.invoice.pending(extension_num=None)` | 100075 | 极速开票待开票列表 |
| `client.invoice.query(serial_nos=[...])` 或 `query(order_nos=[...])` | 100188 | 开票结果，1–50 个标识 |
| `client.invoice.pdf_url(data)` | 100185 | 获取 PDF 地址，不下载 |
| `client.invoice.inspect(data)` | 100136 | 发票查验，可能消耗额度 |
| `client.invoice.cancel(data)` | 100166 | 对符合条件的发票作废 |
| `client.invoice.redeliver(data)` | 100249 | 明确调用时向短信／邮箱重新交付 |
| `client.invoice.issue_red(data)` | 101018 | 微信／支付宝联用蓝票的全额冲红 |
| `client.nst.issue(order)` | 100607 | 诺税通 SaaS 请求开票 |
| `client.nst.query(order_nos=[...], include_details=True)` | 专用测试账号实测 | 诺税通 SaaS 开票结果，1–50 个标识 |
| `client.nst.list_invoices(data)` | 100595 | 诺税通 SaaS 发票列表 |
| `client.call(method, data)` | 按实际接口 | 其他开放平台 API 通用入口 |

`data` 使用官方字段名，区分大小写。除待开票、结果查询外，业务方法为薄封装，字段必填、长度、税目、金额一致性、红票资格等由调用方按当前接口文档校验。金额可传 `Decimal`，不会先转换为 float；响应 JSON 数值也保留 Decimal。官方标为 String 的金额字段仍应传字符串。

诺税通 SaaS 开票要求对应产品资质与接口授权，`nst.issue` 接受 **order 内部字段**，自动包装成 `{"order": ...}`，不可重复嵌套。调用前保存 `orderNo`（每企业唯一）、完整请求及业务状态，按官方文档填写购销方、明细、`invoiceDate`、`invoiceType` 等字段。不提供可直接运行的真实开票样例，以免将演示数据提交为税票。
`invoice.issue_red` 不是适用所有数电票的通用冲红入口；完整红字确认单流程不在本版业务封装内。

## 下载票文件

`from nuonuo.documents import download_document`，调用
`download_document(url, allowed_hosts={"inv.jss.com.cn"}, kind="pdf")` 返回 `Document(name, mimetype, data)`。
调用前校验查询结果中的订单、购销方、票种与金额，再使用接口返回的文件地址。
允许域名由管理员确认，不从返回 URL 自动加入；仅 HTTPS、无重定向、单文件最多 10 MB，
不携带应用凭据、netrc 凭据或继承代理配置。支持 PDF/OFD/XML；文件头检查不替代税票验真。

## 签名、错误与恢复

- 按官方 Python 2.0.0 示例：固定路径 `/open/v1/services`，Base64(HMAC-SHA1)，UTF-8 JSON 原文参与签名。公共参数放查询串，业务 JSON 放请求体；nonce 为文档要求的 8 位正整数。
- 每次请求自动产生 32 位 `senid`，也可通过各方法的 `senid=` 显式传入。它是通信标识，不等同于业务幂等键。
- 不自动重试业务请求，也不在 token 错误后自动刷新重发；默认连接／读取超时分别为 5／30 秒，拒绝 HTTP 重定向。
- `TransportError`：网络或非 2xx HTTP；`ProtocolError`：无效 JSON／响应结构；`AuthenticationError`：未设置 token 或获取失败。异常文本不包含凭据、URL 或远端原始报文。
- `E0000`、`S0000` 等业务码含义取决于接口。开票“提交成功”仅代表受理；根据原单号／流水号查询最终开票状态。
- 超时、响应丢失或解析失败表示结果未知。先查询原业务单，不生成新订单号自动补开；如果仍不确定，交由业务核实。
- SDK 不记录请求／返回值。返回字典含税票和个人信息，调用方审计时应脱敏。

## 开发与验证

```bash
python -m pip install -e '.[test]'
python -m pytest -q
python -m build
```

离线测试使用合成数据，覆盖官方签名向量、实际发送字节、认证参数、金额精度、错误和防重复提交行为。
GitHub Actions 配置 Python 3.10–3.14。2026-09-22 使用诺诺确认只产生测试数据的专用账号，
已通过列表查询、单张数电普通蓝票提交、原订单结果查询和 PDF/OFD 下载。
该测试账号使用正式网关；不能仅凭网关域名判定账号会否产生真实税票。
历史 Juhui 沙箱配置的 `070601` 记录保留供排查，当前账号已通过验签及业务调用。
详见 [沙箱联调记录](docs/sandbox-validation.md)。

接口取证、文档版本和已知边界见 [docs/api-contract.md](docs/api-contract.md)。
