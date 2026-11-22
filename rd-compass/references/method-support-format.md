# 可选方法关联数据（schema 2 扩展）

顶层增加 method_support，内含 version: 1。所有模块按任务提供，旧 schema 2 无此字段仍然有效。数据先按研究内容写完整，再渲染；程序不创建分析结论、不推导分数、不自动改写建议。完整合成示例见 assets/report-data.methods.example.json；真实专利有限案例见 references/kettle-method-case.json 与 case-review.md。

字符串需非空；未知用完整句子说明，不填伪值。ID 采用字母开头的字母、数字、下划线、点或连字符。以下 evidence 都引用现有 E 编号，direction_ids 引用 D 编号，route_ids 引用已有路线，不另建阅读台账。

## opportunities：机会与实现路径数组

每项必填 id、name、need、need_state、capability、mechanism、prerequisites、next_condition、非空 direction_ids。可填 route_ids、evidence、need_evidence。

- need_state: hypothesis（用途假设）、stated_goal（明确目标）、observed（有使用侧证据）。
- stated_goal 必须有 goal_source，准确说明任务或已批准目标来源；observed 必须有 need_evidence。
- need_evidence 支持需求；evidence 支持技术联系。程序只能检查引用存在，不能辨别来源是否真能证明需求。
- next_condition 写未来推进的前提；历史事件继续用 timeline，不自动转成项目日期。

## comparison：共同情境比较对象

必填 scope（本次比较范围）、baseline（简单基准及纳入/不纳入原因）、depth（实际分析深度）、非空 direction_ids、criteria、scenarios、cells。可填 uncertainties、vulnerabilities。

criteria 每项为 id/name/requirement/kind/basis/evidence：kind 为 mandatory 或 preference；requirement 给出可接受标准，未知阈值明确标注；basis 说明来源。

uncertainties 每项为 id/name/range/basis/evidence。range 可用定性范围；区分外部不确定性与可控参数。

scenarios 每项为 id/name/conditions/why_plausible/judgment/uncertainty_ids。judgment 是该情境下经过分析的取舍文字，不是浏览器计算结果。

cells 每项包含 direction_id/scenario_id/criterion_id/status/basis_type/reason/evidence。比较集合中的每个候选×情境×标准恰有一格；不能通过漏填隐藏不利结果。

- status: meets、fails、unknown；分别显示支持满足、支持不满足、尚不能判断。
- basis_type: measurement、model、inference、disclosure、unknown。
- 实测、模型、披露必须引用证据；unknown 依据只能对应 unknown 结论。
- 披露只能证明对应结构是否存在等问题，不能据此声称性能达标；这是内容审阅责任。

vulnerabilities 每项为 direction_ids/scenario_ids/conditions/reason/adaptation/switch_signal/evidence；方向、情境引用不能为空。写失败条件组合、原因、可研究调整和重新考虑的信号。

正文默认显示全部情境的取舍概览；详细矩阵可展开，下拉框只筛选已分析情境。内部引用显现目标及全部祖先详情；无脚本仍可手动展开，打印显示全部内容。不提供没有模型依据的滑块或自动排名。

## evidence_actions：补证及结果分支数组

每项必填 id/question/decision/known/approach/priority_reason/resources/timing/stop_rule/inconclusive/kind/status、非空 direction_ids，以及至少两个 outcomes。可填 opportunity_ids/scenario_ids/criterion_ids/evidence。

- kind: document、records、interview、measurement、model、test。
- status: proposed、in_progress、completed。measurement/model/test 需 decision 模式或真实 plan_requested:true；不能为通过检查自设授权。
- outcomes 每项 id/result/decision_change，写可能观察与相应取舍；inconclusive 写仍不能区分时怎么办。
- resources 与 timing 不知时说明具体未知及影响，不虚构费用/时间；priority_reason 同时说明决策作用及安排理由。
- completed 必须有 result 对象：observed、decision_change、update_note、非空 evidence、outcome_id；outcome_id 对应某个结果分支或 inconclusive。
- 尚未完成时不允许填写 result。update_note 写已同步的位置和仍待处理部分；程序不证明文字与各结论语义一致，需实际回查。

criterion_ids 用于定位受影响指标，页面展示其名称；缺少 comparison 时只能留空。证据行动不是强制试验清单，原文核对可以在机会探索中使用。

## method_notes：本次方法应用数组

每项 method/trigger/inputs/work/result/limits/evidence。method 可为 ifm/rand/nasa/morphology/jtbd/triz/doe，同一方法只填一次。DOE 需已要求验证；结果区记录具体产出，不能只写“采用某方法”。

页面显示方法来源及本次应用深度。不自动加入所有方法；只记录真正发生的工作。没有独立专家或用户参与时，不得称已获得独立复核或用户验证。

## 0.5.1：阅读层与主动补证验收

结构关联继续保留，页面不再把所有对象渲染成同级章节。comparison 的短概览与未解决问题的结果分支直接显示；opportunities、完整矩阵、已完成补查与方法说明进入相应可展开依据。

comparison 可增加 shared_findings:[{text,evidence}]，由分析者撰写适用于多候选/情境的共同发现或限制；程序不自动归纳。证据引用规则同其他内容。

evidence_actions 可增加：
- access：available（现有授权内可取得）、external（需未取得的企业记录、真实观察或新试验）、unavailable（已经尝试但来源不可取得）。这只是本次判断，不由 kind 自动推断。
- current_judgment：当前能支持的判断；remaining_reason：仍未解决的具体原因。未完成项在 ready 交付时必填。
- attempts:[{source,work,finding,evidence}]：实际尝试的来源、做过的动作与结果；失败可以没有证据卡，但仍必须准确说明来源和失败原因。不得补造检索或工具执行。

method_support 可增加 research_check:{status,data_version,content_review,reading_review}。status 为 in_progress 或 ready；data_version 必须等于当前研究版本；后两项记录实际补证/内容回查与顺读回查。新方法研究交付时应填写，旧数据缺少时继续读取并注明未记录新版验收。

ready 的未完成行动只允许 access 为 external 或 unavailable，并须有 current_judgment/remaining_reason；unavailable 还必须有 attempts。available 的关键行动未完成会被拒绝，必须先完成或经实际尝试重新判断可取得性。不能为了过检查改成 external/unavailable；来源与状态真实性、是否遗漏关键疑问、结论回写与阅读质量仍需内容审阅。in_progress 可以保留待执行行动，但报告会显示尚未通过交付前回查。

所有补证执行由宿主分析者使用已授权工具完成；渲染脚本只校验和展示数据，不会自行检索或创建工程判断。
