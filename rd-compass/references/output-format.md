# 输出数据与同源交付

本轮入口与交付统一遵守 [市场确认、角色阅读和完整性](reader-research-contract.md)。新兴技术、发展阶段、技术空白和跨领域匹配按 [技术变化与机会研判](technology-opportunities.md) 按需启用。市场搜索未经使用者确认时不开展，保留相关判断未知；旧版既有研究记录继续复用。

未来技术趋势与研发储备报告另见[预研数据与生成约定](foresight-format.md)。常规新研究采用 `schema_version: 3`，保留 schema 2 的研究数据和台账。旧 schema 1/2 仍可打开及复现，旧格式见 [旧约定](output-format-v1.md)。重新生成旧 schema 2 时，原来的自由文字摘要标为历史摘要。新增字段按实际来源填写。纯技术说明可以省略 `recommendations`，也可以明确留空。

## 命令

```text
python scripts/render_report.py assets/report-data.v2.example.json --bundle demo
python scripts/render_report.py --check-bundle demo
python scripts/render_report.py INPUT.json --output report.html
python -m unittest discover -s tests -v
```

--bundle 生成 report.html、catalog.html、reading.csv、research-data.json 和 manifest.json。单文件报告也内含逐件记录和完整数据，转发后不依赖目录页。清单记录各文件哈希、数据版本与派生计数；--check-bundle 可发现被替换成旧版的文件。所有内容先校验并生成，再逐文件替换，最后写清单；中途系统故障仍可能产生不完整批次，应运行校验并从原输入重新生成，不能声称整个目录事务原子提交。

--output 只生成单文件报告，不会同步目录中的其他历史文件；正式多成果更新使用 --bundle。生成前输入不合法不覆盖既有成果。内容指纹检查不验证专利事实。

## 顶层字段

| 字段 | 约定 |
|---|---|
| schema_version | 新研究填 3。旧报告和旧示例继续使用原 schema |
| data_version | 本次冻结输入的版本字符串；不能代替资料截止日 |
| modes | technology、opportunity、decision 的非空数组，可组合 |
| title / cutoff / finding / boundary | 题名、YYYY-MM-DD 资料截止日、已有发现、影响结论的边界 |
| background | title/text/evidence 数组；technology 模式必填，可如实说明背景未知 |
| current_landscape | 当前已查范围内的技术格局；technology 必填 |
| decision_context | decision 必填；写目标、限制、偏好及关键未知，不能默认项目目标 |
| recommendations | 机会与决策模式必填数组，无合格首屏建议时填 `[]`。技术模式作首屏建议时也使用该数组。`finding` 只写已支持的发现，共同未知写入 `boundary` |
| opportunity / judgment | 仅旧版顶层摘要字段，schema 3 不接受。每条方向自身的 `judgment` 仍保留，首屏引用方向名称和该判断。 |
| records / routes / directions / evidence | 四个数组，可为空，按本次研究范围填写 |
| timeline | 可选事件数组；没有历史材料不强造时间线 |
| plan / plan_requested | 可选 title/text 数组；decision 或明确 plan_requested:true 才展示计划。该布尔值须来自真实任务要求，不能为通过检查自设授权 |
| worklog / appendix / references / decision_boundary | 沿用旧约定的补证记录、附录、来源与条件边界 |

## 逐件记录 records

每条包含 id、document_id（准确文献号与版本）、in_sample（布尔）、reading、read_scope（实际阅读范围）、review。

- reading：not_started / screened / targeted / complete；complete 只指 read_scope 所约定的完整主阅读范围，必须另说明是否完整权项、说明书、必要附图，局部段落补读用 targeted。
- review：not_reviewed / self_checked / independent。independent 还需 reviewer 和 review_scope，且应确有独立原文阅读，不是模型改名。
- 可选 application_id、family_id、source_reader、source_record_id、source_snapshot、row_number、row_number_basis 等来源字段可随快照保留。程序原样保留这些字段，不声称自动完成上游适配或同族核验。
- 上游清单是权威来源时，由分析者映射/引用其稳定ID并冻结快照；本格式不另建长期并行台账。上游改变后重新导出再渲染。

阅读与复核是不同维度，分别统计，不能把两个维度的数量相加。主样本与补充记录分别计数。没有完整申请/同族映射时不能凭记录数推算申请数或同族数；需要这些统计时先核验并明确口径。

## 现有路线 routes 与候选方向 directions

route 包含 id、name、task、mechanism、development、limitations、evidence。说明现有实现，不自动成为候选方向。历史未明可在 development 中如实说明只完成结构对照。mechanism 用完整过程解释；静态结构不强填触发动作。

direction 沿用 name/benefit/tradeoff/judgment/evidence_state/decision_state、五项 reasoning、conditions 及可选内嵌 figure/caption，另有 route_ids、judgment_kind、rationale。route_ids 允许为空（例如来自新的替代原理），否则必须对应实际路线。

judgment_kind 为 conditional_candidate、research_priority、comparison_baseline、performance_comparison。前三类不强求实测；性能比较还需 comparison_conditions 和 comparison_evidence。程序只检查字段与引用，证据是否可比及结论强度必须内容复核。非决策模式不展示候选的决策阶段，但保留原数据。

