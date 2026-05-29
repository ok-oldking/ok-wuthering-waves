# CodeStable 共享口径

由 `cs-onboard` 复制到项目的 `.codestable/reference/shared-conventions.md`。所有 CodeStable 子技能用项目相对路径 `.codestable/reference/shared-conventions.md` 引用本文件——跨子技能共享但不适合堆在单个技能里的规范的唯一权威版本。

skill 本身不共享文件系统（每个 skill 是独立安装单元），共享口径不能放在某个 skill 内部被别的 skill 引用。放在"工作项目"里对所有 skill 都可达。

---

## 0. 目录结构与路径命名

onboard 完成后骨架（`cs-onboard` 负责搭建）：

```
.codestable/
├── attention.md           CodeStable 技能启动必读的项目注意事项
├── requirements/          能力愿景层（"用户需要什么、系统提供什么能力来满足"，过去/现在/未来）
│   ├── VISION.md           中心索引（按 status 分组，每条带 pitch 一句话）
│   └── {slug}.md           一个能力一份，扁平（cs-req 产出）
├── architecture/          架构中心目录（"用什么结构实现"，只记现状）
│   ├── ARCHITECTURE.md    总入口（索引 + 关键架构决定）
│   └── {type}-{slug}.md   子系统 / 模块 doc（cs-arch 产出）
├── roadmap/               规划层（"接下来怎么做这块大需求 + 模块怎么切 + 接口怎么定"）
│   └── {slug}/            一个大需求一个子目录（cs-roadmap 产出）
│       ├── {slug}-roadmap.md   主文档：背景 / 范围 / 模块拆分 / 接口契约 / 子 feature 清单 / 排期
│       ├── {slug}-items.yaml   机器可读子 feature 清单，acceptance 回写状态
│       └── drafts/             可选
├── features/              feature spec 聚合根
│   └── YYYY-MM-DD-{slug}/  每个 feature 一个目录
│       ├── {slug}-brainstorm.md  （可选，case 2 时产出）
│       ├── {slug}-design.md      （标准流程）
│       ├── {slug}-checklist.yaml （标准流程）
│       ├── {slug}-acceptance.md  （标准流程）
│       └── {slug}-ff-note.md     （fastforward 通道唯一产物，与上面四份互斥）
├── issues/                issue spec 聚合根
│   └── YYYY-MM-DD-{slug}/
│       ├── {slug}-report.md
│       ├── {slug}-analysis.md   （根因不显然才有）
│       └── {slug}-fix-note.md
├── refactors/             refactor spec 聚合根
│   └── YYYY-MM-DD-{slug}/
│       ├── {slug}-scan.md
│       ├── {slug}-refactor-design.md
│       ├── {slug}-checklist.yaml
│       └── {slug}-apply-notes.md
├── compound/              沉淀类文档统一目录
│   └── YYYY-MM-DD-{doc_type}-{slug}.md
│                          doc_type ∈ {learning, trick, decision, explore}
├── brainstorm/            brainstorm 阶段 spike 实验代码区（cs-brainstorm 临时产出）
│   └── {slug}/            一次 spike 一个子目录，文件名随意
│                          验完不强制清理，结论回写到对应 brainstorm note
├── tools/                 跨工作流共享脚本（onboard 从技能包释放）
└── reference/             共享参考文档（onboard 从技能包释放）
```

### 命名规则

- 需求文档：`requirements/{slug}.md`（能力愿景，不带日期前缀，扁平不分组）；中心索引 `requirements/VISION.md`
- roadmap：`roadmap/{slug}/`（不带日期前缀，平铺不嵌套）
- feature / issue / refactor 目录：带日期前缀 `YYYY-MM-DD-{slug}`
- 沉淀类：`compound/YYYY-MM-DD-{doc_type}-{slug}.md`，日期用**归档当天**
- 架构 doc：`architecture/{type}-{slug}.md`（长效，不带日期前缀）；总入口固定 `ARCHITECTURE.md`
- 项目注意事项入口固定为 `.codestable/attention.md`，所有 CodeStable 子技能启动前必须读取；不再兼容 `AGENTS.md` / `CLAUDE.md` 等外部入口

