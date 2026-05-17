# `beike` / `lianjia` / `anjuke` 当前缺点与重要未实现项

## 说明

- 本文只讨论当前源码的缺点、耦合点和“已经给出规划/契约，但尚未真正实现”的能力
- 源码位置基于：`/Users/ljh/Documents/GitHub/HouseScraper-mcp/src/house_cli`
- 这里的“重要未实现项”优先指会直接影响你后续做平台解耦、能力补齐和 MCP 化的内容

## 一句话结论

当前最大的结构性问题不是“没有功能”，而是：

1. `beike`、`lianjia`、`anjuke` 三者并没有真正按平台解耦
2. 代码里存在多处“宣称支持”的能力，但没有完整实现
3. 列表、详情、导出、监控之间有多条能力链条没有闭环

---

## 1. 跨平台层面的核心缺点

## 1.1 `lianjia` 并没有独立实现

这是当前最重要的耦合问题。

### 现状

- README 写支持 `lianjia`
- `beike.py` 写的是 `Beike/Lianjia adapter`
- 但平台注册表没有 `lianjia`

### 影响

- 平台边界不清晰
- 无法单独调用 `lianjia`
- 无法单独给 `lianjia` 做能力矩阵、测试、配置和反爬策略
- 后续做 MCP 工具时，无法明确告诉上层“当前调用的是贝壳还是链家”

### 结论

这意味着你提出的“确保 `beike` / `lianjia` / `anjuke` 各自解耦、功能清晰”，第一刀就应该落在这里。

## 1.2 “支持买房 + 租房”是规划级表述，不是三平台都已完整实现

多个地方都把平台描述成 `buy + rent`：

- `beike.py` 的类文案
- `anjuke.py` 的类文案
- `adapters/__init__.py` 的 `RENT_PLATFORMS`
- `SearchFilter.listing_type`
- `search` 命令的 `--type [buy|rent]`

但就当前三个平台的真实实现而言：

- `beike` 明显是围绕 `ershoufang` 写的
- `anjuke` 明显是围绕 `sale` 与推荐房源写的
- `lianjia` 连独立平台都不存在

这说明：

- “租房支持”现在更多是接口层和产品层的规划
- 不是这三个平台都已经具备完整的 rent parser

## 1.3 统一模型定义超前于平台真实落地

`HouseDetail` 和 `SearchFilter` 已经定义了很多字段与参数：

- `page`
- `page_size`
- `keywords`
- `tags`
- `nearby_subway`
- `nearby_schools`
- `price_history`
- `images`

但在三个目标平台里：

- 这些字段并没有都被真正实现
- 不同平台的覆盖度差异非常大

这不是坏事，但说明当前架构阶段是：

- 模型先行
- 平台实现滞后

---

## 2. `beike` 当前缺点

## 2.1 `beike` 与 `lianjia` 语义耦合，没有拆干净

### 现状

- 文件名是 `beike.py`
- `platform_name` 是 `beike`
- 但类文案写成 `Beike/Lianjia`

### 问题

- 这是“一个平台实现承载两个品牌语义”
- 会让后续接口设计变得模糊
- 不利于把 `lianjia` 做成独立 source

### 这属于重要未实现项吗

属于，而且非常重要，因为这直接决定后续 API 设计、测试设计和配置设计。

## 2.2 详情页城市被写死成上海

`beike.detail()` 当前写死了：

- `city_abbr = "sh"`
- `url = https://sh.ke.com/ershoufang/{house_id}.html`
- 返回里的 `url` 也是上海域名

### 影响

- 多城市房源详情抓取不严谨
- URL 与真实城市不一致
- 后续做跨城市搜索、详情二跳时容易出错

### 重要性

高。这是 `beike` 详情可靠性的核心缺陷之一。

## 2.3 `district` 识别是硬编码，泛化不足

列表页 `district` 的提取依赖：

- 图片 `alt` 文本格式
- 一组硬编码区名

### 影响

- 超出名单的城市或区名可能识别不准确
- DOM 轻微调整就可能导致解析失效

### 结论

这是 parser 稳定性问题，不是接口问题，但对生产可用性影响很大。

## 2.4 `building_year` 在列表阶段被解析了，但没有进入统一返回

`beike` 列表解析时实际上读出了 `building_year`，但 `House` 没有对应字段，所以这个信息被丢掉了。

### 含义

- 解析器能力和模型返回之间存在信息损耗
- 如果后面你想在列表页就展示年代，现在这条链是不闭合的

### 优先级

中。不是第一优先级，但改造时值得顺手一起考虑。

## 2.5 强依赖 cookie 和 CAPTCHA 绕过

`beike` 当前流程高度依赖：

- 浏览器 cookie
- 反爬请求头
- 页面长度阈值判断

### 影响

- 可用性高度受 cookie 新鲜度和站点策略影响
- 不是稳定、可预测的抓取链路

### 重要性

高。这是运行时能力问题，不是接口设计问题，但后续要做服务化时必须重点处理。

---

## 3. `lianjia` 当前缺点

## 3.1 没有独立 adapter

当前没有：

