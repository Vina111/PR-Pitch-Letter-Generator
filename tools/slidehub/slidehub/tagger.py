"""Auto-tag a page from its own text.

The source decks carry a full text layer, and the text is unusually explicit:
pages name their client, their year, the trade show, the market and the service
delivered. So tagging is dictionary matching over that text, not a model call.

That choice is deliberate rather than merely cheap. Case pages carry client names
and commercial results, so keeping classification on the machine avoids sending
confidential material anywhere; the rules are auditable, so a wrong tag is a
dictionary entry to fix rather than a prompt to re-tune; and results are stable,
so re-running never quietly reshuffles a reviewed library.

Everything here is a *proposal*. Confidence is reported per field so review can
start with the weakest pages.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# --------------------------------------------------------------------------- #
#  Controlled vocabularies, built from the material itself.
#  Each entry: canonical value -> the surface forms that imply it.
# --------------------------------------------------------------------------- #
REGION = {
    "北美": ["北美", "美国", "美国市场", "纽约", "硅谷", "洛杉矶", "拉斯维加斯", "加州",
             "伊利诺伊", "威斯康星", "达拉斯", "芝加哥", "尔湾", "橙县", "US ", "U.S.",
             "USA", "American", "北美市场"],
    "加拿大": ["加拿大", "多伦多", "Canada"],
    "欧洲": ["欧洲", "德国", "法国", "巴黎", "柏林", "西班牙", "意大利", "英国", "伦敦",
             "大英图书馆", "慕尼黑", "Europe", "European", "达沃斯", "瑞士"],
    "中东": ["中东", "沙特", "迪拜", "海湾", "阿联酋", "Middle East"],
    "东南亚": ["东南亚", "新加坡", "马来西亚", "印尼", "泰国", "越南"],
    "日韩": ["日本", "韩国", "东京", "首尔"],
    "非洲": ["非洲", "坦桑尼亚", "多多马", "Africa"],
    "澳洲": ["澳洲", "澳大利亚", "悉尼", "Australia"],
    "南美": ["南美", "巴西", "拉美"],
    "中国": ["中国市场", "深圳", "杭州", "宁波", "上海", "北京"],
    "全球": ["全球", "国际市场", "海外市场", "全球市场", "五大洲", "Global"],
}

INDUSTRY = {
    "AI与大模型": ["大模型", "AI模型", "开源模型", "AIGC", "混元", "生成式", "算力",
                   "LLM", "AI软件", "AI 软件", "PixVerse", "Tripo", "盛大"],
    "机器人": ["机器人", "外骨骼", "扫雪机", "割草机", "发球机", "具身智能", "Robot",
               "SenseRobot", "Hengbot", "PONGBOT", "AIRSEEKERS", "Yarbo", "Artly"],
    "AR/AI眼镜": ["眼镜", "AR", "XR", "智能穿戴", "RayNeo", "雷鸟", "INMO", "INAIR",
                  "Rokid", "Even G1", "戒指"],
    "消费电子与智能硬件": ["消费电子", "智能硬件", "数位板", "耳机", "音频", "充电",
                          "移动电源", "倍思", "追觅", "Dreame", "ugee", "Vocci", "UREVO"],
    "新能源与储能": ["储能", "电池", "锂电", "光伏", "绿能", "新能源", "充电桩", "光储充",
                     "清洁能源", "隆基", "LONGi", "REPT", "宁德", "新能安", "Ampace",
                     "中创新航", "CALB", "国轩", "Gotion", "科陆", "EcoFlow", "协鑫"],
    "汽车与出行": ["汽车", "出行", "电动车", "滑板车", "整车", "NAVEE", "九号公司",
                   "Kosmera", "元戎", "速腾"],
    "家电与家居": ["家居", "家电", "空调", "洗碗机", "厨卫", "顾家", "KUKA", "方太",
                   "FOTILE", "美的", "Midea", "TCL", "金牌家居", "照明", "睡眠", "床垫"],
    "医疗与生物科技": ["医疗", "生物", "皮肤科", "临床", "复宏汉霖", "华熙生物", "透明质酸",
                       "Nuon", "美容科技", "SleepScore"],
    # "融资" is excluded on purpose: it describes a *moment* in a case
    # (a funding round) and appears across every industry, so matching it here
    # labelled AI and robotics cases as finance.
    "金融": ["金融", "Fintech", "投资者关系", "银行", "支付", "保险"],
    "母婴与个护": ["母婴", "吸奶器", "哺乳", "Momcozy", "个护", "脱毛", "Ulike"],
    "宠物": ["宠物", "Noesis", "Pet"],
    "餐饮与食品": ["餐饮", "中餐", "美食", "MenuSifu", "POS"],
    "工业与B2B": ["工业", "B2B", "制造", "建厂", "工程机械", "临工", "Red Sky", "RSL"],
    "文化与内容": ["阅文", "图书馆", "文学", "IP", "时装周"],
}

SERVICE = {
    "展会传播": ["展会", "参展", "展台", "首秀", "CES", "IFA", "MWC", "GTC", "RE+",
                 "GDC", "KBIS", "IBSE", "SLEEP", "NRA", "ees Europe", "SCC77", "WEF",
                 "COP28", "达沃斯", "探展"],
    "媒体活动与发布会": ["发布会", "媒体活动", "沟通会", "体验会", "快闪", "Global Connect",
                         "ShowStoppers", "媒体沟通会", "开业", "启动"],
    "媒体关系与Pitch": ["媒体关系", "Pitch", "邀约", "媒体库", "记者", "专访", "深访",
                        "独家", "外媒", "媒体名单", "建联"],
    "新闻稿与通稿发布": ["新闻稿", "通稿", "官宣", "发布稿", "转载"],
    "KOL与达人": ["KOL", "达人", "网红", "红人", "Influencer"],
    "社交媒体运维": ["社交媒体", "社媒", "LinkedIn", "领英", "Reddit", "Glassdoor",
                     "X平台", "X 平台", "Facebook", "Twitter", "账号运维", "运维"],
    "内容与物料制作": ["内容", "物料", "宣传册", "官网", "Blog", "白皮书", "话术",
                       "品牌资料包", "内容基建", "本地化内容"],
    "视频与拍摄": ["拍摄", "剪辑", "视频", "宣传片", "电视台", "TV", "栏目"],
    "危机与舆情": ["危机", "舆情", "监测", "敏感点", "问答准备", "防御"],
    "品牌本地化基建": ["本地化基建", "品牌定位", "信息架构", "5R", "本土化", "从0到1",
                       "从0 到1"],
    "CSR与公共事务": ["CSR", "捐赠", "公益", "NGO", "联合国", "UNDP", "总领馆", "政府"],
    "雇主品牌与招聘": ["雇主品牌", "招聘", "人才", "员工故事"],
    "培训与咨询": ["培训", "内训", "咨询", "陪跑", "美讯学院", "课程", "研讨会", "Webinar"],
    "调研": ["调研", "Focus Group", "用户调研", "市场调研", "竞品分析"],
}

EVENT = {
    "CES": ["CES"], "IFA": ["IFA"], "MWC": ["MWC"], "NVIDIA GTC": ["GTC"],
    "RE+": ["RE+"], "GDC": ["GDC"], "KBIS": ["KBIS"], "IBSE": ["IBSE"],
    "SLEEP": ["SLEEP 2", "SLEEP2", "SLEEP 会议"], "NRA": ["NRA"],
    "ees Europe": ["ees Europe"], "WEF 达沃斯": ["WEF", "达沃斯"],
    "COP28": ["COP28"], "AAD 皮肤科年会": ["AAD", "皮肤科医生年会"],
    "Amazon Prime Day": ["Prime Day"], "Global Connect Show": ["Global Connect"],
    "SCC77": ["SCC77"],
}

# Client names worth recognising directly; the rest are proposed by heuristic.
CLIENT = [
    "道通", "AUTEL", "协鑫能科", "REPT", "瑞浦兰钧", "隆基", "LONGi", "国轩高科", "Gotion",
    "能链", "科陆", "CLOU", "新能安", "Ampace", "中创新航", "CALB", "Jackery", "EcoFlow",
    "九号公司", "NAVEE", "Dreame", "追觅", "Mova", "倍思", "Ulike", "ugee", "UREVO",
    "Dream Valley", "Vocci", "Kosmera", "Nuon Medical", "方太", "FOTILE", "Yarbo",
    "美的", "Midea", "KUKA", "顾家", "TCL", "复宏汉霖", "Red Sky", "华熙生物", "MenuSifu",
    "金牌家居", "阅文", "临工", "腾讯", "混元", "Hunyuan", "PixVerse", "Tripo", "Artly",
    "Hengbot", "SenseRobot", "Ascentiz", "PONGBOT", "AIRSEEKERS", "Noesis", "Rokid",
    "INMO", "INAIR", "RayNeo", "雷鸟", "Even Realities", "Momcozy", "Poposoap",
    "LiveLarge", "Keenray", "Bondee", "Shoplazza", "Nori", "xLean", "ROPET", "万勋",
    "Wisson", "盛大", "熊猫安安", "华星", "CSOT", "海贝丽致", "Gyges",
]

SECTION_MARKER = re.compile(r"^\s*(\d{2})\s+(.{2,30}?)\s*$")
YEAR = re.compile(r"(20[12]\d)\s*年?")


@dataclass
class Tags:
    year: str = ""
    years: list[str] = field(default_factory=list)
    regions: list[str] = field(default_factory=list)
    industries: list[str] = field(default_factory=list)
    services: list[str] = field(default_factory=list)
    events: list[str] = field(default_factory=list)
    clients: list[str] = field(default_factory=list)
    page_type: str = "content"
    confidence: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "year": self.year, "years": self.years, "regions": self.regions,
            "industries": self.industries, "services": self.services,
            "events": self.events, "clients": self.clients,
            "page_type": self.page_type, "confidence": self.confidence,
        }


def _hits(text: str, vocab: dict) -> list[tuple[str, int]]:
    scored = []
    for canonical, surfaces in vocab.items():
        n = sum(text.count(s) for s in surfaces)
        if n:
            scored.append((canonical, n))
    scored.sort(key=lambda kv: (-kv[1], kv[0]))
    return scored


def _confidence(scored: list, taken: int) -> float:
    """Strong when the winner clearly leads; weak when everything ties at one
    mention. Review queues sort on this."""
    if not scored:
        return 0.0
    top = scored[0][1]
    if top >= 3:
        return 0.9
    if top == 2:
        return 0.7
    return 0.45 if taken == 1 else 0.35


def classify_page_type(title: str, text: str, word_count: int,
                       image_count: int, is_first: bool, is_last: bool) -> str:
    t = (title or "").strip()
    if is_first:
        return "封面"
    if is_last and ("愿与您" in text or "谢谢" in text or "Thank" in text):
        return "封底"
    if t.startswith("目录") or "Index" in t:
        return "目录"
    if SECTION_MARKER.match(t) or (word_count < 14 and len(t) < 24 and image_count <= 2):
        return "过渡页"
    if "策略STRATEGY" in t or t.strip() in ("策略STRATEGY", "成果RESULT"):
        return "正文续页"
    return "正文"


def tag_page(text: str, title: str = "", word_count: int = 0,
             image_count: int = 0, is_first: bool = False,
             is_last: bool = False, doc_year_hint: str = "") -> Tags:
    blob = "%s\n%s" % (title, text)

    years = sorted(set(YEAR.findall(blob)))
    region_hits = _hits(blob, REGION)
    industry_hits = _hits(blob, INDUSTRY)
    service_hits = _hits(blob, SERVICE)
    event_hits = _hits(blob, EVENT)

    # "全球" is a fallback, not a competitor: drop it when a real market is named.
    named_regions = [r for r, _ in region_hits if r != "全球"][:2]
    regions = named_regions or [r for r, _ in region_hits][:1]

    industries = [i for i, _ in industry_hits][:2]
    services = [s for s, _ in service_hits][:3]
    events = [e for e, _ in event_hits][:2]
    clients = [c for c in CLIENT if c in blob][:3]

    page_type = classify_page_type(title, text, word_count, image_count,
                                   is_first, is_last)
    if page_type in ("封面", "封底", "目录", "过渡页"):
        # Structural pages have no case behind them. Whatever industry or client
        # their text brushes against is incidental, and letting it through
        # pollutes every facet count in the library.
        industries, clients, events = [], [], []
        regions = [r for r in regions if r == "全球"]

    tags = Tags(
        year=(years[-1] if years else doc_year_hint),
        years=years, regions=regions, industries=industries,
        services=services, events=events, clients=clients,
        page_type=page_type,
    )
    tags.confidence = {
        "year": 0.9 if years else (0.3 if doc_year_hint else 0.0),
        "region": _confidence(region_hits, len(regions)),
        "industry": _confidence(industry_hits, len(industries)),
        "service": _confidence(service_hits, len(services)),
        "client": 0.9 if clients else 0.0,
    }
    return tags


def weakest_fields(tags: Tags, threshold: float = 0.5) -> list[str]:
    """Which fields a reviewer should look at first."""
    return sorted(k for k, v in tags.confidence.items() if v < threshold)