### 架构 doc 分组规则（同类聚合）

`architecture/` 下用文件名第一段作 type 标记：`ui-chat.md` 和 `ui-events.md` 同 `ui` 类。**所有架构 doc 必须 `{type}-{slug}.md`**——只有一份的也要带合理 type 段（如 `cli-entry.md`），否则未来同类出现时聚合不了。

**触发**：某 type 在 `architecture/` 根目录达到 ≥6 份时（即新加第 6 份那次），把这一类全部收进同名子目录。

**收入后**：去掉 type 前缀。`ui-chat.md` → `ui/chat.md`。

**只升不降**：删到 ≤5 份也不折回平铺。

**触发时谁负责**：`cs-arch` 的 `backfill` / `update` 模式在 Phase 6 落盘前主动检查并搬迁；命中阈值时这次操作要把"本次新加 / 改的 + 已有同类全部"一起搬，并同步改 `ARCHITECTURE.md` 链接（搬迁本身要在 Phase 5 给用户 review，不偷偷做）。`check` 模式不主动搬迁，但发现 ≥6 仍平铺时在报告末尾列为观察项。

### 改目录结构

改 `cs-onboard/reference/shared-conventions.md` 模板，新项目 onboard 时带上新版本；已有项目手动同步 `.codestable/reference/shared-conventions.md`。

---

## 1. 共享元数据口径

**feature spec**：brainstorm / design / acceptance 共用 `doc_type` / `feature` / `status` / `summary` / `tags`。子技能只补特有字段。`status`：brainstorm = `confirmed`（落盘即确认无 draft）；design = `draft` / `approved`；acceptance 见对应技能。

**issue spec**：report / analysis / fix-note 共用 `doc_type` / `issue` / `status` / `tags`。`severity` / `root_cause_type` / `path` 由对应阶段按需补。

**归档类（compound）**：

- learning / trick / decision / explore 四类**统一写入 `.codestable/compound/`**
- 每个文档 frontmatter 顶部带 `doc_type`（learning / trick / decision / explore）作跨子技能归属判定
- 文件名 `YYYY-MM-DD-{doc_type}-{slug}.md`——日期打头便于 `ls` 排序，type 段在中间便于 grep
- 各子技能在 `doc_type` 之外保留专属 frontmatter（learning 的 `track` / trick 的 `type` / decision 的 `category` / explore 的 `type`）
- 各子技能只认自己的 `doc_type` 不读写别家
- `status` 等通用字段语义和本文件保持一致

**外部读者文档**（guidedoc / libdoc）：frontmatter 由各自子技能定义。无特殊说明：`draft` = 待 review，`current` = 当前有效，`outdated` = 代码已变更待同步。

**写作约束**：子技能提字段时优先写"额外字段"或"阶段状态变化"，不重复展开整套通用字段。

---

## 2. {slug}-checklist.yaml 生命周期

- 是 feature 工作流的唯一执行清单
- 由 `cs-feat-design` 在 design 确认通过后一次生成 `steps` + `checks`
- `cs-feat-ff` **不生成** checklist（也不写 design / acceptance），是跳过 spec 流程直接写代码的超轻量通道；唯一留下的痕迹是动手后回写的 `{slug}-ff-note.md`（轻量回顾，参与 scoped-commit、可被 cs-arch / cs-req backfill 检索到）

`steps` 的粒度是 **编排-计算分离维度的切片策略**——按"先编排骨架、后计算节点、最后持久化与测试"写（最简 Workflow 先行 → 逐个节点填充），**不下沉到 file:line / 函数级**。具体改哪个文件由 implement 阶段决定。

**design 的职责**：

- 提取 `steps`（4-8 步，每步独立可验证退出信号）：后端节奏 = 编排骨架 → 计算节点逐个填 → 接通持久化 → 测试覆盖；前端 = 静态结构 → 交互逻辑 → 状态接入 → 联调收尾
- 提取 `checks`：第 1 节"明确不做"→ 范围守护；第 2.1 接口 → 名词契约；第 2.2 主流程 + 流程级约束 → 编排骨架；第 2.3 挂载点 → 挂载点；第 3 节场景清单 → 验收场景

