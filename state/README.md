# 状态账本（state/）使用说明

## 这是什么

跨章节的状态账本，解决"写到第 30 章数字兜不住、伏笔忘了、人设漂移"的问题。
它是**事实源**：人物状态、关键数字、伏笔、待兑现钩子、术语统一表都在这里。

## 两个文件

- `ledger.json` — 机器可读的事实源。Agent 写新章前必读，定稿后必更新。
- `README.md` — 本文件，人工阅读的使用说明。

## 工作流中的位置

```
写第 N 章前 → 读 ledger.json（确认人物状态、数字、未回收伏笔）
        ↓
建立章节契约（本章目标、冲突、钩子）
        ↓
初稿 → Semantic Gate → Deterministic Gate
        ↓
定稿后 → 更新 ledger.json：
  - book.current_chapter = N
  - characters：人物状态变化（受伤/位置/新获信息）
  - numbers：数字扣减（写明去向）
  - foreshadows：新增伏笔 / 标记已回收
  - hooks_pending：本章钩子入账 / 兑现旧钩子出账
  - terminology：新术语登记
```

## 字段说明

| 顶层键 | 内容 | 更新时机 |
|---|---|---|
| `book` | 书名、当前预设、时代背景、当前章节数 | 开书时填，`current_chapter` 每章更新 |
| `characters` | 关键人物：位置、伤势、已知/未知信息、持有物资、关系变化 | 人物状态变化时 |
| `numbers` | 金额、物资数量、时间线锚点；每次扣减写去向 | 数字变化时（必须写去向） |
| `foreshadows` | 伏笔：埋设章节、内容、预计回收章节、是否已回收 | 埋新伏笔 / 回收时 |
| `hooks_pending` | 待兑现钩子：内容、埋设章节、兑现期限 | 章末钩子入账 / 兑现时出账 |
| `terminology` | 术语统一表 | 新术语出现时 |

## 规则

1. **数字一旦定死，全书不许吃书**。改数字先改 ledger，再改正文。
2. **伏笔必须有预计回收章节**；fanqie_fast_pace 预设下钩子三章内必须兑现。
3. ledger.json 用 UTF-8 编码，保持合法 JSON（更新后可用 `python -m json.tool` 校验）。
4. 项目私有数据：ledger.json 建议加入 `.gitignore`（含剧透），或按项目需求决定是否进仓库。
