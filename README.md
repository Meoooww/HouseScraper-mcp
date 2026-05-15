# HouseScraper 

用于聚合检索房源，支持 `lianjia`、`anjuke`。
贝壳和链家使用的是同一套核心数据源，贝壳多一点，可以不额外处理贝壳（反爬，但功能支持）
基于 https://github.com/Luxuzhou/house-cli 二次开发

## 贝壳 `beike` 使用前置

贝壳/`ke.com` 有较强的反爬策略。即使本地已经有 `~/.config/house-cli/cookies.json`，如果其中缓存的是旧会话，CLI 仍然可能直接跳到 CAPTCHA 页面并报失败。

当你第一次使用 `beike`，或连续遇到 `ke.com returned CAPTCHA` 时，先做下面这一步：

1. 在浏览器中打开 [https://sh.ke.com/ershoufang/](https://sh.ke.com/ershoufang/)。
2. 完成滑块或人机验证，直到你能正常看到房源列表页。
3. 刷新本地缓存的 `ke.com` cookie，再重新运行 CLI。

可以直接用下面的命令把浏览器里的最新 `ke.com` cookie 写回 `~/.config/house-cli/cookies.json`：

```bash
PYTHONPATH=src .venv/bin/python - <<'PY'
from house_cli.client.auth import _try_browser_cookie3, save_cookies

cookies = _try_browser_cookie3("ke.com")
if not cookies:
    raise SystemExit("No ke.com browser cookies found")

save_cookies("ke.com", cookies)
print("Saved latest ke.com cookies")
PY
```

完成这一步后，再执行例如：

```bash
PYTHONPATH=src .venv/bin/python -m house_cli.main search --platform beike --city 上海 --output json
```

本地实测中，先完成浏览器验证并刷新 `ke.com` cookie 后，贝壳搜索可以恢复正常返回结果。

