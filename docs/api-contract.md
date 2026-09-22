# API 协议核验记录

核验日期：2026-09-19。数据来自诺诺公开文档页面使用的官方 JSON 接口及官方 SDK 下载。

本任务为独立 SDK，无 Odoo 运行时版本；已检索 Solutions/mommy_base，没有可直接复用的诺诺协议客户端，不引入 Odoo 依赖。参考现有 fapiaozone-sdk 的包结构与业务服务模式。

## 来源

- [API 文档入口](https://jss.com.cn/open/#/api-doc/common-api?id=100075)
- [自用／服务商认证](https://jss.com.cn/open/#/dev-doc/create-app)
- [官方 SDK 中心](https://jss.com.cn/open/#/dev-doc/sdk-usage)
- [公开 SDK 下载索引](https://jss.com.cn/open/api/interplatform/getSdkDownLoadUrl.do)

官方 Python 示例包版本名 `nuonuo-sdk-python2.0.0`（ZIP 内时间 2019-08-31）；仅用于核对协议，未将其源码复制分发。

ZIP SHA256: `09def6467fbec50f9770f4804409a1763da850228935ec9c868ea8f583f6a2b3`

签名固定向量（合成数据）：secret=`secret`, appkey=`app`, senid=32 个 a, nonce=`12345678`, content=`{"name":"中文"}`, timestamp=`1700000000`；官方函数输出 `4BzcKzrcoqxPis0W/W3X2ae0uIo=`。

## 核实的方法与版本

公开详情读取方式：POST `https://jss.com.cn/open/api/interplatform/getApiDetails.do`，表单 `apiId=<ID>&version=`。这是文档读取地址，不是业务网关。

| 文档 | 方法 | 版本 | 沙箱支持 |
| --- | --- | --- | --- |
| [100075](https://jss.com.cn/open/#/api-doc/common-api?id=100075) | `nuonuo.speedBilling.querySpeedBilling` | V2.0, V1.0 | 是 |
| [100188](https://jss.com.cn/open/#/api-doc/common-api?id=100188) | `nuonuo.ElectronInvoice.queryInvoiceResult` | V2.0 | 否 |
| [100185](https://jss.com.cn/open/#/api-doc/common-api?id=100185) | `nuonuo.ElectronInvoice.getPDF` | V2.0 | 否 |
| [100166](https://jss.com.cn/open/#/api-doc/common-api?id=100166) | `nuonuo.electronInvoice.invoiceCancellation` | V2.0 | 否 |
| [100249](https://jss.com.cn/open/#/api-doc/common-api?id=100249) | `nuonuo.ElectronInvoice.deliveryInvoice` | V2.0 | 是 |
| [100136](https://jss.com.cn/open/#/api-doc/common-api?id=100136) | `nuonuo.electronInvoice.invoiceInspection` | V2.0, V1.0 | 否 |
| [101018](https://jss.com.cn/open/#/api-doc/common-api?id=101018) | `nuonuo.ElectronInvoice.unifiedfastInvoiceRed` | V2.0 | 是 |
| [100607](https://jss.com.cn/open/#/api-doc/common-api?id=100607) | `nuonuo.OpeMplatform.requestBillingNew` | V2.0 | 是 |
| [100595](https://jss.com.cn/open/#/api-doc/common-api?id=100595) | `nuonuo.OpeMplatform.queryInvoiceList` | V2.0 | 是 |

## 重要差异

- 100075 的目录显示 V1.0，但详情默认返回 V2.0。实现采用详情确认的 v1/services HTTP 协议；文档版本 V2.0 并不意味着网关路径为 /v2。
- 官方样例随机数范围和文字说明不同：SDK 使用文字要求的 8 位正整数。
- 认证不是业务签名调用：表单提交 client_credentials／authorization_code／refresh_token；刷新的 client_id 必须是 userId。
- 100607 属于诺税通 SaaS 产品；不把此方法伪装成普通诺诺发票直接开票。
- 通用调用保留所有业务返回码；不假定 200 是所有发票接口的成功码。
- 回调接收、验签、所有进项接口及所有特殊票种业务校验未封装；可通过通用调用扩展官方授权接口。
- 2026-09-19 初版未执行业务写操作；后续专用测试账号联调见 sandbox-validation.md。

## 2026-09-22 诺税通查询补充

`client.nst.query` 使用 `nuonuo.OpeMplatform.queryInvoiceResult`，与普通
`nuonuo.ElectronInvoice.queryInvoiceResult` 区分。方法名来自现有 Juhui 对接，
本次专用测试账号已实测 `orderNos`、`isOfferInvoiceDetail="1"` 与最终状态 2 的完整返回。
当前公开诺税通目录未找到该方法的独立文档 ID，不将 100188 误标为该方法文档。
对接方须确认所属应用权限；保留未知状态，不把受理成功当作开票成功。

新下载工具支持明确域名白名单、禁止重定向、大小限制和基本文件头校验。
