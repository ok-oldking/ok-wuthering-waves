# CodeStable 体系总览

本文档介绍 CodeStable 工作流家族整体——有哪些子技能、各管什么场景、产物怎么组织。无论是 AI 在运行时读到这个文件，还是人打开来看，都能对整个体系有个完整印象。

AI 辅助开发里，有几类场景会反复出现——加新功能、修 bug、遇到值得沉淀的经验、做技术选型、摸新模块的代码、接入新仓库。每种场景如果每次从零处理，都会出各自的典型问题：AI 给功能起的术语跟老代码冲突、bug 改完没人记得当时怎么诊断的、上周刚踩过的坑下周又踩一遍。

CodeStable 把这几类场景各配一套子技能，产物放进统一的目录结构、带统一的 YAML frontmatter,互相之间可以检索引用。


## 技能分成四部分

**根入口**——开放式诉求 / 不知道走哪个时的统一入口:

- `cs` — 介绍体系全貌 + 把诉求路由到正确的 cs-* 子技能。本技能不做事,只做分诊和提示

**做事**——从一段模糊想法走到上线的功能、或者从一份错误报告走到修好的 bug:

- `cs-feat` — 新功能,design → implement → acceptance（想法还模糊时先走讨论层 `cs-brainstorm` 做分诊，不属于 feature 流程内部）
- `cs-issue` — 修 bug,report → analyze → fix
- `cs-refactor` — 代码优化(行为不变、结构/性能/可读性变),scan → design → apply

两类都不直接让 AI 写代码,而是先产出 spec(功能方案 / 问题分析),用户 review 后再动手,代码和 doc 一起交付。针对的是术语冲突、范围失控、改完不留存档这三种 AI 默认会出的问题。

**沉淀**——把做事过程产生的知识存下来,下次遇到同类问题直接复用:

- `cs-learn` — 回顾"做 X 时踩了 Y 这个坑"
- `cs-trick` — 处方"以后做 X 就这样做"
- `cs-decide` — 规定"全项目今后都按 X 来"
- `cs-explore` — 存档"调查了 X 问题,看到代码里是这样的"
- `cs-note` — 把一两行启动必读的项目注意事项追加到 `.codestable/attention.md`

**讨论层**——想法还模糊时的统一入口,不直接产出设计或代码:

- `cs-brainstorm` — 和用户对话做分诊:case 1(已经够清楚,直接 feature-design)、case 2(小需求,在 feature 里继续讨论并落 `{slug}-brainstorm.md`)、case 3(大需求,移交给 roadmap)

**辅助**——围着前几类转的周边工具:

- `cs-onboard` — 把新仓库接入 CodeStable 目录结构
- `cs-req` — 起草或刷新 `.codestable/requirements/` 下的需求文档——系统的能力愿景层，覆盖过去/现在/未来
- `cs-arch` — 架构相关一站式:起草新架构文档 / 刷新已有文档 / 做架构体检(含 design 自洽 / design↔代码一致 / architecture 目录多份文档间一致)。architecture 只记现状
- `cs-roadmap` — 把一块装不进单个 feature 的大需求拆成带依赖和状态的子 feature 清单,作为后续多次 feature 流程的种子和排期依据;独立于需求 / 架构档案
- `cs-guide` — 写给外部读者的开发者指南 / 用户指南
- `cs-libdoc` — 为库的公开 API 逐条目生成参考文档


## 场景路由

仓库里还没有 `.codestable/` 目录,先用 `cs-onboard` 搭骨架。

| 场景 | 子技能 |
|---|---|
| 想法还模糊 / "有个想法没想清楚" / "先聊聊" | `cs-brainstorm`(分诊后路由到 design / feature-brainstorm 落盘 / roadmap) |
| 新功能 / 新能力 | `cs-feat` |
| BUG / 异常 / 文档错误 | `cs-issue` |
| 代码优化 / 重构 / 重写(行为不变) | `cs-refactor` |
| 摸代码、提问调研 | `cs-explore` |
| 补 / 更新需求文档 | `cs-req` |
| 补 / 更新 / 检查架构文档 | `cs-arch` |
| 大需求拆解 / 排期规划 | `cs-roadmap` |
| 技术选型 / 约束 / 规约 | `cs-decide` |
| 踩坑回顾、经验总结 | `cs-learn` |
| 可复用的编程模式、库用法 | `cs-trick` |
| 开发者指南 / 用户指南 | `cs-guide` |
| 库 API 参考 | `cs-libdoc` |

