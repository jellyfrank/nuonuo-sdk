# 沙箱联调记录

日期：2026-09-19。SDK 基线：`8da546993049791ffb668a854de70f9b067908ff`。

凭据来源：用户授权使用 Juhui `jhui_account_nuonuo` 模块中
`btn_gen_testconfig` 保存的历史测试应用配置。凭据只在内存中读取，未复制到本仓库。

目标：`https://sandbox.nuonuocs.cn/open/v1/services`。

| 检查 | 结果 |
| --- | --- |
| SDK `invoice.pending('0')` | 收到 JSON：`070601`，签名不匹配 |
| SDK `nst.list_invoices(...)` | 收到 JSON：`070601`，签名不匹配 |
| 官方 Python 2.0.0 示例发送相同待开票查询 | 同样返回 `070601`，签名不匹配 |
| 相同凭据及固定输入下 SDK 与官方函数签名比较 | 完全一致 |
| 离线回归测试 | 55 项通过 |

结论：网络连接、HTTP 请求发送与 JSON 解析已走通；所选历史凭据未通过沙箱网关验签。
官方示例同样失败，当前证据不支持修改 SDK 签名算法。
尚不能确认这组 AppKey/AppSecret 与当前沙箱应用匹配，也未验证 token 有效性、接口权限或业务响应。
下一步需在诺诺开放平台确认当前沙箱应用及配套 AppKey/AppSecret/access_token，再执行相同只读检查。

未请求新 token、未访问正式业务网关、未执行开票、冲红、作废、查验或短信／邮件交付。