- `src/house_cli/client/adapters/lianjia.py`
- `platform_name = "lianjia"`
- `ADAPTER_REGISTRY["lianjia"]`

### 影响

- 不能单独搜索
- 不能单独查详情
- 不能单独做能力声明
- 不能单独做测试

### 这是最重要的未实现项之一

是。因为你明确希望三者各自解耦，而 `lianjia` 现在其实还不存在。

## 3.2 没有独立命令入口

当前运行：

```bash
PYTHONPATH=src .venv/bin/python -m house_cli.main search --platform lianjia --city 上海 --output json
```

直接报错：

```text
Error: Unknown platform: lianjia
```

这说明 `lianjia` 现在不是“能力差”，而是“没有接入平台层”。

## 3.3 没有独立数据与配置边界

当前 `lianjia` 没有：

- 独立 cookie 域策略
- 独立 URL 构造器
- 独立字段 parser
- 独立监控策略

### 对改造的启示

后面一旦要拆开，至少要决定：

- `lianjia` 是 `beike` 的 alias，还是一个真正独立的平台 source
- 如果独立，是否抓 `lianjia.com`
- 如果只是 alias，是否应该从 README 和 API 文案里删除“独立平台”表述

---

## 4. `anjuke` 当前缺点

实时证据参考：

- `docs/anjuke-real-probe-2026-05-15.md`

## 4.1 搜索筛选能力仍不完整（但入口契约已落地）

截至当前实现，`anjuke` 已经补上了筛选流入口：

- 入口模板：`https://{city}.anjuke.com/sale/?from=HomePage_Search`

但 `anjuke.search()` 真正参与 URL 构造并影响请求路径的仍然主要是：

- `city`
- 命中本地 slug 的 `district`

以下字段虽然在统一模型和 CLI 中都出现了，但没有被 `anjuke` 实际消费：

- `min_price`
- `max_price`
- `min_area`
- `max_area`
- `layout`
- `sort_by`
- `page`
- `page_size`
- `keywords`
- `tags`
- `listing_type=rent`

### 影响

- 上层现在可以知道“接口声明支持哪些参数”，但仍不能保证这些参数在站点端生效
- 结果仍可能是宽泛列表，甚至在回退时变成推荐流结果

### 重要性

非常高。这是 `anjuke` 从“能跑”到“能用”的关键一步。

## 4.2 `district` 仅在本地已有 slug 时生效

当前代码里，`district` 会尝试从本地 `DISTRICTS` 映射转成站点可识别的 path slug。

### 含义

`district` 对已有映射的城市/区域可生效；缺失映射时仍会退回城市列表入口。

## 4.3 搜索会回退到首页推荐房源，不是真正的条件搜索闭环

当前流程是：

1. 先试 `sale` 页
2. 不行就退到城市首页
3. 从首页推荐卡片里继续解析

### 影响

- 返回结果和用户条件之间的关系变弱
- 结果更像“城市推荐房源”
- 不适合作为严谨筛选结果源

### 重要性

高。这个问题和上一个组合起来，决定了 `anjuke.search()` 目前更像“发现源”，而不是“搜索引擎”。

## 4.4 详情页城市被写死成北京

`anjuke.detail()` 当前写的是：

- `city = "beijing"`
- `url = https://beijing.anjuke.com/prop/view/{house_id}`

### 影响

- 上海、杭州、深圳等城市房源会落到错误城市域名
- 标题、链接、页面内容都可能错位

### 重要性

非常高。这是 `anjuke.detail()` 目前最大的问题之一。

## 4.5 详情字段几乎没有真正实现

`anjuke.detail()` 当前真正做的只有：

- 取 `<title>`
- 用一个正则尝试抓价格

而这些重要字段都没有解析：

- `area`
- `unit_price`
- `layout`
- `floor`
- `orientation`
- `community`
- `district`
- `address`
- `building_year`
- `building_type`
- `nearby_subway`
- `nearby_schools`
- `price_history`
- `images`
- `tags`

### 影响

`anjuke` 详情页现在更像“最小可返回对象”，不是一个真正的详情抓取器。

### 重要性

非常高。因为 `compare`、`analyze`、`watch` 都依赖这个能力。

## 4.6 `get_price_history()` 只是接口链路打通，不是能力真的实现了

当前 `anjuke.get_price_history()` 只是：

- 先调 `detail()`
- 再返回 `d.price_history`

但 `detail()` 根本没有填 `price_history`。

### 这说明什么

- 这是“接口上存在、语义上承诺、实现上为空”的典型例子
- 是后续非常值得优先补齐的能力

---

## 5. 与三个平台强相关的“已规划但未实现”能力

下面这些是当前最值得你优先关注的“已经给出规划或契约，但尚未真正落地”的能力。

## 5.1 独立 `lianjia` 平台

### 规划迹象

- README 写支持 `lianjia`
- `beike.py` 写 `Beike/Lianjia`

### 当前缺失

- 平台注册
- 独立 adapter
- 独立命令入口
- 独立字段能力说明

### 重要性

最高。因为这就是“平台解耦”的核心。

## 5.2 `buy + rent` 双类型支持

### 规划迹象

