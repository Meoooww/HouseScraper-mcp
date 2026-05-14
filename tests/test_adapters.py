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
