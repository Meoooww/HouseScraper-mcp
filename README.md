# HouseScraper MCP

一个本地运行的 MCP 服务，用于聚合检索房源，当前第一版支持 `beike`、`lianjia`、`anjuke`。其中 `beike` 和 `lianjia` 现在是分开的平台实现，可以分别探测、分别搜索、分别回归测试。

## 当前能力

- `probe_sources`
  作用：探测平台当前是否可抓取，返回样本数据、cookie 状态、是否疑似触发反爬。
- `search_listings`
  作用：执行一次基础房源搜索，返回统一结构的结果，并在多平台聚合时标记疑似重复房源。
- `get_listing_detail`
  作用：根据稳定的 `listing_ref` 拉取单条房源详情，用于价格和元数据核验。

## 环境准备

要求：

- Python `3.12`
- `uv`

初始化依赖：

```bash
cd /Users/ljh/Documents/GitHub/HouseScraper-mcp
uv sync --python 3.12
```

## 启动服务

本服务默认使用 MCP `stdio` transport。

直接启动：

```bash
cd /Users/ljh/Documents/GitHub/HouseScraper-mcp
uv run housescraper-mcp
```

启动后它会等待 MCP 客户端通过标准输入输出连接，不会自己打印交互界面。

## 接入 MCP 客户端

如果你的 MCP 客户端支持 `command` + `args` 方式接入本地服务，可以配置成：

```json
{
  "mcpServers": {
    "housescraper": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/Users/ljh/Documents/GitHub/HouseScraper-mcp",
        "housescraper-mcp"
      ]
    }
  }
}
```

接入后可直接调用两个工具：`probe_sources` 和 `search_listings`。
现在也支持第三个工具：`get_listing_detail`。

## 怎么调用

### 1. 先探测平台是否可用

示例参数：

```json
{
  "city": "上海",
  "platforms": ["anjuke"]
}
```

返回重点：

- `ok`：是否成功拿到结果
- `result_count`：过滤后的结果数
- `raw_result_count`：平台原始返回数
- `cookies_detected`：是否检测到 cookie
- `captcha_suspected`：是否疑似被反爬拦截
- `sample_titles`：样本房源标题

### 2. 执行房源搜索

示例参数：

```json
{
  "city": "上海",
  "platforms": ["anjuke"],
  "keyword": "世茂滨江花园",
  "max_price": 500,
  "layout": "2室",
  "listing_type": "buy",
  "limit": 5
}
```

返回重点：

- `status`：顶层搜索状态，使用 `success` / `partial_success` / `no_results` / `error`
- `meta`：控制信息，包含平台状态、`raw_count`、`possible_duplicate_count`、`returned_count`、`truncated`
- `data`：统一结构的房源列表
- `data[*].listing_ref`：稳定房源引用，例如 `beike:107114117310`
- `data[*].duplicate_id`：如果当前房源疑似重复，会指向保留主房源的 `listing_ref`
- `meta.platforms[*].filter_mode`：标记平台是 `default`、`native` 还是 `post_filtered`
- `data[*].keyword_match.matched_fields`：当使用 `keyword` 搜索时，展示命中了 `title`、`community`、`address`、`district`、`tags` 中的哪些字段

### 3. 核验单条房源详情

示例参数：

```json
{
  "listing_ref": "beike:107114117310"
}
```

返回重点：

- `status`：`success` 或 `error`
- `meta.listing_ref`：本次核验的稳定房源引用
- `meta.platform`：详情来源平台
- `meta.error_type` / `meta.error_message`：当详情页因 cookie 或反爬不可访问时，给出机器可读错误
- `data.price`、`data.unit_price`、`data.community`、`data.layout`、`data.area`：适合手机侧快速对照的核心字段

## 不通过 MCP，直接本地调用

为了方便本地 smoke test，仓库里还提供了一个轻量 CLI。

探测平台：

```bash
cd /Users/ljh/Documents/GitHub/HouseScraper-mcp
uv run housescraper-cli probe --city 上海 --platform anjuke
```

搜索房源：

```bash
cd /Users/ljh/Documents/GitHub/HouseScraper-mcp
uv run housescraper-cli search --city 上海 --platform anjuke --keyword 世茂滨江花园 --max-price 500 --layout 2室 --limit 5
```

核验单条房源详情：

```bash
cd /Users/ljh/Documents/GitHub/HouseScraper-mcp
uv run housescraper-cli detail --listing-ref beike:107114117310
```

验证多平台聚合 + 去重行为：

```bash
cd /Users/ljh/Documents/GitHub/HouseScraper-mcp
uv run housescraper-cli search \
  --city 上海 \
  --platform beike \
  --platform lianjia \
  --platform anjuke \
  --max-price 500 \
  --layout 2室 \
  --limit 10
```

检查重点：

