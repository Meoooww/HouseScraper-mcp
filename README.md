# HouseScraper MCP

一个本地运行的 MCP 服务，用于聚合检索房源，当前第一版优先支持 `beike` 和 `anjuke`。其中 `lianjia` 在 V0 中作为 `beike` 的别名处理。

## 当前能力

- `probe_sources`
  作用：探测平台当前是否可抓取，返回样本数据、cookie 状态、是否疑似触发反爬。
- `search_listings`
  作用：执行一次基础房源搜索，返回统一结构的结果。

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
  "max_price": 500,
  "layout": "2室",
  "listing_type": "buy",
  "limit": 5
}
```

返回重点：

- `results`：统一结构的房源列表
- `platform_status`：每个平台的抓取状态
- `client_side_filtering`：是否启用了客户端二次过滤

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
uv run housescraper-cli search --city 上海 --platform anjuke --max-price 500 --layout 2室 --limit 5
```

这两个命令走的就是 MCP 服务底层同一套逻辑，适合先做本地核验。

## 已知限制

- `anjuke` 当前可以返回真实数据，但有时依赖 fallback 页面，因此服务端会做一层客户端二次过滤。
- `beike` / `lianjia` 需要先在浏览器打开一次 `ke.com`，让服务读取可用 cookie。
- `beike` / `lianjia` 带筛选条件时，当前会优先抓基础列表页，再在本地做价格 / 面积 / 户型 / 区域过滤，目的是降低验证码触发概率。
- 第一版还不支持“按楼盘名精确搜索”，目前更适合按城市、区域、总价、面积、户型做海选。
