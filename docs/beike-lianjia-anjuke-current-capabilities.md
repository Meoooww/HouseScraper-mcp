# `beike` / `lianjia` / `anjuke` 当前已实现能力

## 说明

- 本文基于当前本地源码分析：`/Users/ljh/Documents/GitHub/HouseScraper-mcp/src/house_cli`
- 分析目标是“当前这份代码实际上实现了什么”，不是 README 宣称了什么
- 重点只覆盖三个来源：
  - `beike`
  - `lianjia`
  - `anjuke`
- 结论由两部分组成：
  - 静态源码分析
  - 少量命令行为验证

## 总体架构

当前 `house-cli` 的平台适配是统一模型、平台特化解析的架构：

- 统一接口：`src/house_cli/client/base.py`
- 平台注册：`src/house_cli/client/adapters/__init__.py`
- 统一数据模型：
  - `src/house_cli/models/house.py`
  - `src/house_cli/models/filter.py`
- 统一命令入口：`src/house_cli/main.py`

### 对外命令

当前已经注册的 CLI 命令有：

- `search`
- `detail`
- `compare`
- `analyze`
- `mortgage`
- `watch`
- `export`

### 统一数据模型

搜索结果统一映射为 `House`，详情页统一映射为 `HouseDetail`。

`House` 当前的统一字段包括：

- `id`
- `platform`
- `title`
- `price`
- `price_unit`
- `area`
- `unit_price`
- `layout`
- `floor`
- `orientation`
- `community`
- `district`
- `city`
- `address`
- `url`
- `listing_date`
- `tags`

`HouseDetail` 在此基础上扩展了：

- `description`
- `building_year`
- `building_type`
- `elevator`
- `parking`
- `green_ratio`
- `volume_ratio`
- `property_fee`
- `nearby_schools`
- `nearby_subway`
- `price_history`
- `images`

### 平台注册现状

当前注册表里真正存在的平台 key 是：

- `beike`
- `anjuke`
- `tongcheng`
- `ziroom`
- `fang`
- `zhuge`

这里没有 `lianjia`。这意味着：

- `lianjia` 不是当前的独立平台实现
- CLI 不支持 `--platform lianjia`
- “链家”目前只存在于注释、README 和 `beike` 适配器文案里

---

## `beike` 当前已实现能力

## 平台定位

当前 `beike` 的真实抓取目标是 `ke.com`，实现文件是：

- `src/house_cli/client/adapters/beike.py`

代码注释写的是 `Beike/Lianjia adapter`，但实际 URL 都是：

- 列表页：`https://{city}.ke.com/ershoufang/...`
- 详情页：`https://{city}.ke.com/ershoufang/{id}.html`

因此当前更准确的说法是：

- `beike` 已实现
- “链家”语义被合并到 `beike` 文案里
- 没有单独的 `lianjia` 抓取入口

## `beike.search()` 已实现内容

### 已实现的搜索入口

`beike.search()` 已实现二手房列表抓取：

- 通过 `ke.com/ershoufang/` 路径访问
- 使用 cookie + 反爬请求头 + 异步 HTTP 抓取 HTML
- 通过字符串切分和正则提取卡片字段

### 当前真正生效的筛选项

`beike` 是三个目标来源里筛选能力最完整的一个，当前已真实接入 URL 构造的筛选项有：

| 筛选项 | 当前状态 | 说明 |
| --- | --- | --- |
| `city` | 已实现 | 通过 `CITY_ABBR` 切换子域名 |
| `district` | 已实现 | 通过 `DISTRICTS` 做中文区名到 slug 的映射 |
| `min_price` / `max_price` | 已实现 | 转成 `bp{lo}ep{hi}` |
| `min_area` / `max_area` | 已实现 | 转成 `ba{lo}ea{hi}` |
| `layout` | 已实现 | 通过数字转成 `l1` 到 `l5` |
| `sort_by` | 已实现一部分 | `price_asc` / `price_desc` / `area` 会映射到 URL |
| `page` | 代码里已支持 | 大于 1 时追加 `pg{page}`，但 CLI 没暴露 |

### 列表页实际返回字段

`beike.search()` 返回的 `House`，当前能填充这些字段：

| 字段 | 当前状态 | 来源 |
| --- | --- | --- |
| `id` | 已填充 | 从详情链接提取 |
| `platform` | 已填充 | 固定 `beike` |
| `title` | 已填充 | 卡片标题 |
| `price` | 已填充 | 总价 |
| `price_unit` | 已填充 | 固定 `万` |
| `area` | 已填充 | `houseInfo` 区块 |
| `unit_price` | 已填充 | `unitPrice` 区块 |
| `layout` | 已填充 | `houseInfo` 区块 |
| `floor` | 已填充 | `houseInfo` 区块 |
| `orientation` | 已填充 | `houseInfo` 区块 |
| `community` | 已填充 | 小区链接文本 |
| `district` | 已填充 | 从 `alt` 文本推断 |
| `city` | 已填充 | 搜索入参 |
| `url` | 已填充 | 详情链接 |
| `listing_date` | 已填充 | `followInfo` 中的“发布”文本 |
| `tags` | 已填充 | 卡片标签 |
| `address` | 未填充 | 列表页不返回 |

