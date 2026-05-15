from housescraper_mcp.adapters import BeikeClient, LianjiaClient


BEIKE_HTML = """
<html>
  <body>
    <ul class="sellListContent">
      <li class="clear">
        <a href="https://sh.ke.com/ershoufang/107114117310.html" title="世茂滨江全明户型，落地窗森系景观，正南大客厅！">
          <img alt="世茂滨江全明户型，落地窗森系景观，正南大客厅！-上海浦东陆家嘴二手房">
        </a>
        <div class="info clear">
          <div class="title">
            <a>世茂滨江全明户型，落地窗森系景观，正南大客厅！</a>
            <span class="goodhouse_tag tagBlock">必看好房</span>
          </div>
          <div class="positionInfo">
            <a href="https://sh.ke.com/xiaoqu/5011000017872/">世茂滨江花园</a>
          </div>
          <div class="houseInfo">低楼层 (共43层) | 2004年 | 2室2厅 | 143.2平米 | 东 南</div>
          <div class="followInfo">268人关注 / 7月前发布</div>
          <div class="tag">
            <span class="subway">近地铁</span>
            <span class="taxfree">满五年</span>
          </div>
          <div class="priceInfo">
            <div class="totalPrice totalPrice2"><span class="">1249</span><i>万</i></div>
            <div class="unitPrice"><span>87,221元/平</span></div>
          </div>
        </div>
      </li>
    </ul>
  </body>
</html>
"""


LIANJIA_HTML = """
<html>
  <body>
    <div class="listContentLine"></div>
    <ul class="sellListContent" log-mod="list">
      <li class="clear LOGVIEWDATA LOGCLICKDATA">
        <a class="noresultRecommend img LOGCLICKDATA" href="https://sh.lianjia.com/ershoufang/107110451347.html">
          <img alt="大区聚焦两室+高区视野好+诚意出售+低总价">
        </a>
        <div class="info clear">
          <div class="title">
            <a href="https://sh.lianjia.com/ershoufang/107110451347.html">大区聚焦两室+高区视野好+诚意出售+低总价</a>
            <span class="goodhouse_tag tagBlock">必看好房</span>
          </div>
          <div class="flood">
            <div class="positionInfo">
              <a href="https://sh.lianjia.com/xiaoqu/5011000004033/">西上海御庭</a> - <a href="https://sh.lianjia.com/ershoufang/anting/">安亭</a>
            </div>
          </div>
          <div class="address">
            <div class="houseInfo">2室2厅 | 90.35平米 | 南 | 简装 | 高楼层(共23层) | 2016年 | 板楼</div>
          </div>
          <div class="followInfo">10人关注 / 一年前发布</div>
          <div class="tag">
            <span class="vr">VR房源</span>
            <span class="taxfree">房本满五年</span>
          </div>
          <div class="priceInfo">
            <div class="totalPrice totalPrice2"><i> </i><span class="">175</span><i>万</i></div>
            <div class="unitPrice" data-price="19370"><span>19,370元/平</span></div>
          </div>
        </div>
      </li>
    </ul>
  </body>
</html>
"""


KE_DETAIL_HTML = """
<html>
  <head><title>世茂滨江花园南向两房</title></head>
  <body>
    <h1 class="main">世茂滨江花园南向两房</h1>
    <span class="total">1249</span>
    <span class="unitPriceValue">87,221</span>
    <div class="communityName"><a>世茂滨江花园</a></div>
    <div class="areaName">
      <a>浦东</a>
      <a>陆家嘴</a>
    </div>
    <div class="subwayInfo">
      <a>2号线陆家嘴</a>
    </div>
    <div class="introContent">正南大客厅，落地窗森系景观。</div>
    <span class="label">房屋户型</span><span>2室2厅</span>
    <span class="label">所在楼层</span><span>低楼层</span>
    <span class="label">建筑面积</span><span>143.2平米</span>
    <span class="label">房屋朝向</span><span>东 南</span>
    <span class="label">建筑类型</span><span>塔楼</span>
    <span class="label">建成年代</span><span>2004年</span>
    <span class="label">配备电梯</span><span>有</span>
    <span class="label">物业费</span><span>6元/平/月</span>
    <span class="label">绿化率</span><span>35%</span>
    <span class="label">容积率</span><span>2.5</span>
    <span class="label">停车位</span><span>充足</span>
    <span class="estateTag">必看好房</span>
    <span class="tag">近地铁</span>
    <div>学校<a>明珠小学</a></div>
    <img data-src="https://example.com/1.jpg">
  </body>
</html>
"""


def test_beike_parser_extracts_listing_fields() -> None:
    houses = BeikeClient()._parse_list(BEIKE_HTML, "上海")

    assert len(houses) == 1
    assert houses[0].platform == "beike"
    assert houses[0].community == "世茂滨江花园"
    assert houses[0].district == "浦东"
    assert houses[0].layout == "2室2厅"
    assert houses[0].price == 1249.0


def test_lianjia_parser_extracts_listing_fields() -> None:
    houses = LianjiaClient()._parse_list(LIANJIA_HTML, "上海")

    assert len(houses) == 1
    assert houses[0].platform == "lianjia"
    assert houses[0].community == "西上海御庭"
    assert houses[0].district == "安亭"
    assert houses[0].layout == "2室2厅"
    assert houses[0].price == 175.0
    assert houses[0].unit_price == 19370.0


def test_beike_detail_parser_extracts_verification_fields() -> None:
    detail = BeikeClient()._parse_detail(KE_DETAIL_HTML, "107114117310", "sh")

    assert detail.platform == "beike"
    assert detail.title == "世茂滨江花园南向两房"
    assert detail.price == 1249.0
    assert detail.unit_price == 87221.0
    assert detail.community == "世茂滨江花园"
    assert detail.district == "浦东"
    assert detail.layout == "2室2厅"
    assert detail.url == "https://sh.ke.com/ershoufang/107114117310.html"


def test_lianjia_detail_parser_keeps_platform_and_domain() -> None:
    detail = LianjiaClient()._parse_detail(KE_DETAIL_HTML, "107110451347", "sh")

    assert detail.platform == "lianjia"
    assert detail.url == "https://sh.lianjia.com/ershoufang/107110451347.html"
