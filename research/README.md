# Research Engine (v0.3)

网文市场调研引擎：发现热门小说 → 语料权利门禁 → 风格画像 → 榜单数据报告。

架构原则：**热门发现**和**正文获取**是两条独立管线。本引擎只读公开榜单元数据
（书名/作者/排名/在读数/字数/章节数/最近更新时间/简介），不抓任何正文；进入
风格分析的语料只能是开放许可、明确授权、或用户自己提供的文本，由 manifest 的
rights 字段门禁。

## 用法

仓库根目录运行：

```powershell
# 1. 轮询番茄全部 74 个板块（男频/女频 × 在读榜/新书榜 × 37 题材）
#    每板块 top10，数据落 data/novels.json + data/snapshots/ 时间戳快照
python -m research.cli discover

# 只抓单个板块（调试用）
python -m research.cli discover --board 1_2_751

# 2. 从 novels.json 生成数据报告（落 data/reports/*.md）
python -m research.cli report

# 3. 给自己有权使用的小说文本建档（默认标 user_provided）
python -m research.cli manifest <语料目录>

# 4. 提炼风格画像（落 data/style_profiles/current.json）
python -m research.cli mine <语料目录>

# 跑测试
python -m unittest discover -v
```

## 板块

板块表在 `research/sources/fanqie_boards.py`，提取自番茄榜单导航：

- 码格式 `rank/{gender}{type}_{category}`：gender 0=女频 1=男频；
  type 1=新书榜（上升期新书）2=在读榜（累计热读，含完结书）
- 男频 19 题材 + 女频 18 题材，共 74 板块
- 抓哪些由 `research/config.toml` 的 `genders` / `rank_types` 控制
- 番茄页面结构变化时只需改 `research/sources/fanqie.py` 适配器

## 报告内容

`report` 子命令产出 markdown 报告：各板块 Top3、书名风格（长度/逗号句式/
冒号/数字比例）、简介标签（【爽+双洁+系统】类）、章均字数、连载与更新节奏、
跨榜书。快照攒多期后可扩展真实日更速度与在读涨速。

## 已知限制

- 番茄页面用自定义字体反爬：抓到的书名/简介里部分字是私有区码点，显示缺字
  （记录里 `title_obfuscated: true`）。码点与原字一一对应且跨请求稳定，
  字符数/标点统计、去重、周度追踪都不受影响；完整解码需要做 woff2 字形映射，
  留待后续版本。
- 单板块一次返回 10 条。
- 热度分只在板块内部可比（不同板块量纲不同），跨板块对比请看在读中位数。

## 依赖

Python 3.11+（用到内置 tomllib），`pip install requests`。