### 列表阶段可被上层直接消费的能力

基于当前 `beike.search()`，上层已经可以直接做：

- 多条件二手房搜索
- 统一格式 JSON / YAML 输出
- 列表页价格排序、面积排序
- 基于统一模型的跨平台聚合展示

## `beike.detail()` 已实现内容

### 已实现的详情页入口

`beike.detail()` 已实现：

- 通过 cookie 访问详情页
- 从详情 HTML 里抽取结构化字段
- 返回 `HouseDetail`

### 详情页当前实际返回字段

`beike.detail()` 当前能填充的字段比较完整：

| 字段 | 当前状态 |
| --- | --- |
| `title` | 已填充 |
| `price` | 已填充 |
| `price_unit` | 已填充，固定 `万` |
| `area` | 已填充 |
| `unit_price` | 已填充 |
| `layout` | 已填充 |
| `floor` | 已填充 |
| `orientation` | 已填充 |
| `community` | 已填充 |
| `district` | 已填充 |
| `address` | 已填充 |
| `building_year` | 已填充 |
| `building_type` | 已填充 |
| `elevator` | 已填充 |
| `parking` | 已填充 |
| `green_ratio` | 已填充 |
| `volume_ratio` | 已填充 |
| `property_fee` | 已填充 |
| `nearby_schools` | 已填充 |
| `nearby_subway` | 已填充 |
| `description` | 已填充 |
| `tags` | 已填充 |
| `price_history` | 尝试填充 | 依赖页面里是否包含 `priceHistory` |
| `images` | 尝试填充 | 最多取前 10 张 |

### 基于详情页已打通的衍生命令

只要 `beike.detail()` 能拿到页面，以下命令都已经可以工作：

- `detail`
- `compare`
- `analyze`
- `watch`

其中：

- `compare` 会并排展示两套房的详情字段
- `analyze` 会把详情页信息组织成价格、通勤、学校、投资几个小节
- `watch` 会把详情快照写入本地关注列表

## `beike` 当前能力边界

虽然 `beike` 是目前三者里最完整的实现，但它当前实际聚焦的是：

- `ke.com`
- 二手房列表
- HTML 正则解析

也就是说，当前已经可以把它看作一个“二手房搜索 + 详情抓取”的可用基座。

---

## `lianjia` 当前已实现能力

## 当前真实状态

`lianjia` 当前没有独立 adapter、没有独立平台注册，也没有独立 CLI 能力。

### 代码层事实

以下位置出现了“链家”语义：

- `README.md` 写了支持 `lianjia`
- `src/house_cli/client/adapters/beike.py` 标题写了 `Beike/Lianjia`
- `src/house_cli/client/auth.py` 的 cookie 示例里出现了 `lianjia_uuid`

但以下关键位置没有 `lianjia`：

- `ADAPTER_REGISTRY`
- `BUY_PLATFORMS`
- `RENT_PLATFORMS`
- CLI `--platform` 的实际可选集合

## `lianjia` 当前实际可用能力

如果严格按“平台”来定义能力，那么 `lianjia` 当前已实现能力是：

- 没有独立 `search`
- 没有独立 `detail`
- 没有独立 `compare`
- 没有独立 `analyze`
- 没有独立 `watch`
- 没有独立字段模型

如果按“品牌语义并入 `beike`”来定义，那么当前唯一能说得通的表述是：

- “链家能力”被耦合进了 `beike` 适配器
- 用户必须使用 `beike` 才能走当前实现

## 行为验证

从当前源码直接运行：

```bash
PYTHONPATH=src .venv/bin/python -m house_cli.main search --platform lianjia --city 上海 --output json
```

结果是：

```text
Error: Unknown platform: lianjia
```

因此，`lianjia` 当前不是一个可以单独调用的平台能力。

---

## `anjuke` 当前已实现能力

## 平台定位

`anjuke` 的实现文件是：

- `src/house_cli/client/adapters/anjuke.py`

真实参数探测报告见：

- `docs/anjuke-real-probe-2026-05-15.md`
- 注意区分“代码声明层契约”和“实时抓取已验证参数”

当前策略是：

1. 通过筛选流入口模板访问 `https://{city}.anjuke.com/sale/?from=HomePage_Search`
2. 如果 `sale` 页不可用，就回退到城市首页
3. 从可解析的卡片区块提取房源

这意味着它已经有了明确的“筛选流入口契约”，但还不是完整的强条件搜索器。

## `anjuke.search()` 已实现内容

### 已实现的搜索入口

当前 `anjuke.search()` 已经具备：

- cookie 驱动访问
- `sale` 筛选流入口抓取（`from=HomePage_Search`）
- 城市首页回退逻辑
- 列表 HTML 正则解析
- 返回统一 `House` 数据模型

### 已实现的筛选流入口契约（用于 MCP/工具层对接）

`AnjukeClient` 当前已经提供两个公开方法：

- `filter_flow_contract()`: 返回筛选流契约（入口模板、接受入参、返回字段）
- `build_filter_flow_entry(filters)`: 返回本次请求的入口 URL 与归一化参数