完整的操作手册、退出条件、和其他工作流的关系,各子技能里讲。


## 沉淀类四个子技能如何区分

learning / trick / decision / explore 都是存档文档类型,区别在记录内容的性质:

- 回顾某次做 X 时发现了 Y —— `cs-learn`(产出 `doc_type: learning`)
- 以后做 X 就这样做的处方 —— `cs-trick`(产出 `doc_type: trick`)
- 全项目今后都得遵守的规定 —— `cs-decide`(产出 `doc_type: decision`)
- 调查了一个问题,留份证据 —— `cs-explore`(产出 `doc_type: explore`)

四者共用 `.codestable/compound/` 目录,靠 frontmatter 的 `doc_type` 字段和文件名中间的类型段(`YYYY-MM-DD-{doc_type}-{slug}.md`)区分。每个子技能只认自己的 `doc_type`,不读写别家产物——**"A 和 B 有什么不同"这种判断由本节负责,子技能里不再重复**。


## 愿景档案 vs 结构档案 vs 规划档案 vs 单次动作

四类文档各管一段时间尺度,不要混:

- **愿景档案**(requirements)——描述"用户需要什么、系统提供什么能力来满足"。`status` 区分三个时间深度：`draft`（未来愿景）、`current`（现在的能力）、`outdated`（过去的痕迹）。draft req 可独立于实现存在——先把愿景定下来，后续 roadmap 排期和 design 实现才有稳定对齐基准
- **结构档案**(architecture)——描述"系统现在用什么结构实现"。只记现状,默认在 feature-acceptance 时跟着代码同步;必要时由 cs-arch 主动刷新。**不写"未来会加什么层"**
- **规划档案**(roadmap)——描述"接下来打算怎么分步实现"。独立于愿景和结构档案,改动不牵连 requirements / architecture。所有条目 done / dropped 后 roadmap 进入 `completed` 状态,作为历史档案留存
- **单次动作**(feature / issue / refactor)——本次要做的一件具体事情的 spec。动作走完后,相关沉淀提炼进愿景档案、结构档案和沉淀类文档

用户说"我想要一个 X 系统"这种大需求,先走 roadmap 拆成若干子 feature,再一条一条走 feature 流程。直接起 feature 会变成巨型 design 塞不下、拆了又没有追踪抓手。


## feature 和 issue 的阶段不可跳

feature 走 brainstorm(可选) → design → implement → acceptance,issue 走 report → analyze → fix。每个阶段有退出条件,上一个没满足,下一个不开始。

AI 最常见的问题是一口气铺几百行代码才让人看——等发现问题已经很难中止。阶段间的人工 checkpoint 就是为了早一步中止。每个 checkpoint 具体检查什么,对应子技能里讲。

例外两种:issue 根因一眼确定时走快速通道,跳过 analyze 直接 fix;feature 范围小时走 `cs-feat-ff`,写完 spec 直接进实现。


## 进一步参考

- `.codestable/reference/shared-conventions.md` — 目录结构、YAML frontmatter 口径、`{slug}-checklist.yaml` 生命周期、收尾 commit 约定、归档类共享规则
- `.codestable/reference/tools.md` — `search-yaml.py` / `validate-yaml.py` 用法
- `.codestable/reference/maintainer-notes.md` — 断点恢复、新增子工作流的登记

目录结构(requirements/、architecture/、roadmap/、features/、issues/、compound/、tools/、reference/)的权威定义在 `shared-conventions.md`。要改目录先改那里——方法是改 `cs-onboard/reference/shared-conventions.md` 这个模板,新项目 onboard 时会带上新版本。


## 相关

- `.codestable/attention.md` — CodeStable 技能启动必读的项目注意事项
- `.codestable/architecture/ARCHITECTURE.md` — 项目架构总入口