## 首屏研发建议 recommendations

| 字段 | 约定 |
|---|---|
| direction_id | 已有 `directions` 中的一个 ID，同方向只出现一次 |
| evidence | 至少一个支持本方向的证据 ID。对应证据要有同件同版本的文献号、原文链接和权项、页段或附图等实际位置，且引用于本方向五步推导的第一步材料披露或对应机制路线。仅在对照、使用条件或筛选标签出现的条目不能作为本方向的原文依据 |
| conditions | 对方向与对照同时适用的任务、配置、工况和边界 |
| comparator | `name` 为可实施的具体基线，`mechanism` 说明在共同工况的工作方式。`basis_type: disclosure` 须配至少一条有原文的 `evidence`。`basis_type: engineering_baseline` 表示待验证的工程对照，明确其设定，可补来源 |
| check | 在共同工况下比较的具体指标、现象或动作，说明如何判断是否有实质差异 |
| elimination | `trigger` 写能观测到的失败结果或不满足的硬约束，`action` 写触发后停止该方向、缩小适用范围或切换方案 |

首屏的链接进入同一个方向条目；条目直接显示这组工况、对照和淘汰条件，证据链接打开原文定位。编辑时检查原文是否真的支撑该机构、双方是否使用同一工况、淘汰条件能否改变取舍。没有实测时明确工程待验边界，不编造阈值或试验结果。仍不满足三个条件的想法可在正文标为线索。

## 证据 evidence

沿用 E 编号、title、summary、source_role、in_sample、location、disclosure、limitation、directions、documents。record_ids 可关联零到多条实际记录；零条适用于未纳入逐件台账的背景资料，仍必须准确引用来源。卡片存在不等于文献已读完。

documents 每项为 number/url，可增加 locations:[{statement, locator}]，在卡片中分别展示具体陈述与页码、段落或网页位置。来源链接只接受 HTTP(S)。背景事实也可直接放 references；影响关键结论时应进入可定位证据，不能用背景身份降低所需核查。

卡片与记录可多对多关联，既不能要求卡数等于已读数，也不能把卡数当作所有正文来源的数量。records.in_sample 决定记录统计；evidence.in_sample 是该卡的统计说明，混合来源卡应在 source_role 与 limitation 写清，不据卡片倒推原始分母。

## 时间记录 timeline

每项含 date（ISO日期或 null）、date_type（publication / grant / product_release / source_date / unknown）、document_id、title、change、evidence。新稿的 title 是简明技术标题，change 用一句话写能区分路线的要点，完整工作过程写在路线中。可选 route_ids 对应实际现有路线，供卡片直达；旧数据省略该字段仍可生成。已知日期相对升序，未知日期标明并放在已知节点之后；date_type 不由文献后缀自动生成。document_id 必须能对应所引证据的 documents.number 或关联 records.document_id。

可选 earliest_verified_disclosure:true 仅适用于已知 publication 事件，还需 disclosure_locator 和 search_scope。表示本次已查范围内较早披露，不是行业首次。授权事件在较早公开未取得时仍可显示，不能借授权日声称技术起点。文献公开日、授权日、产品时间分别取证，继承/替代关系不是该字段推导结果。

新版不自动生成主题化时期结论；需要解释发展时写在路线 development 中并引用依据。不能根据日期分箱替读者推导技术阶段。

## 内容与页面验证

内容按 reader-review.md 审阅。结构检查、来源真实性、研究理解和浏览器交互是独立检查，分别记录。默认示例均为合成材料。合成测试成功不能称水壶真实报告已经重跑通过。

## 0.5.0 可选方法关联

method_support.version 为 1，包含 opportunities、comparison、evidence_actions、method_notes，字段和校验见 [方法关联数据](method-support-format.md)。模块按任务选择，旧 schema 2 可继续生成。程序检查机会/方向/情境/指标/证据引用、比较覆盖和实际结果状态；不能证明需求真实、证据可比或结论已在语义上同步。

assets/report-data.methods.example.json 为完整合成回归数据。references/kettle-method-case.json 是两件真实专利的限定研究，阅读与评审边界见 case-review.md；它不是行业全景、需求调查、实验或法律结论。

## 0.5.1 正文段落与交付回查

方向可增加 narrative:[{text,evidence}]，由分析者按完整句子撰写并审核。正文须包含值得研究的能力、关键成立条件与代价，不能只剩营销摘要；reasoning 与 conditions 仍保留在数据及可展开依据中。未提供 narrative 的旧数据继续完整展示原推导，生成器不自动压缩或补造。

method_support 可使用 research_check 及行动 access/current_judgment/remaining_reason/attempts，具体规则见 method-support-format.md。旧 schema 1/2 继续可读，不自动声明经过新版验收。

证据 ID 直接沿用交接记录的非空字符串，在同一研究内精确区分并唯一。E02 与 E2 是两个不同 ID；所有引用使用原值，不按数字改写。报告对需要安全编码的 ID 仅转换页面锚点，研究数据与显示文本保留原值。重复 ID、未登记引用或无效 Unicode 会报错。
