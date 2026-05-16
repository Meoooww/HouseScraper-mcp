# HouseScraper

用于聚合检索房源，当前确认可用的平台是 `beike`、`anjuke`。

说明：

- `beike` 真实抓取的是 `ke.com`
- `anjuke` 真实抓取的是 `anjuke.com`
- `lianjia` 目前不是独立平台入口，不能直接 `--platform lianjia`
- 贝壳和链家在业务上高度相关，但当前代码里“链家”不是单独 adapter

基于 https://github.com/Luxuzhou/house-cli 二次开发
请求头根据本机环境动态生成更贴近真实浏览器的指纹

## Agent Quick Start

如果你是 agent，建议按这个顺序准备环境并验证：

1. 先在真实浏览器中打开目标站点并完成验证：
   - 贝壳：<https://sh.ke.com/ershoufang/>
   - 安居客：<https://shanghai.anjuke.com/sale/>
2. 确认页面已经能正常看到房源列表，而不是登录页、验证码页或空白页。
3. 让本项目读取或刷新本地 cookies。
4. 先单独验证 `beike` 和 `anjuke`，再跑聚合查询。

## Cookie 前置

项目依赖浏览器会话 cookies，默认从这里读取：

- `~/.config/house-cli/cookies.json`

cookie 解析顺序见 `src/house_cli/client/auth.py`：

1. 优先读取 `~/.config/house-cli/cookies.json`
2. 文件没有或已过期时，尝试从 Chrome / Edge / Firefox 自动提取
3. 如果仍然拿不到，调用方自己处理失败

补充说明：

- cookie TTL 当前是 7 天
- 过期后会被当成不可用
- 文件格式是按域名分组，例如 `ke.com`、`anjuke.com`

示例：

```json
{
  "ke.com": {
    "_updated_at": 1778912007,
    "lianjia_uuid": "...",
    "lianjia_ssid": "...",
    "hip": "..."
  },
  "anjuke.com": {
    "_updated_at": 1778910758,
    "sessid": "...",
    "id58": "..."
  }
}
```

## 平台前置

### 贝壳 `beike`

贝壳/`ke.com` 反爬较强，第一次使用或连续失败时，先做下面这一步：

1. 在浏览器中打开 <https://sh.ke.com/ershoufang/>
2. 完成滑块、人机验证或登录检查
3. 确认你看到的是正常房源列表页，而不是 `hip.ke.com/captcha` 或 `clogin.ke.com/login`
4. 刷新本地 `ke.com` cookies 后再运行 CLI

当前代码会优先请求筛选页；如果筛选页被拦，会退回到基础列表页再尝试。

### 安居客 `anjuke`

安居客/`anjuke.com` 同样依赖真实浏览器会话。

1. 在浏览器中打开 <https://shanghai.anjuke.com/sale/>
2. 完成验证码或风控校验
3. 确认你看到的是正常房源列表页，而不是 `callback.58.com/antibot/verifycode`
4. 刷新本地 `anjuke.com` cookies 后再运行 CLI

注意：

- 安居客在风控较强时，可能回退到“城市首页推荐流”而不是严格的列表筛选流
- 这时仍然能返回房源，但筛选精度可能弱于正常搜索页

## 当前平台边界

### `beike`

- 支持 `--platform beike`
- 抓取域名：`ke.com`
- 依赖 `ke.com` cookies

### `anjuke`

- 支持 `--platform anjuke`
- 抓取域名：`anjuke.com`
- 依赖 `anjuke.com` cookies

### `lianjia`

- README 中可以提到“链家语义”，但当前代码不支持 `--platform lianjia`
- 如果需要独立链家入口，需要单独实现 `lianjia` adapter

## 最小验证

建议先分别验证两个来源，而不是直接跑 `all`。

```powershell
$env:PYTHONPATH='src'
py -m house_cli.main search --platform beike --city 上海 --district 浦东 --output json
py -m house_cli.main search --platform anjuke --city 上海 --district 浦东 --output json
```

如果安居客结果为空，可以先放宽价格等过滤条件再判断是否真不可用，因为推荐流结果可能不满足严格筛选条件。

## 排障顺序

当 agent 发现“抓不到结果”时，优先按下面顺序排查：

1. 浏览器里是否已经能正常打开目标房源列表页
2. `~/.config/house-cli/cookies.json` 是否存在对应域名条目
3. cookie 是否在 7 天 TTL 内
4. 贝壳是否跳到了 `clogin.ke.com/login` 或 `hip.ke.com/captcha`
5. 安居客是否跳到了 `callback.58.com/antibot/verifycode`
6. 是否是筛选过严导致结果被客户端过滤为空
