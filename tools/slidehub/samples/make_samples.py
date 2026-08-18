"""Generate three sample decks that deliberately drifted apart.

The point is not to look pretty — it is to exercise everything that breaks when
a slide is lifted out of one deck and dropped into another:

  * theme-relative colour (schemeClr accent1) and theme fonts (+mj-lt / +mn-lt)
  * title/body placeholders whose position is inherited, not stated
  * pictures, tables, native charts, grouped shapes
  * a slide-level gradient background

Each deck gets its own colour scheme and font pair, standing in for "everyone's
copy drifted". If assembly is faithful, a page must look identical after the move
even though its master no longer travels with it.
"""
from __future__ import annotations

import io
import shutil
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.util import Emu, Inches, Pt

HERE = Path(__file__).resolve().parent
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"

THEMES = {
    "A": dict(accent1="0E747E", accent2="17A2AF", dk2="123039", lt2="E4F1F2",
              major="Georgia", minor="Trebuchet MS"),
    "B": dict(accent1="C2571A", accent2="E08A3C", dk2="3A2411", lt2="F7EADF",
              major="Palatino Linotype", minor="Verdana"),
    "C": dict(accent1="5B3E90", accent2="8A6DBF", dk2="2A1C45", lt2="EDE7F5",
              major="Times New Roman", minor="Tahoma"),
}


def _swatch(path: Path, color: tuple, label: str) -> Path:
    """A deterministic stand-in for a client logo or photo."""
    img = Image.new("RGB", (640, 400), color)
    d = ImageDraw.Draw(img)
    for i in range(0, 640, 40):
        d.line([(i, 0), (i - 200, 400)], fill=tuple(min(255, c + 24) for c in color), width=9)
    d.rectangle([40, 40, 600, 360], outline="white", width=5)
    d.text((70, 70), label, fill="white")
    img.save(path)
    return path


def _retheme(pptx_path: Path, spec: dict) -> None:
    """Rewrite theme1.xml so each deck carries a genuinely different palette."""
    with zipfile.ZipFile(pptx_path) as zf:
        items = {n: zf.read(n) for n in zf.namelist()}

    theme_name = next(n for n in items if n.startswith("ppt/theme/theme") and n.endswith(".xml"))
    xml = items[theme_name].decode("utf-8")
    import re

    def set_slot(slot: str, value: str, text: str) -> str:
        return re.sub(
            r'(<a:%s>)\s*<a:(?:srgbClr|sysClr)[^/]*/>' % slot,
            r'\1<a:srgbClr val="%s"/>' % value, text, count=1)

    for slot in ("accent1", "accent2", "dk2", "lt2"):
        xml = set_slot(slot, spec[slot], xml)
    xml = re.sub(r'(<a:majorFont>\s*<a:latin typeface=")[^"]*',
                 r'\g<1>%s' % spec["major"], xml, count=1)
    xml = re.sub(r'(<a:minorFont>\s*<a:latin typeface=")[^"]*',
                 r'\g<1>%s' % spec["minor"], xml, count=1)
    items[theme_name] = xml.encode("utf-8")

    tmp = pptx_path.with_suffix(".tmp.pptx")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in items.items():
            zf.writestr(name, data)
    shutil.move(tmp, pptx_path)


def _title_body(prs, title: str, bullets: list[str]):
    """Uses the built-in Title and Content layout so geometry is *inherited* —
    the case that breaks when a slide changes master."""
    slide = prs.slides.add_slide(prs.slide_layouts[1])
    slide.shapes.title.text = title
    body = slide.placeholders[1].text_frame
    body.text = bullets[0]
    for b in bullets[1:]:
        body.add_paragraph().text = b
    return slide


def _accent_band(slide, prs, text: str):
    """A bar filled with schemeClr accent1 — recolours silently on a new master
    unless the colour is baked."""
    band = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.6), prs.slide_height - Inches(1.35),
        prs.slide_width - Inches(1.2), Inches(0.7))
    band.fill.solid()
    band.fill.fore_color.theme_color = 5  # MSO_THEME_COLOR.ACCENT_1
    band.line.fill.background()
    tf = band.text_frame
    tf.text = text
    tf.paragraphs[0].alignment = PP_ALIGN.CENTER
    tf.paragraphs[0].runs[0].font.size = Pt(14)
    tf.paragraphs[0].runs[0].font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
    return band


