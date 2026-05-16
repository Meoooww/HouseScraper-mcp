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

cookie 策略见 `src/house_cli/client/auth.py`：

1. CLI 只读取 `~/.config/house-cli/cookies.json`
2. 不再自动读取 Chrome / Edge / Firefox 的本地 cookie 数据库
3. 需要刷新 cookie 时，先用带 DevTools 端口的真实浏览器完成验证，再运行 `refresh-cookies`

不再使用浏览器数据库自动提取的原因：

- Windows/Edge 上 cookie DB 经常被后台进程锁住
- 新版 Chromium cookie 加密可能导致 `browser_cookie3` 无法解密登录 cookie
- 自动提取失败容易让 agent 误以为已经拿到有效登录态

贝壳推荐刷新方式：

```powershell
Start-Process -FilePath 'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe' -ArgumentList @('--remote-debugging-port=9222','--remote-allow-origins=*','https://zh.ke.com/ershoufang/ba40ea70l2co41/')

# 在浏览器里完成登录/滑块/人机验证，确认筛选页显示正常房源列表后：
$env:PYTHONPATH='src'
py -m house_cli.main refresh-cookies --domain ke.com
```

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
    "lianjia_token": "...",
    "lianjia_token_secure": "...",
    "security_ticket": "..."
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

1. 用带 DevTools 端口的浏览器打开目标筛选 URL，而不是只打开基础列表页
2. 完成滑块、人机验证或登录检查
3. 确认你看到的是正常房源列表页，而不是 `hip.ke.com/captcha` 或 `clogin.ke.com/login`
4. 运行 `py -m house_cli.main refresh-cookies --domain ke.com`
5. 再运行 CLI 搜索

当前代码会请求严格筛选页；如果筛选页被拦，会直接报错，不会静默回退到基础列表页。这样可以避免把“未筛选结果”误当成筛选流结果。

### 安居客 `anjuke`

安居客/`anjuke.com` 同样依赖真实浏览器会话。

1. 在浏览器中打开 <https://shanghai.anjuke.com/sale/>
2. 完成验证码或风控校验
3. 确认你看到的是正常房源列表页，而不是 `callback.58.com/antibot/verifycode`
4. 刷新本地 `anjuke.com` cookies 后再运行 CLI

注意：

- `--anjuke-flow search` / `--anjuke-flow auto` 不会静默回退到推荐流
- 若搜索流被风控拦截，会直接报错并提示刷新 cookies
- 只有显式使用 `--anjuke-flow recommend` 才会走城市首页推荐流
- 城市解析不再依赖内置白名单，运行时会从 `https://www.anjuke.com/sy-city.html` 动态解析城市 slug

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

贝壳详情页需要城市参数，避免落到默认城市域名：

```powershell
py -m house_cli.main detail beike:105122339790 --city 珠海 --output json
```

## 排障顺序

当 agent 发现“抓不到结果”时，优先按下面顺序排查：

1. 浏览器里是否已经能正常打开目标房源列表页
2. `~/.config/house-cli/cookies.json` 是否存在对应域名条目
3. cookie 是否在 7 天 TTL 内，且贝壳是否包含 `lianjia_token`、`lianjia_token_secure`、`security_ticket`
4. 贝壳是否跳到了 `clogin.ke.com/login` 或 `hip.ke.com/captcha`
5. 安居客是否跳到了 `callback.58.com/antibot/verifycode`
6. 贝壳命令报 strict filter URL blocked 时，重新用 DevTools 浏览器打开同一个筛选 URL 并运行 `refresh-cookies`
7. 是否是筛选过严导致结果被客户端过滤为空
