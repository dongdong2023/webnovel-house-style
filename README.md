# webnovel-house-style · 网文写作家规 Skill

把"怎么写、怎么查"变成 AI 的肌肉记忆——一套经过 40+ 章连载实战检验的中文网文写作/修订/评审标准，打包成 coding agent 的 skill（Claude Code / ZCode / Codex / OpenCode 等通用）。

写新章、改稿、终检时家规自动加载，不用每次把方法论重新贴一遍。

## 家规内容

- **章长硬标准**：每章 2000–2400 非空白字符（含标题），附自动校验脚本，不靠目测
- **去AI味**：禁"不由得/忍不住/仿佛/深吸一口气"类堆砌、排比口号、模板化表达
- **主角行为铁律（韩立式10条）**：留三手、不轻信、先算计、分散风险、闷声发财、不赌运气、提前想跑路、躲人后、利己不伤人、智商≠预知
- **只赢一点点**：每次交锋都是险胜，赢必有代价/新麻烦；连赢三章必安排一次被动
- **全员智商在线**：主角靠信息差和准备赢，不靠对手降智
- **判断必有前文依据链**：不许"她就是知道"，推理不许跳步
- **对话短、硬、藏信息**；心理只写"看到→想到→决定"三步；**章末必留钩子**
- **数字咬合**：数量、金额、时间线全书一致，术语统一
- **每章固定动作**：读梗概 → 细纲 → 初稿 → 双模型互审 → grep 验证 → 定稿 → 更新梗概
- **每周调研机制**：市场趋势 / AI 写作技巧 / 去AI味与人味写作三条线定期调研，重要结论回写家规（见 `references/调研工作流.md`，可配 agent 定时任务自动执行）

## 安装

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
```

任一文件越界退出码为 1，方便接进发布前检查。

## 换成你自己的家规

本仓库是一个起点，不是标准答案：

1. `references/检查清单.md` 里的人名和数值都是**通用化示例**——把你设定集里的数值、人物锚点、禁词填进去
2. `SKILL.md` 的硬标准按你的类型和平台口径改（章长区间、CP 线、更新节奏）
3. 结构原则：**SKILL.md 短**（核心规则，触发即加载），**references 长**（细节，按需读）

## 仓库结构

```text
├── SKILL.md                  # 家规正文（核心规则 + 工作流）
├── references/
│   ├── 检查清单.md            # 7大类逐项检查清单 + grep 验证模板
│   ├── 爆款趋势调研.md        # 女频末世/囤货题材趋势与套用方法
│   └── 调研工作流.md          # 每周调研手册（三线调研 + 归档回写规则）
└── scripts/
    └── check_chapter.py      # 章长校验（非空白字符计数）
```

## 许可

[MIT](LICENSE)