def _gradient_bg(slide, c1: str, c2: str):
    from lxml import etree
    from pptx.oxml.ns import qn
    cSld = slide._element.find(qn("p:cSld"))
    bg = etree.SubElement(cSld, qn("p:bg"))
    cSld.remove(bg)
    cSld.insert(0, bg)
    bgPr = etree.SubElement(bg, qn("p:bgPr"))
    grad = etree.SubElement(bgPr, qn("a:gradFill"))
    lst = etree.SubElement(grad, qn("a:gsLst"))
    for pos, color in ((0, c1), (100000, c2)):
        gs = etree.SubElement(lst, qn("a:gs"))
        gs.set("pos", str(pos))
        srgb = etree.SubElement(gs, qn("a:srgbClr"))
        srgb.set("val", color)
    lin = etree.SubElement(grad, qn("a:lin"))
    lin.set("ang", "5400000")
    etree.SubElement(bgPr, qn("a:effectLst"))


def build_deck_a(out: Path, media: Path) -> None:
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)

    cover = prs.slides.add_slide(prs.slide_layouts[0])
    cover.shapes.title.text = "灵石整合传播  ·  公司介绍"
    cover.placeholders[1].text = "2025 年度对外提案通用版"
    _gradient_bg(cover, "0E747E", "07343A")
    for ph in cover.placeholders:
        for para in ph.text_frame.paragraphs:
            for run in para.runs:
                run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)

    s = _title_body(prs, "我们是谁", [
        "成立于 2013 年，总部上海，北京 / 深圳 / 新加坡设有办公室",
        "全案整合传播：媒体关系、内容营销、活动、危机管理",
        "服务超过 180 个品牌，年度媒体发稿量逾 12,000 篇",
    ])
    _accent_band(s, prs, "一句话定位：把品牌的专业能力，翻译成媒体愿意写的故事")

    s = prs.slides.add_slide(prs.slide_layouts[5])
    s.shapes.title.text = "全国办公网络与团队规模"
    s.shapes.add_picture(str(_swatch(media / "a_office.png", (14, 116, 126), "OFFICE")),
                         Inches(0.8), Inches(1.8), width=Inches(5.4))
    tbl = s.shapes.add_table(4, 3, Inches(6.7), Inches(1.8), Inches(5.8), Inches(2.6)).table
    for c, head in enumerate(["城市", "团队规模", "成立年份"]):
        tbl.cell(0, c).text = head
    for r, row in enumerate([["上海", "68 人", "2013"], ["北京", "41 人", "2015"],
                             ["深圳", "22 人", "2019"]], start=1):
        for c, val in enumerate(row):
            tbl.cell(r, c).text = val

    s = prs.slides.add_slide(prs.slide_layouts[5])
    s.shapes.title.text = "发展里程碑"
    for i, (year, label) in enumerate([("2013", "创立"), ("2017", "北京落地"),
                                       ("2021", "出海业务"), ("2025", "AI 传播实验室")]):
        x = Inches(0.9 + i * 3.05)
        box = s.shapes.add_shape(MSO_SHAPE.CHEVRON, x, Inches(3.0), Inches(2.9), Inches(1.2))
        box.fill.solid()
        box.fill.fore_color.theme_color = 5
        box.line.fill.background()
        box.text_frame.text = "%s  %s" % (year, label)
        box.text_frame.paragraphs[0].runs[0].font.size = Pt(13)
    prs.save(str(out))


