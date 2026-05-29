# CodeStable 维护者说明

本文件由 `cs-onboard` 复制到项目的 `.codestable/reference/maintainer-notes.md`。维护 CodeStable 技能家族时需要反复查阅、但不适合放在各子技能正文里的说明。

---

## 1. 断点恢复

AI 对话随时可能中断（token 超限、网络断开、用户换设备）。各阶段发现自己不是从零开始时，必须优先检查已有产物的完成度，从上次停下的地方继续：

- **brainstorm**：如 `{slug}-brainstorm.md` 已有部分内容，读取后问用户"上次聊到 X，要接着聊还是推翻重来？"
- **design**：如 `{slug}-design.md` 已有部分节，逐节检查完成度，补齐缺失节，不重写已完成节
- **implement**：`{slug}-checklist.yaml` 中已 `done` 的步骤不重做，从第一个 `pending` 步骤开始
- **acceptance**：如 `{slug}-acceptance.md` 已有部分节，检查哪些节已填写（有实质 checklist 勾选），从下一个未完成节继续
- **issue-analyze**：如 `{slug}-analysis.md` 已存在，检查 5 节是否都有内容，缺失的补做，已有的不重写
- **issue-fix**：如代码已改但 `{slug}-fix-note.md` 不存在，直接进入验证 + 写 fix-note 环节

恢复时先向用户简短汇报："检测到上次工作到 X 阶段，我从 Y 继续"。

---

## 2. 扩展点

### 新增子工作流

新工作流定型后，在 `cs-onboard/reference/system-overview.md` 的"技能分成四部分"和"场景路由"表里加一段索引，并登记新的目录位置。

### 跨阶段新约束

如果发现某条规则适用于所有阶段（例如所有 spec doc 都必须补某个字段），优先写进共享 reference（`shared-conventions.md` 或 `system-overview.md`），不要只改一个子技能。

### 新模板 / 新产物类型

如果引入新的 spec 产物（例如风险评估表、回滚预案），先在 `shared-conventions.md` 登记路径，再在对应阶段技能里引用。

### 共享术语表

如果 CodeStable 自己形成了稳定共享术语，应优先沉淀成共享 reference，而不是散落在多个子技能里重复定义。

### 跨工作流状态一览

目前查看"项目当前有几个 feature 在进行中、几个 issue 未关闭"仍需要手动查询。未来如要补 `status.py` 或 `.codestable/STATUS.md`，先在 `shared-conventions.md` 登记方向，再实现。

---

## 3. 维护规则

- 每次扩展都要同步更新 `system-overview.md` 索引和相关子技能
- 不允许只在某个子技能里加东西而不在 `system-overview.md` 登记
- 共享说明优先放 `.codestable/reference/`，不要散落在各子技能里