**implement 的职责**：

- 按 `steps` 顺序执行，每步完成把 status `pending` → `done`
- 实现到具体文件级时需要拆分某步、或发现微重构是其前置（参考第 7 节反射检查）→ 跟用户对齐后追加 / 拆分 steps，**不偷偷做**
- 不改写 `checks`

**acceptance 的职责**：只更新 `checks[].status`（`pending` → `passed` / `failed`），不重写 `steps`。

**写作约束**：子技能描述 checklist 时只补本阶段读 / 写哪一部分，不重新定义生命周期。

---

## 2.5 roadmap ↔ feature 衔接协议

`.codestable/roadmap/{slug}/{slug}-items.yaml` 是规划层和 feature 执行层的唯一接口。三个技能共同读写它——是 skill 都读写项目共享产物，不算耦合。

**items.yaml 状态机**：

```
planned  → in-progress  （cs-feat-design 启动 feature 时改）
in-progress → done      （cs-feat-accept 验收完成时改）
planned  → dropped      （cs-roadmap update 模式，用户决定不做时改）
```

`done` / `dropped` 是终态。需要回退重做的新加一条 slug 略改的条目，不改终态。

**cs-roadmap 的职责**：生成和维护 roadmap 主文档 + items.yaml；把 `planned` 改 `dropped`（用户放弃时）；不改 `in-progress` / `done`（feature 技能负责）。

**cs-feat-design 的职责**（从 roadmap 起头时）：

1. design.md frontmatter 加 `roadmap: {roadmap-slug}` + `roadmap_item: {子 feature slug}`
2. items.yaml 对应条目 `status: in-progress` + `feature: YYYY-MM-DD-{slug}`
3. 校验 yaml

直接起 feature（非 roadmap 来）两字段留空，不触发 roadmap 写。

**cs-feat-accept 的职责**：

1. 读 design frontmatter `roadmap` / `roadmap_item`
2. 空 → 跳过
3. 有值 → items.yaml 对应条目 `status: done`；同步主文档子 feature 清单显示状态；校验 yaml

回写是**实际写文件的动作**，验收报告要明确记录回写结果。

**最小闭环标记**：items.yaml 每份只有一条 `minimal_loop: true`，标记"做完后系统能端到端跑通最窄路径"。design 启动 `minimal_loop` 条目时优先级最高。

---

## 3. 阶段收尾推荐

**feature-acceptance** 收尾按顺序判断：

1. `cs-learn`：沉淀经验
2. `cs-decide`：长期约束 / 选型
3. `cs-guide`：开发者 / 用户指南
4. `cs-libdoc`：公开 API 参考
5. `scoped-commit`

**issue-fix** 收尾按顺序判断：

1. `cs-learn`：坑点
2. `cs-decide`：暴露的长期约束
3. `scoped-commit`

**feature-ff** 收尾按顺序判断（比标准 acceptance 短，没有 architecture / req 回写动作）：

1. `cs-learn`：动手过程暴露的坑
2. `cs-decide`：动手过程拍板的长期约束
3. `scoped-commit`

**统一规则**：一律一句话提示；用户说"不用"立即跳过；不强制；上游主动提示，下游承接执行。

---

## 4. 收尾提交（scoped-commit）

acceptance / issue-fix 走完后把本次产物提交为一个 commit：

- **范围**：本次工作改到的代码 + 相关 spec 文档 + 本次实际更新过的架构 doc + 本次实际更新过的 roadmap items.yaml / 主文档
- **不该进**：和本次工作无关的顺手修改；属于"下次另起 feature / issue"的扩大范围
- **提交前确认**：用户没明确同意不要 `git commit`
- **commit message**：一句话说清"做了什么"，不贴 spec 目录路径

子技能只描述本阶段特有提交范围，通用规则看这里。

---

## 5. 归档检索规则