- `SearchFilter.listing_type`
- `search --type [buy|rent]`
- `RENT_PLATFORMS`
- `beike` / `anjuke` 类注释里都写了 `buy + rent`

### 当前缺失

- `beike` 仍然只走 `ershoufang`
- `anjuke` 仍然只走 `sale`
- `lianjia` 没有独立实现

### 重要性

很高。因为这决定了平台能力声明是否可信。

## 5.3 搜索结果缓存与导出闭环

### 规划迹象

- `export` 命令依赖 `~/.config/house-cli/last_search.json`
- `utils/cache.py` 明确写了 `Search result index cache`

### 当前缺失

- `search` 没有把结果写进缓存
- `utils/cache.py` 还是空壳

### 行为验证

当前运行：

```bash
PYTHONPATH=src .venv/bin/python -m house_cli.main export --format json --output /tmp/house-cli-export.json
```

会直接报：

```text
No cached search results. Run 'house search' first.
```

但实际上当前 `search` 并不会自动写这个缓存。

### 重要性

很高。因为它直接让 `export` 变成了未闭环功能。

## 5.4 搜索分页、关键词、标签过滤

### 规划迹象

`SearchFilter` 里已经定义了：

- `page`
- `page_size`
- `keywords`
- `tags`

### 当前缺失

在这三个平台里：

- `page_size` 没真正接入
- `keywords` 没真正接入
- `tags` 没真正接入
- `page` 只有 `beike` 部分支持，CLI 也没暴露

### 重要性

高。这些都是后续做“可控搜索”必须补的基础能力。

## 5.5 真实价格监控

### 规划迹象

- `watch` 命令文案写的是 `Watch a house for price changes`
- `BaseClient` 里定义了 `get_price_history()`

### 当前缺失

`watch` 当前只做：

- 抓一次详情快照
- 写到 `watchlist.json`

它没有：

- 定时轮询
- 历史价格比对
- 变更通知
- 价格趋势存储

### 重要性

高。如果后面你想把这个项目做成“持续跟踪”工具，这一块必须补。

## 5.6 真正的配置层与格式化层

### 规划迹象

这些文件已经存在：

- `src/house_cli/utils/cache.py`
- `src/house_cli/utils/config.py`
- `src/house_cli/utils/formatter.py`

### 当前状态

它们仍然只是：

- `# To be implemented`

### 重要性

中高。不是最先改的功能入口，但对工程化、可配置化、统一输出会越来越重要。

---

## 6. 衍生命令的当前缺点

这些不是平台 adapter 本身的问题，但它们直接受三平台能力影响，尤其是 `beike` 和 `anjuke`。

## 6.1 `compare` 依赖详情质量

### 现状

`compare` 是纯粹把两个 `detail()` 的结果并排展示。

### 含义

- `beike` 详情强，`compare` 才有价值
- `anjuke` 详情薄，`compare` 的信息密度就很低
- `lianjia` 由于没有独立平台，根本没法独立比较

## 6.2 `analyze` 不是 AI 分析引擎，只是模板化摘要

### 规划迹象

- 命令文案写的是 `AI-powered analysis`

### 当前实现

实际上只是把详情字段拼成几段 Markdown：

- 价格分析
- 通勤分析
- 教育资源
- 投资参考

### 影响

- 它完全依赖详情字段质量
- 不是独立的智能分析能力

## 6.3 `watch` 不是监控系统，只是收藏夹

### 当前实现

`watch` 只支持：

- 添加
- 删除
- 列表展示

### 当前没有

- 自动检测价格变化
- 历史变更记录
- 差异比较
- 通知机制

---

## 7. 重要性排序

如果目标是“先补齐 `house-cli` 基本能力，并确保三个平台各自解耦、功能清晰”，我建议的优先级如下。

## P0

- 把 `lianjia` 的平台身份定清楚：独立 adapter 还是明确 alias
- 修 `anjuke.detail()`：至少补齐城市、价格、面积、户型、区域、小区
- 修 `export` 闭环：让 `search` 真正写入 `last_search.json`

## P1

- 给 `anjuke.search()` 补真实筛选：价格、面积、户型、排序、分页
- 把 `beike.detail()` 的城市 hardcode 去掉
- 明确 `beike` / `anjuke` 的 `rent` 是否真的支持

## P2

- 给 `watch` 增加真实的价格变化检测
- 把 `price_history` 变成可用能力
- 把 `utils/cache.py`、`config.py`、`formatter.py` 补成真正的工具层

---

## 8. 最终判断

当前三者的真实状态不是“都差不多”，而是分层明显：

- `beike`：能力最完整，但品牌语义耦合、城市 hardcode 和反爬依赖都很重
- `lianjia`：还不是一个真正存在的平台实现
- `anjuke`：列表抓取已成形，但详情和真实筛选都远未补齐

如果你的目标是“平台解耦 + 基本能力补齐”，最关键的不是先加新平台，而是先把这三条链补完整：

1. 平台身份链：`lianjia` 到底是什么
2. 搜索闭环链：筛选参数到底有没有真的生效
3. 数据闭环链：`search -> detail -> compare/analyze/watch/export` 是否真正贯通
