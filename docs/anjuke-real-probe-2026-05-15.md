# 安居客真实参数探测报告（2026-05-15）

本报告只记录“实时抓取可验证”的事实，不使用手工猜测参数。

- 代码探测器：`src/house_cli/client/adapters/anjuke_probe.py`
- 测试：`tests/test_anjuke_real_probe.py`
- 运行日期：2026-05-15
- 城市：上海

## 1) 探测方法

1. 访问城市首页：`https://shanghai.anjuke.com/?from=AJK_Web_City`
2. 从页面真实锚点中提取 `/sale/...` 过滤链接（作为站点可接受 token 证据）
3. 调用 `AnjukeClient.search(SearchFilter(city="上海"))`，统计真实返回结果中的非空字段

说明：

- `sale` 列表页在本次会话中多次触发 geetest 风控，因此“全量过滤 token”无法稳定一次性抓全。
- 但首页可稳定抓到区县 + 总价档位 token，这些是“已实时验证可见”的参数。

## 2) 真实接受入参（已验证）

当前可验证的是“路径 token”参数，而不是 query 参数。

### 2.1 区县 token（`district_slug`）

| token | 含义 | 示例 URL |
| --- | --- | --- |
| `pudong` | 浦东 | `https://shanghai.anjuke.com/sale/pudong/` |
| `minhang` | 闵行 | `https://shanghai.anjuke.com/sale/minhang/` |
| `songjiang` | 松江 | `https://shanghai.anjuke.com/sale/songjiang/` |
| `baoshan` | 宝山 | `https://shanghai.anjuke.com/sale/baoshan/` |
| `jiading` | 嘉定 | `https://shanghai.anjuke.com/sale/jiading/` |
| `xuhui` | 徐汇 | `https://shanghai.anjuke.com/sale/xuhui/` |
| `qingpu` | 青浦 | `https://shanghai.anjuke.com/sale/qingpu/` |
| `jingan` | 静安 | `https://shanghai.anjuke.com/sale/jingan/` |
| `putuo` | 普陀 | `https://shanghai.anjuke.com/sale/putuo/` |
| `yangpu` | 杨浦 | `https://shanghai.anjuke.com/sale/yangpu/` |
| `fengxian` | 奉贤 | `https://shanghai.anjuke.com/sale/fengxian/` |
| `huangpu` | 黄浦 | `https://shanghai.anjuke.com/sale/huangpu/` |
| `hongkou` | 虹口 | `https://shanghai.anjuke.com/sale/hongkou/` |
| `changning` | 长宁 | `https://shanghai.anjuke.com/sale/changning/` |
| `jinshan` | 金山 | `https://shanghai.anjuke.com/sale/jinshan/` |
| `chongming` | 崇明 | `https://shanghai.anjuke.com/sale/chongming/` |
| `shanghaizhoubian` | 上海周边 | `https://shanghai.anjuke.com/sale/shanghaizhoubian/` |

### 2.2 总价档位 token（`price_bucket`）

| token | 含义 | 示例 URL |
| --- | --- | --- |
| `m13470` | 100万以下 | `https://shanghai.anjuke.com/sale/m13470` |
| `m13471` | 100-200万 | `https://shanghai.anjuke.com/sale/m13471` |
| `m13472` | 200-250万 | `https://shanghai.anjuke.com/sale/m13472` |
| `m13473` | 250-300万 | `https://shanghai.anjuke.com/sale/m13473` |
| `m13474` | 300-350万 | `https://shanghai.anjuke.com/sale/m13474` |
| `m13475` | 350-400万 | `https://shanghai.anjuke.com/sale/m13475` |
| `m13476` | 400-500万 | `https://shanghai.anjuke.com/sale/m13476` |
| `m13477` | 500-800万 | `https://shanghai.anjuke.com/sale/m13477` |
| `m13478` | 800-1000万 | `https://shanghai.anjuke.com/sale/m13478` |
| `m13479` | 1000万以上 | `https://shanghai.anjuke.com/sale/m13479` |

### 2.3 `sale` 页一次成功抓取中观测到的额外 token（补充证据）

在同一会话的早期请求中，`https://shanghai.anjuke.com/sale/?from=HomePage_Search` 曾成功返回完整页面（后续触发 geetest）。从该次页面锚点中额外观测到以下 token 类别：

- `area_bucket`：`a11906`..`a11915`（50㎡以下、50-60㎡...210㎡以上）
- `layout_bucket`：`b2`、`b4`、`b10`、`b11`、`b12`、`b13`（一室、二室、三室...）
- `orientation_bucket`：`l1`..`l10`（东、南、西、北、东南、东北、西南、西北、南北、东西）
- `floor_bucket`：`fl1`..`fl5`（底层、低层、中层、高层、顶层）
- `building_age_bucket`：`y1`..`y4`（2年内、2-5年、5-10年、10年以上）
- `property_type_bucket`：`t1`、`t2`、`t3`、`t4`、`t5`、`t9`、`t12`
- `property_nature_bucket`：`z1`、`z2`、`z5`、`z6`、`z782513`
- `renovation_bucket`：`d1`..`d4`（毛坯、普通装修、精装修、豪华装修）
- `feature_near_subway`：`dt1`
- `feature_verified`：`fv1`
- `feature_vr`：`v3`
- `feature_urgent`：`ls1`
- `sort_token`：`o2`（面积）、`o4`（价格）
- `page_token`：`p2`、`p3`、`p4`、`p5`、`p6`、`p50`
- `bizcircle_slug`：如 `pudong-q-lujiazui`、`xuhui-q-xujiahui`（大量）

这些 token 是“页面真实存在的可点击链接”证据；但受风控影响，建议在稳定 cookie 会话下重复抓取并生成长期快照。

## 3) 真实返回参数（已验证）

在本次实时探测中，`AnjukeClient.search()` 的返回样本数为 `8`，统计到的非空字段如下：

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

这也是当前可以稳定对外声明的“已验证返回字段”。

## 4) 当前边界

- 代码里虽然有更多“声明型参数”（如 `min_area`、`layout`、`sort_by`、`page` 等），但本报告不把它们当作“真实生效”结论。
- 需要在能稳定通过 geetest 的会话下，继续对 `/sale/` 全量筛选链接做抓取补全（户型、面积、朝向、楼层、装修、VR、排序、分页等 token）。