def build_deck_b(out: Path, media: Path) -> None:
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)

    cover = prs.slides.add_slide(prs.slide_layouts[0])
    cover.shapes.title.text = "服务能力总览"
    cover.placeholders[1].text = "媒体关系 / 内容营销 / 活动 / 危机管理"

    s = _title_body(prs, "媒体关系服务", [
        "常年媒体沟通与关系维护，覆盖财经、科技、消费三大条线",
        "重大节点新闻稿撰写、发布与追踪",
        "媒体专访安排与发言人陪访",
    ])
    _accent_band(s, prs, "平均每个客户年度触达记者 240+ 人次")

    s = prs.slides.add_slide(prs.slide_layouts[5])
    s.shapes.title.text = "内容营销：产出结构与配比"
    data = CategoryChartData()
    data.categories = ["深度稿", "短资讯", "视频脚本", "社媒图文", "白皮书"]
    data.add_series("年度产出占比", (28, 34, 12, 20, 6))
    s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(1.0), Inches(1.7),
                       Inches(11.3), Inches(4.6), data)

    s = prs.slides.add_slide(prs.slide_layouts[5])
    s.shapes.title.text = "危机管理响应机制"
    s.shapes.add_picture(str(_swatch(media / "b_crisis.png", (194, 87, 26), "CRISIS")),
                         Inches(7.4), Inches(1.9), width=Inches(5.1))
    tf = s.shapes.add_textbox(Inches(0.9), Inches(1.9), Inches(6.1), Inches(4.0)).text_frame
    tf.word_wrap = True
    tf.text = "四级响应分级"
    for line in ["L1 舆情监测：7×24 小时关键词监控",
                 "L2 预警研判：2 小时内出具研判简报",
                 "L3 应对执行：统一口径 + 媒体沟通",
                 "L4 复盘沉淀：形成案例入库"]:
        p = tf.add_paragraph()
        p.text = line
        p.level = 1
    prs.save(str(out))


def build_deck_c(out: Path, media: Path) -> None:
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)

    cover = prs.slides.add_slide(prs.slide_layouts[0])
    cover.shapes.title.text = "行业服务案例集"
    cover.placeholders[1].text = "汽车 · 消费电子 · 美妆"

    for name, industry, color, nums in [
        ("某新能源汽车品牌", "汽车", (91, 62, 144), [("发稿量", "1,240 篇"), ("头部媒体覆盖", "86%"), ("声量增幅", "+173%")]),
        ("某国产消费电子品牌", "消费电子", (70, 90, 160), [("发稿量", "870 篇"), ("测评覆盖", "52 家"), ("互动量", "410 万")]),
    ]:
        s = prs.slides.add_slide(prs.slide_layouts[5])
        s.shapes.title.text = "%s ｜ %s行业" % (name, industry)
        s.shapes.add_picture(str(_swatch(media / ("c_%s.png" % industry), color, industry.upper())),
                             Inches(0.9), Inches(1.9), width=Inches(5.0))
        for i, (label, value) in enumerate(nums):
            card = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                                      Inches(6.5), Inches(1.9 + i * 1.45),
                                      Inches(5.9), Inches(1.2))
            card.fill.solid()
            card.fill.fore_color.theme_color = 6  # ACCENT_2
            card.line.fill.background()
            tf = card.text_frame
            tf.text = "%s   %s" % (label, value)
            tf.paragraphs[0].runs[0].font.size = Pt(16)
            tf.paragraphs[0].runs[0].font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)

    s = _title_body(prs, "美妆行业方法论", [
        "以成分科普切入，建立专业可信度",
        "KOL 分层：头部造势 / 腰部种草 / 素人口碑",
        "大促节点前 6 周启动预热",
    ])
    _accent_band(s, prs, "该方法论已在 11 个美妆客户上复用")
    prs.save(str(out))


def main() -> None:
    out_dir = HERE / "decks"
    media = HERE / "_media"
    for d in (out_dir, media):
        d.mkdir(parents=True, exist_ok=True)

    specs = [("deck_A_公司介绍.pptx", build_deck_a, "A"),
             ("deck_B_公司服务.pptx", build_deck_b, "B"),
             ("deck_C_行业案例.pptx", build_deck_c, "C")]
    for filename, builder, theme_key in specs:
        path = out_dir / filename
        builder(path, media)
        _retheme(path, THEMES[theme_key])
        print("built %s (theme %s: accent1=#%s, fonts=%s/%s)"
              % (filename, theme_key, THEMES[theme_key]["accent1"],
                 THEMES[theme_key]["major"], THEMES[theme_key]["minor"]))


if __name__ == "__main__":
    main()
