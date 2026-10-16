# webnovel-house-style · 网文写作质量控制 Skill

[![GitHub Stars](https://img.shields.io/github/stars/dongdong2023/webnovel-house-style?style=social)](https://github.com/dongdong2023/webnovel-house-style/stargazers)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![中文](https://img.shields.io/badge/lang-中文-red)](README.md)

**English**: A quality-control Agent Skill for Chinese web-novel writing and editing. It combines deterministic chapter/purity checks with semantic review rules and an explainable Style Profile mined from user-authorized reference texts. Works with Claude Code / ZCode / Codex / OpenCode.

把“怎么写、怎么查”变成 AI 的工作流：**规则 → 真人语料风格画像 → 章节契约 → 语义审查 → 程序硬检 → 回归**。目标不是追某一个 AI 检测器的分数，而是让长篇网文写作更稳定、更像目标作者/题材的真实表达。

写新章、改稿、终检时家规自动加载，不用每次把方法论重新贴一遍。

## 核心能力

- **章长硬标准**：默认每章 2000–2400 非空白字符，支持 `house-style.toml` 配置
- **正文零污染**：自动拦截 prompt、模型客套、系统提示、AI 自述、Markdown 残留等
- **英文白名单**：避免 `APP/GPS/USB/NPC` 等合法术语触发误报
- **JSON 门禁输出**：方便 Agent、CI 或其他工具消费检查结果
- **人类写作 Style Profile**：从你有权使用的参考语料提取句长、段落、对话、标点等可解释统计特征
- **章节契约**：把“这一章必须完成什么”变成写作前可检查输入
- **语义门禁规则**：重点检查 OOC、降智、推理跳步、天降信息、钩子、节奏和风格漂移
- **回归测试**：规则变化后用固定样本验证，减少“修 AI 味却误伤正常文本”
- **去AI味**：禁"不由得/忍不住/仿佛/深吸一口气"类堆砌、排比口号、模板化表达
- **正文零污染**：成稿只含小说本身——prompt 片段、模型客套（"好的，以下是…"）、系统提示、AI 自述、Markdown 残留由脚本自动扫描拦截
- **主角行为铁律（韩立式10条）**：留三手、不轻信、先算计、分散风险、闷声发财、不赌运气、提前想跑路、躲人后、利己不伤人、智商≠预知
- **只赢一点点**：每次交锋都是险胜，赢必有代价/新麻烦；连赢三章必安排一次被动
- **全员智商在线**：主角靠信息差和准备赢，不靠对手降智
- **判断必有前文依据链**：不许"她就是知道"，推理不许跳步
- **对话短、硬、藏信息**；心理只写"看到→想到→决定"三步；**章末必留钩子**
- **数字咬合**：数量、金额、时间线全书一致，术语统一
- **每章固定动作**：读梗概 → 细纲 → 初稿 → 双模型互审 → grep 验证 → 定稿 → 更新梗概
- **每周调研机制**：市场趋势 / AI 写作技巧 / 去AI味与人味写作三条线定期调研，重要结论回写家规（见 `references/调研工作流.md`，可配 agent 定时任务自动执行）

## 安装

一键安装（需 Node）：

```bash
npx skills add dongdong2023/webnovel-house-style
```

或手动克隆：

```bash
git clone https://github.com/dongdong2023/webnovel-house-style.git
```

**ZCode / Codex / OpenCode**（用户级，所有项目可用）：

```bash
mkdir -p ~/.agents/skills
cp -r webnovel-house-style ~/.agents/skills/
```

**Claude Code**：

```bash
mkdir -p ~/.claude/skills
cp -r webnovel-house-style ~/.claude/skills/
```

只想在某个项目里用，就放进 `<项目>/.agents/skills/`（或 Claude Code 的 `<项目>/.claude/skills/`）。

## 使用

装好后正常对话即可触发，比如说：

- "写第 43 章" / "续写下一章"
- "评审这一章" / "按家规终检 17-42 章"
- "把这段去AI味" / "检查章长"

章长校验也可以单独跑：

```bash
python scripts/check_chapter.py 第41章.txt            # 单文件
python scripts/check_chapter.py 章节目录/             # 整目录
python scripts/check_chapter.py . --recursive --min 2000 --max 2400
python scripts/check_chapter.py 第41章.txt --json
```

任一文件越界退出码为 1，方便接进发布前检查。

## 为什么加入 Style Profile？

简单的“去 AI 味黑名单”只能处理表层词汇。真正影响阅读感的还有句长、段落、对话比例、信息释放和节奏。当前版本先用低依赖、可解释的统计画像建立基线，不做模型训练。

```text
真人/人工优选语料 → Style Mining → Style Profile → 写作参考 → 语义审查 → 程序硬检 → 回归样本
```

> **不以“骗过某个 AI 检测器”为目标。** Style Profile 是写作质量参考，外部检测器只作为反馈信号。

## 定位：与"从零生成"型 skill 的区别

社区已有优秀的**从零生成**方案（如 [chinese-novelist-skill](https://github.com/PenglongHuang/chinese-novelist-skill)、[oh-story-claudecode](https://github.com/zenstory-ai/oh-story-claudecode)）：问答定题材 → 生成大纲 → 自动逐章写出一本新书。

本仓库解决的是另一个问题：**你已经有了自己的标准，或已经在写一本书**——需要 AI 在每次写章、改稿、终检时严格执行你的口径：章长区间、去AI味黑名单、主角行为铁律、数字一致性、正文零污染扫描。

两者不冲突：用生成型 skill 起书，用本 skill 做"改稿 + 终检 + 连载守规"。只想用本 skill 也完全可以，把你的标准填进去即可（见下方"换成你自己的家规"）。

## 换成你自己的家规

本仓库是一个起点，不是标准答案：

1. `references/检查清单.md` 里的人名和数值都是**通用化示例**——把你设定集里的数值、人物锚点、禁词填进去
2. `SKILL.md` 的硬标准按你的类型和平台口径改（章长区间、CP 线、更新节奏）
3. 结构原则：**SKILL.md 短**（核心规则，触发即加载），**references 长**（细节，按需读）

## 仓库结构

```text
├── SKILL.md
├── house-style.toml
├── references/
│   ├── 检查清单.md
│   ├── 章节契约模板.md
│   ├── 爆款趋势调研.md
│   └── 调研工作流.md
├── scripts/
│   ├── check_chapter.py
│   ├── build_style_profile.py
│   └── compare_style_profile.py
├── tests/
│   └── test_quality_tools.py
└── .github/
    └── workflows/
        └── test.yml
```

## 自定义

### `house-style.toml`

不要直接改 Python 代码来换章长或英文例外。复制/修改配置即可：

```toml
[chapter]
min_chars = 2000
max_chars = 2400

[english]
allowlist = ["APP", "GPS", "USB", "DNA", "NPC", "VIP"]
```

### 章节契约

写章前先填 `references/章节契约模板.md`，明确目标、冲突、必须发生/不能发生、角色已知/未知、关键数字和章末钩子。

## 许可

[MIT](LICENSE)