当前契约定义为：

- `flow_name`: `anjuke_sale_filter_flow`
- `entry_url_template`: `https://{city}.anjuke.com/sale/?from=HomePage_Search`

当前声明接受的入参有：

- `city`（required）
- `district`
- `min_price`
- `max_price`
- `min_area`
- `max_area`
- `layout`
- `sort_by`
- `page`
- `keywords`
- `listing_type`

当前声明的统一返回字段有：

- `id`
- `platform`
- `title`
- `price`
- `price_unit`
- `area`
- `unit_price`
- `layout`
- `district`
- `city`
- `url`

### 当前真正参与搜索 URL 构造的筛选项

`anjuke` 当前代码里真正参与 URL 构造的筛选项是：

| 筛选项 | 当前状态 | 说明 |
| --- | --- | --- |
| `city` | 已实现 | 通过 `ANJUKE_CITY` 做城市映射并落到子域名 |
| 其他筛选项 | 未实现到 URL | 当前只进入统一筛选流入口，未把筛选项编码到 URL |

### 列表页实际返回字段

`anjuke.search()` 返回的 `House` 当前能稳定填充：

| 字段 | 当前状态 | 来源 |
| --- | --- | --- |
| `id` | 已填充 | 从 `/prop/view/` 链接提取 |
| `platform` | 已填充 | 固定 `anjuke` |
| `title` | 已填充 | 卡片标题 |
| `price` | 已填充 | 卡片价格 |
| `price_unit` | 已填充 | 固定 `万` |
| `area` | 已填充 | `xx㎡` 文本 |
| `unit_price` | 已填充 | `xx元/㎡` 文本 |
| `layout` | 已填充 | `2室1厅` 这类文本 |
| `district` | 已填充 | 取“区域 商圈”中的第一段 |
| `city` | 已填充 | 搜索入参 |
| `url` | 已填充 | 原始详情链接 |

以下字段在当前列表阶段没有填：

| 字段 | 当前状态 |
| --- | --- |
| `community` | 未填充 |
| `floor` | 未填充 |
| `orientation` | 未填充 |
| `address` | 未填充 |
| `listing_date` | 未填充 |
| `tags` | 未填充 |

### 当前基于列表能力已经可用的事情

在当前实现下，`anjuke` 已经可以支持：

- 城市级房源列表抓取
- 基于列表的统一输出
- 作为聚合结果源参与 `search`

它当前更适合作为：

- 候选房源发现源
- 聚合搜索的补充来源

而不是完整详情主源。

## `anjuke.detail()` 已实现内容

### 已实现的详情能力

`anjuke.detail()` 当前已经实现：

- 用 cookie 请求详情页
- 从详情页拿标题
- 尝试用一个正则提取价格
- 返回 `HouseDetail`

### 当前详情页实际返回字段

当前 `anjuke.detail()` 真正会填的字段很少：

| 字段 | 当前状态 |
| --- | --- |
| `id` | 已填充 |
| `platform` | 已填充 |
| `title` | 已填充 |
| `price` | 尝试填充 |
| `price_unit` | 已填充，固定 `万` |
| `url` | 已填充 |

其余详情字段目前基本依赖 dataclass 默认值：

- `area`
- `unit_price`
- `layout`
- `floor`
- `orientation`
- `community`
- `district`
- `address`
- `building_year`
- `nearby_subway`
- `nearby_schools`
- `images`
- `price_history`

### 基于详情页当前已经“能跑”的衍生命令

因为 `detail()` 已经有返回值，以下命令在技术上可以执行：

- `detail`
- `compare`
- `analyze`
- `watch`

但它们对 `anjuke` 的实际价值取决于详情字段丰富度，而不是命令本身有没有注册。

---

## 当前能力矩阵

| 能力 | `beike` | `lianjia` | `anjuke` |
| --- | --- | --- | --- |
| 独立平台注册 | 有 | 没有 | 有 |
| `search` | 有 | 没有 | 有 |
| `detail` | 有 | 没有 | 有 |
| `compare` | 可用 | 不可用 | 可执行 |
| `analyze` | 可用 | 不可用 | 可执行 |
| `watch` | 可用 | 不可用 | 可执行 |
| 聚合搜索参与 `all` | 有 | 没有 | 有 |
| 独立 `--platform` | `beike` | 不支持 | `anjuke` |

## 当前字段完整度对比

| 维度 | `beike` | `lianjia` | `anjuke` |
| --- | --- | --- | --- |
| 列表字段完整度 | 高 | 不存在独立实现 | 中 |
| 详情字段完整度 | 高 | 不存在独立实现 | 低 |
| 筛选能力完整度 | 高 | 不存在独立实现 | 低 |

## 当前最准确的产品定义

就现在这份代码本身而言，更准确的产品定义应该是：

- `beike`：一个比较完整的 `ke.com` 二手房搜索与详情抓取适配器
- `lianjia`：尚未独立实现，只是并入 `beike` 的文案概念
- `anjuke`：一个可用的列表抓取来源，已实现筛选流入口契约，详情能力已打通但字段仍然较薄
