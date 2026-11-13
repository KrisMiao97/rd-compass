# 输出数据与同源交付（schema 2）

新研究采用 schema_version: 2。兼容旧 schema 1，旧格式见 [旧约定](output-format-v1.md)；旧示例和历史报告继续可运行，但不自动获得新增的日期、台账或语义验收。新增字段必须按实际来源填写，禁止猜造。schema 2 可只解释技术，不强制生成未来方向。

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
| schema_version | 2 |
| data_version | 本次冻结输入的版本字符串；不能代替资料截止日 |
| modes | technology、opportunity、decision 的非空数组，可组合 |
| title / cutoff / finding / boundary | 题名、YYYY-MM-DD 资料截止日、已有发现、影响结论的边界 |
| background | title/text/evidence 数组；technology 模式必填，可如实说明背景未知 |
| current_landscape | 当前已查范围内的技术格局；technology 必填 |
| decision_context | decision 必填；写目标、限制、偏好及关键未知，不能默认项目目标 |
| opportunity / judgment | 可选的产品机会和条件判断，纯技术理解不强填机会 |
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

## 证据 evidence

沿用 E 编号、title、summary、source_role、in_sample、location、disclosure、limitation、directions、documents。record_ids 可关联零到多条实际记录；零条适用于未纳入逐件台账的背景资料，仍必须准确引用来源。卡片存在不等于文献已读完。

documents 每项为 number/url，可增加 locations:[{statement, locator}]，在卡片中分别展示具体陈述与页码、段落或网页位置。来源链接只接受 HTTP(S)。背景事实也可直接放 references；影响关键结论时应进入可定位证据，不能用背景身份降低所需核查。

卡片与记录可多对多关联，既不能要求卡数等于已读数，也不能把卡数当作所有正文来源的数量。records.in_sample 决定记录统计；evidence.in_sample 是该卡的统计说明，混合来源卡应在 source_role 与 limitation 写清，不据卡片倒推原始分母。

## 时间记录 timeline

每项含 date（ISO日期或 null）、date_type（publication / grant / product_release / source_date / unknown）、document_id、title、change、evidence。已知日期相对升序，未知日期可保留；date_type 不由文献后缀自动生成。document_id 必须能对应所引证据的 documents.number 或关联 records.document_id。

可选 earliest_verified_disclosure:true 仅适用于已知 publication 事件，还需 disclosure_locator 和 search_scope。表示本次已查范围内较早披露，不是行业首次。授权事件在较早公开未取得时仍可显示，不能借授权日声称技术起点。文献公开日、授权日、产品时间分别取证，继承/替代关系不是该字段推导结果。

新版不自动生成主题化时期结论；需要解释发展时写在路线 development 中并引用依据。不能根据日期分箱替读者推导技术阶段。

## 内容与页面验证

内容按 reader-review.md 审阅。结构检查、来源真实性、研究理解和浏览器交互是独立检查，分别记录。默认示例均为合成材料。合成测试成功不能称水壶真实报告已经重跑通过。
