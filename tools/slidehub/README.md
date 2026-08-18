# slidehub — P0 技术验证

回答一个问题：**能不能把一页从 A deck 抽出来放进 B deck，而它看起来还是原来那一页？**

平台方案的其余部分全部依赖这个答案，所以在写任何 UI 之前先把它测出来。

## 结论

```
fidelity   : 10/10 pages bit-identical to source  (worst layout=0, colour=0.00)
markers    : 10/10 recovered, manifest present
round-trip : deleted=1  modified=1  new=1  unchanged=7  unmatched=1
```

- **跨 deck 拼装完全无损** —— 三份主题色/字体各不相同的 deck 交错抽 10 页，渲染结果与源页逐页一致
- **回传能认出来源** —— 改字、删页、移动、剥掉标记、加新页，五种情况全部正确分类
- **不需要商业库** —— python-pptx + LibreOffice 足够

## 跑一遍

```bash
pip install -r requirements.txt          # python-pptx / Pillow / PyMuPDF
# 渲染依赖 LibreOffice Impress：
#   apt install libreoffice-impress fonts-noto-cjk

python3 samples/make_samples.py          # 造三份「各自魔改过」的样本 deck
python3 -m slidehub spike                # 端到端验证，退出码 0 表示全部通过
```

换成你自己的真实 deck：

```bash
python3 -m slidehub spike --decks /path/to/your/decks --out build/real
```

然后**用 PowerPoint 打开 `build/real/assembled.pptx` 亲眼对一遍**。
数字只负责把可疑的页圈出来，最终验收靠眼睛。

## 单步命令

```bash
python3 -m slidehub ingest deck1.pptx deck2.pptx --out build/library
python3 -m slidehub assemble --library build/library --pages A:1,C:2,B:3 --out out.pptx
python3 -m slidehub roundtrip out.pptx
python3 -m slidehub reimport --library build/library --deck returned.pptx
```

页面用 `<deck字母>:<页码>` 引用，`ingest` 会打印出来。

## 代码结构

| 模块 | 职责 |
|---|---|
| `split.py` | deck → 自包含单页 pptx（复制整包再删其他页，母版/主题零损失） |
| `assemble.py` | 单页合并成 deck。**不改页**：版式、母版、主题一起搬过去 |
| `opc.py` | OPC part 深拷贝与关系重映射。保留 part 内部 rId，否则图表会静默损坏 |
| `marker.py` | 画布外空形状，把来源 id 藏在 shape name 里 |
| `manifest.py` | deck 级导出清单，存在 customXml part 里，用于发现「回传时少了的页」 |
| `reimport.py` | 回传识别：标记 → manifest → 指纹兜底，产出决策队列 |
| `library.py` | 页索引 + 去重聚类 |
| `fingerprint.py` | 文本 / 感知 / 结构 / 媒体四类指纹 |
| `render.py` | LibreOffice → PDF → PNG |
| `verify.py` | 保真度回归：结构 + 颜色双信号 |
| `pptx_compat.py` | 绕开 python-pptx 的 `add_slide` 重名 bug |
| `simulate.py` | 模拟客户会后的真实编辑，用于验证回传 |

## 三个值得记住的坑

**1. `python-pptx` 的 `add_slide` 会生成重名 part**

它用 `len(sldIdLst) + 1` 推导 part 路径，而文档字符串写的是 "next available"。
删一页再加一页 → `slide10.xml` 撞名 → PowerPoint 报文件损坏。
「删了再加」正是这个产品最高频的操作，所以建 slide 一律走 `pptx_compat.add_slide`。

**2. 母版按页重复克隆**

每页是独立打开的文件，所以同一份源 deck 的母版会被克隆 N 次 —— 10 页产出 11 套母版。
`PartCloner` 因此按 part 的**整个可达子图**哈希去重（`_content_key`），而不是按对象身份。

只按 part 自身字节去重是不够的：三份样本 deck 的 `slideMaster1.xml` 完全相同，
只有挂在下面的 theme 不同，按字节去重会把不同品牌色的母版合并掉。
这个错误是被下面第 3 条的颜色检测抓出来的。

**3. 灰度感知哈希看不见颜色变化**

早期试过把页重挂到统一母版。图表的柱子从橙变青（图表颜色不在 slide 里，在独立的
chart part 中靠目标主题推导），而 dhash 给出的距离只有 2 —— **判定通过**。
保真度检测因此必须带一个颜色维度的信号，见 `fingerprint.color_signature`。

## 这只是验证工具

不是产品代码。索引是一个 JSON 文件而不是数据库，没有并发控制、没有权限、没有 UI。
字段命名刻意与正式实现保持一致，方便平移。