feature-design / issue-analyze / issue-fix 动手前到 `.codestable/compound/` 搜已有沉淀：

- 总是先搜 `architecture/` 和 `compound/`
- 在 `compound/` 用 `doc_type` 过滤（learning / trick / decision / explore）
- 搜到的结果只作参考输入，不盲目套用——可能已 `outdated` 或不适合当前上下文
- 搜到和当前方向冲突的 decision → **必须**正面回应"为什么仍然这么做"或调整方向

子技能只补本阶段查询命令。完整搜索语法看 `.codestable/reference/tools.md`。

---

## 6. 归档类子技能共享守护规则

`cs-learn` / `cs-trick` / `cs-decide` / `cs-explore` 共享下面这组规则。子技能正文只写特有反模式，通用看这里：

1. **只增不删**——已归档除非被明确取代（`status=superseded`）否则不删；理由丢失成本极高
2. **宁缺毋滥**——用户说不出理由的节直接省略，不要 AI 编造
3. **不替用户写实质内容**——AI 负责起草结构和串联语言，实质结论必须来自用户或可追溯的代码证据
4. **attention.md 检查**——写完后若沉淀暴露出"每次启动都该知道"的一两行硬约束，提示用户用 `cs-note` 追加到 `.codestable/attention.md`；不要直接改外部 AI 入口
5. **起草前先查重叠**——动手写前用 `search-yaml.py --query` 查语义相近的旧文档。命中就把候选列给用户在三条路径里选：
   - **更新已有**（默认优先）：沿用原文件名和原创建日期，**不新建**；frontmatter 补 `updated: YYYY-MM-DD`；超出小修在文末加"YYYY-MM-DD 更新"简述
   - **supersede**：旧文档保留原文，`status: superseded` + `superseded-by: {新文件名}`，正文顶部加 `**[已取代]** 见 {新 slug}`；新文档 frontmatter 带 `supersedes: {旧文件名}`
   - **确实是不同主题**：新建，文末"相关文档"列出已有那条说明区别
6. **识别用户意图是"改已有"还是"记新的"**——用户说"改 / 更新 / 修订 / 补充 {某条}"、明确指向某条旧文档、或话题高度重合时默认走"更新已有"，不要闷头新建。分不清就问。

各子技能只认自己的 `doc_type`，不读写别家产物。

---

## 7. 写代码时的反射检查

`cs-feat-impl` 和 `cs-issue-fix` 共用。AI 默认会往"大函数 / 大文件 / god class / 处处特殊分支"漂，这一节把漂移截在发生那一刻。

**不是阈值，是触发器**——硬数字会诱发为拆而拆把自然聚合的代码切碎。每条都是"遇到 X 情况就停下来问自己"。

| 触发场景 | 停下来问自己 |
|---|---|
| 要往一个已经很长的文件追加代码时 | 文件承担几件事？新加的是已有职责延伸还是第 N+1 件事？是第 N+1 就默认新建文件 |
| 要给已经很多方法的类加方法时 | 新方法是核心职责的自然扩展，还是把类推向"什么都能干"？ |
| 写的函数已超过一屏时 | 函数在做几件事？几件事就拆 |
| 要加 `if (特殊情况) { 特殊处理 }` 分支时 | 抽象维度选错了？正确做法可能是把特殊路径和通用路径分成不同函数 / 策略 / 类 |
| 要 copy-paste 一段代码时 | 能抽成共用还是只字面相似？能抽就抽 |
| 要给函数加第 4+ 个参数时 | 函数做的事是不是太多了？参数列表是 API 恶化的早期信号 |
| 要新写"万能工具类 / helper"时 | 真没归属还是只是想不起来放哪儿就先堆 util？ |

**停下来之后**：反射检查只把问题提出来，结论用户定。停下来想清楚的动作（拆 / 新建 / 重命名 / 抽共用）会让改动超出现有 steps 范围 → 跟用户对齐再决定（纳入当前推进 / 记顺手发现留后续）。

不许偷偷拆完继续写，也不许忽略信号硬冲。默认动作是停、问、再继续。