- 顶层 `status` 应该能区分 `success`、`partial_success`、`no_results`、`error`
- `meta.possible_duplicate_count` 大于 `0` 时，说明本次聚合发现了疑似重复房源
- `data[*].listing_ref` 应为稳定引用，例如 `beike:107114117310`
- `data[*].duplicate_id` 为 `null` 时表示主房源；有值时表示它被判定为重复，并且值会指向主房源的 `listing_ref`
- 疑似重复房源会被移动到主房源之后，但仍然计入 `limit`
- `meta.platforms[*].raw_result_count` 可帮助判断平台原始抓取量与最终返回量的差异

验证已知小区 / 楼盘关键词搜索：

```bash
cd /Users/ljh/Documents/GitHub/HouseScraper-mcp
uv run housescraper-cli search \
  --city 上海 \
  --platform beike \
  --platform lianjia \
  --platform anjuke \
  --keyword 世茂滨江花园 \
  --limit 10
```

检查重点：

- `data` 里应优先保留与 `世茂滨江花园` 相关的结果
- `data[*].keyword_match.matched_fields` 应明确展示是命中了 `title`、`community` 还是其他字段
- `meta.platforms[*].result_count` 可以帮助判断每个平台最终留下了多少条匹配结果
- `meta.platforms[*].raw_result_count` 则能反映平台原始返回量，便于区分“上游就很少”还是“本地二次过滤后变少”

验证单条详情核验：

建议用一个刚刚通过搜索拿到的 `listing_ref` 做 spot check。下面是一条适合本地复现的流程：

```bash
cd /Users/ljh/Documents/GitHub/HouseScraper-mcp
uv run housescraper-cli search \
  --city 上海 \
  --platform beike \
  --keyword 世茂滨江花园 \
  --limit 1
```

从返回结果里复制第一条 `data[0].listing_ref`，然后继续：

```bash
cd /Users/ljh/Documents/GitHub/HouseScraper-mcp
uv run housescraper-cli detail --listing-ref beike:107114117310
```

检查重点：

- `data.price`、`data.unit_price`、`data.community`、`data.layout` 是否足够做手机侧价格比对
- `data.url` 是否指向原始详情页，便于人工二次核验
- 如果当前机器 cookie 失效或被反爬拦截，返回应该是 `status = error`，并带 `meta.error_type` / `meta.error_message`

运行实时回归基线：

```bash
cd /Users/ljh/Documents/GitHub/HouseScraper-mcp
uv run housescraper-cli baseline --city 上海
```

分别测试三个平台：

```bash
cd /Users/ljh/Documents/GitHub/HouseScraper-mcp
uv run housescraper-cli probe --city 上海 --platform beike
uv run housescraper-cli probe --city 上海 --platform lianjia
uv run housescraper-cli probe --city 上海 --platform anjuke
```

这些命令走的就是 MCP 服务底层同一套逻辑，适合先做本地核验。

本次实测

- `2026-05-14` 在这台机器上已验证成功。
- `beike`：`ok=true`，`raw_result_count=30`
- `lianjia`：`ok=true`，`raw_result_count=30`
- `anjuke`：`ok=true`，`raw_result_count=8`

健康结果可这样判断：

- 顶层 `ok` 为 `true`
- `platform_summary` 里每个平台的 `probe_ok` 和 `search_ok` 都为 `true`
- `probe_raw_result_count` 或 `search_result_count` 为正数
- `report_artifact_path` 指向 `artifacts/baseline/` 下的新报告

说明：房源数量会随时间变化，不要把某个固定数量当成唯一正确答案。

## 已知限制

- `anjuke` 当前可以返回真实数据，但有时依赖 fallback 页面，因此服务端会做一层客户端二次过滤。
- `beike` 主要读取 `ke.com` cookie。
- `lianjia` 优先读取 `lianjia.com` cookie；如果浏览器里还没有链家自己的 cookie，会回退复用 `ke.com` 的共享登录票据。
- `beike` / `lianjia` 带筛选条件时，当前会优先抓基础列表页，再在本地做价格 / 面积 / 户型 / 区域过滤，目的是降低验证码触发概率。
- 关键词搜索当前也遵循同样的保守策略：会尽量把 `keyword` 传给支持的平台，同时继续在本地做一致性的二次校验，并在结果里显式标出匹配字段。
- 多平台去重目前是保守的 advisory heuristic：主要依赖跨平台 `community + district + area` 近似匹配，只做标记和排序，不会把不同来源硬合并成一条记录。
- 详情核验当前依赖本机浏览器里已有的真实登录态和 cookie；如果 cookie 过期或详情页触发反爬，服务会返回结构化错误而不是伪造空详情。
- `lianjia` 列表页里的区位字段更接近商圈/板块，不一定总是行政区。
- 第一版的关键词搜索更适合“已知小区 / 楼盘名”的精确或半精确命中，还不适合复杂自然语言检索。
