# 代码维度速查

写代码前先确认每个维度的档位。没明说的走默认，偏离默认的地方要标出来让用户确认。

这份文档是 CodeStable 子技能共享的口径，被 design / fastforward / issue-fix 等阶段引用。项目内的权威副本在 `.codestable/reference/code-dimensions.md`，由 `cs-onboard` 从技能包释放。

---

## 核心四维（每次都要定）

### 健壮性 Robustness —— 错误处理的严苛程度

- **L1 快跑**：happy path 跑通就行，异常直接崩、让它炸。适合一次性脚本、探索代码。
- **L2 够用**：捕获预期错误（文件不存在、网络超时），非预期错误往上抛。适合内部工具。
- **L3 严防**：所有外部输入验证、所有失败路径都有明确处理、关键操作幂等可重试。适合对外接口、生产系统。

### 结构 Structure —— 代码组织的颗粒度

- **inline**：全写在一起，十几行搞定的那种。
- **functions**：按职责拆函数，同一个文件内。
- **modules**：拆多个文件/模块，有明确的导入关系。
- **layers**：分层架构（如 handler / service / repository），有依赖方向约束。

### 性能 Performance —— 对开销的关注度

- **careless**：怎么方便怎么写，O(n²) 也无所谓。
- **reasonable**：避开明显的坑（循环里查 DB、重复计算），但不刻意优化。
- **budgeted**：有明确的性能预算（延迟、内存、QPS），按预算设计数据结构和算法。
- **extreme**：榨性能，要 profiling、要基准测试、可以牺牲可读性。

### 可读性 Readability —— 写给谁看

- **self**：自己当下看得懂就行，命名可以随意。
- **team**：队友半年后还能快速上手，命名规范、关键处有注释。
- **public**：外部开发者能无背景读懂，公共 API 要有文档、示例。
- **teaching**：代码本身就是教材，每一步意图清晰、刻意展示模式。

---

## 场景维度（相关时才定）

### 可演进性 Evolvability —— 预期会怎么变

- **frozen**：接口锁死，不许改（如已发布的库 API）。
- **stable**：偶尔变，变动要走流程、要兼容。
- **active**：当前在迭代，接口随业务调整。
- **experimental**：随时推倒重来，不考虑向后兼容。

### 可观测性 Observability —— 运行时能看到多少

- **opaque**：黑盒，出了问题靠猜。
- **logged**：关键路径有日志，能事后翻查。
- **traced**：有链路追踪，跨服务能串起来。
- **instrumented**：指标齐全（metrics / traces / logs 三件套），可接告警。

### 可测试性 Testability —— 测试覆盖的深度

- **untested**：没测试。
- **testable**：结构支持测试（依赖可注入、副作用可隔离），但还没写。
- **tested**：有单元/集成测试覆盖主要路径。
- **verified**：核心逻辑有测试 + 关键不变量有断言/属性测试/形式化验证。

### 安全性 Security —— 信任边界

- **trusted**：全在可信环境内，不设防。
- **validated**：外部输入做校验和清洗。
- **sandboxed**：权限最小化、危险操作隔离（容器、subprocess 限权）。
- **hardened**：按对抗性环境设计，防注入/防越权/防侧信道，有威胁模型。

---

## 特殊维度（只在涉及时提）

- **Concurrency 并发**：single-threaded / thread-safe / lock-free / distributed
- **Determinism 确定性**：nondeterministic / reproducible / deterministic
- **Compatibility 兼容性**：current-only / backward-compatible / cross-version
- **Idempotency 幂等性**：non-idempotent / idempotent / exactly-once

---

## 常用默认组合

| 场景 | 组合 |
|---|---|
| 聊天里问的随手代码 | L1 + inline + careless + self + experimental |
| 项目内部工具 | L2 + functions + reasonable + team + active + logged + testable |
| 对外发布的库/服务 | L3 + modules + budgeted + public + stable + traced + tested + validated |

没明说就按场景走默认。动手前列出关键档位，偏离默认的地方明确标出来让用户确认。

---

## 怎么用这份文档

- **design / fastforward 起草时**：AI 先按场景猜默认组合，把判断出的"可能偏离默认"的维度列出来问用户；用户没明确说的维度按默认走。只记偏离项，默认档位不抄。
- **implement / fix 写代码时**：翻一眼当前 feature 或 issue 记录的维度档位，按档位写。比如记了 `健壮性=L3` 就不要偷工省掉输入校验；记了 `可读性=public` 就得补示例和文档。
- **acceptance / review 时**：把维度档位当成验收标准的一部分——档位说 L3 但代码里外部输入没校验，就是不达标。
