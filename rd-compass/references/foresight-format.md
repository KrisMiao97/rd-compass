# 生成填写模板或真实项目报告

在 Skill 所在目录运行。模板目录须为新目录或空目录。交互页可离线打开，向填写者说明如何下载已填 Markdown 保存工作。

```text
python scripts/render_report.py --foresight-template 我的填写模板
python scripts/render_report.py assets/foresight/steam-oven.example.json --bundle 蒸汽烤箱示例
python scripts/render_report.py --check-bundle 蒸汽烤箱示例
python scripts/render_report.py 项目研究数据.json --output 项目报告.html
```

真实项目使用自己的研究数据。内置案例展示结构及有记录的公开材料，可用来试运行。复用格式时替换对象、事实、日期、原文和判断。完整成品包包括报告、逐件阅读页、阅读 CSV、研究数据和文件校验清单。单独打开报告也能查证据、看阅读清单并下载已确认的交互填写模板。包检查仅核对文件一致性。

## 哪些文字需要在建议旁就能读懂

首段 finding 概括已观察到的变化。各时间视野的 answer 写给首次看到该建议的人，说明对象、场景、原因和下一项决定，boundary 保留关键限制。第 6 章用候选的 narrative 及适用时的 process 说明基线、拟改的部件或步骤、证据性质和未知。第 8 章每个方向用 conclusion 概括最接近的公开内容及最影响决定的缺口，计数和来源仍保留。

工程验证的 comparator 写明简单对照与具体差异，check 写同工况的观察方法。change_condition 是改变本项安排的条件。elimination.trigger 和 action 说明何时放弃或调整候选。同项中两处触发和处置一致时生成器显示一次，含不同适用组别或条件时分别显示。近义重复由作者按适用范围核对。能力储备按用途填写留存成果和失效处理。原数据缺少参数时标明未知，继续使用原有字段与证据编号。

## 新预研报告的首读字段

- 顶层 finding 用一句话概括发现。foresight.finding_points 是依次显示的分项，每项含 label、text、evidence（原证据编号列表）。有时间证据时从早期基线讲到后来的具体变化，并列的技术变化分别写；最后点明这批材料能把性能判断推进到哪一步。只有缺口也可写一项，不补造年代、数量或趋势。
- foresight.scope_note 用一句话点出最影响取舍的限制。完整范围、核查深度、来源矛盾和检索失败保存在顶层 boundary，摘要末可展开。某项矛盾若影响一个决定，在该建议旁也写明能确认什么、还缺什么。问题的 answer 仅概括本时间视野的安排及理由，不把全部行动挤进一段。
- 每条 recommendations 项增加 first_read 对象。mechanism 写使用情境、部件位置或流程环节、动作与结果，分清原文的参照和本项目设想。comparison 写实际基线、共同条件、改变的因素、观察最终表现的手段；以信号推断实际状态时交代独立参照。decision 写如果出现哪种可观察结果，则对哪项任务采取什么行动；阈值未定时指出何时约定，先写可区分的结果方向。对于能力储备或观察线索，比较现行做法、独立参照或维持现状，说明保留什么、信息失效如何处理。建议卡原 evidence 应指向支持其机理的记录。一个没有对应建议的 direction 自身也须提供 first_read，解释怎样比较或因何暂缺可比条件。
- 三个字段各写一至两句。可用读者在产品上能实际找到的对象、可观察到的后果检验措辞。摘要和候选章由同一组文字生成。多个候选分别填写。工程比较不指定任何产品的排序、候选结构或阈值。

## 数据怎样对应报告

沿用[常规报告的数据](output-format.md)与原证据编号。新报告指定 `schema_version: 4`、`report_contract_version: 3`、`foresight.version: 2`（历史 version 1 仍可生成）。每个时间视野各对应一个 `reader_contract.questions` 问题。明确完整预研时用 `scope: full`，模式含 technology、opportunity、foresight；约定仅研究一部分时用 limited，并写清限制。项目未完成可用 `method_support.research_check.status: in_progress`，按真实状态登记复核。常规研究和原有 schema 1–3 沿用原流程。

| 字段 | 用法 |
| --- | --- |
| horizons | 完整报告含 near 和 reserve。逐项写 window、question_id、reason、status、recommendation_ids。有建议填 assessed_with_recommendations；未形成建议、证据不足、已确认调整范围分别用 assessed_no_recommendation、insufficient、out_of_scope。问题状态与正文一致。 |
| search_scope、family_rule、history_boundary | 范围、同族去重口径、历史材料能支持的时间与结论。每个方向另外记录自己的检索轨迹。资料截止日与 reader_contract.as_of 分列。 |
| timeline、evidence、records | 时间事件写 attribution 标明申请人或发布者，通过 document_id、locator、evidence 对到同件原文。证据写 kind、origin、documents、locations、record_ids。阅读与复核分别记。不同编号即使只有前导零不同也要保留。 |
| trends | 逐项填写 observation、hypothesis、independence、alternative、condition、review_trigger 和 evidence。尚不能提出趋势时用空列表并写 trend_gap。 |
| routes、directions | 现有路线与未来候选分别建档。算法、工艺、材料或系统用 mechanism_kind 对应 algorithm、process、material、system，并给 input、process、output、application_conditions 和引用原文的 narrative。如果还含运动部件，设 has_moving_part 为 true 并补运动过程。 |
| readiness | 每方向先写 bottleneck 说明最先影响投入的瓶颈。dimensions 包含 performance、integration、production、durability。各写 judgment、gap、evidence、status。可用 supported、partial、unknown；无支持材料的项保留 unknown。 |
| direction_reviews | 每方向写 target、search_log、members、closest、structure_gap、performance_gap、next_step、completion、conclusion。每个 member 引一条 record_id，列 family_id、family_basis、direct；判断披露时给 locator。定点原文已经明确写出的事实可另记在该 member 的 located_finding，填写 evidence_id、locator、text。它显示在计数前，不自动增加复核或披露同族数。未计数给 uncounted_reason。最接近项写 evidence_id、document_id、locator、match、difference；并列者按同一结构放入 equally_close。无从确定时用 null 并填写 closest_gap。 |
| recommendations | 每项有稳定 id、direction_id、horizon_ids、action_kind、stance、conditions、check、evidence、change_condition。engineering_validation 还需比较对象和淘汰条件。capability_reserve 或 watch 需 alternative 与 review_trigger。stance 选 advance、hold、stop。同一方向有不同处理意见时，以 scope_explanation 解释适用范围。 |
| roadmap | 节点列 id、title、horizon_ids、requires、condition、time_basis、action、fallback、evidence。from、to 可省略，也可用年份或完整日期。有兑现判断时，outcome 用 achieved 或 not_achieved，另引 outcome_evidence。空路线图写 roadmap_gap。 |
| portfolio、resource_boundary、update_note、revisit | 资源受限时如何取舍、哪些约束未知、这次更新了什么、下次拿到什么材料时查哪些结论。没有可列路线或方向时写 route_gap、candidate_gap。 |

程序检查编号、时间视野、日期、文献版本和引用位置能否对上。遇到缺项或错引时退出并指出问题。是否属于同一实施方式、条件能否比较、两项证据是否独立，仍要按原文复核。成品出来后，先请试读者仅看正文复述两项决定，再逐条回到原件核查。有关阅读评审见[验收说明](reader-review.md)。

## 首次阅读与证据展开

给每个 recommendation.first_read 写一个可选的 title，用目标对象和本次要做的决定命名。同一方向近期试验和未来能力可以有不同标题。mechanism 先交代部件位置或输入与作用过程，分清已有结构和拟改变的因素。comparison 写同条件基准、唯一改变的因素、实际观察和独立参照。控制指令、传感器信号和物理结果各能说明什么，按真实证据解释。decision 写观察到什么就保留、调整、停止或重新研究；只有另一项独立对照能解释的效果，留给那项对照。已有安全限制、互相干扰的试验和失效后的处置放在动作旁。证据缺时指出缺哪一环及对判断的影响。

每个 foresight.horizons 项可填 reader_limit。保留直接影响该组决定的简短限制；如果已在建议旁说明，填空字符串。原有 question.boundary 仍完整存放在相应资料说明里。老数据若未区分两者，保留原边界的可见性。scope_note 汇入研究范围；任何必须提前知晓的条件写进首项建议或 reader_limit。history_boundary 用于日期、分案、资料未入轴等口径，逐件来源连回原文。不要把这些过程再复制进 finding、观察或优先动作。趋势、样本稀疏与工程验证分别表述。

第 3 章先用操作情境说明不同构型如何工作。已有可定位的原图时，可在 foresight.figures 放对象列表。每项含 title、alt、caption、evidence_id、locator 和 image。image 是来自对应原件的 PNG/JPEG/WebP 的 base64 data URI。图注交代观察位置、动作或编号及图能说明的范围。图片不在手或缺少对应关系时用文字说明。技术时间轴根据本次有出处的事件生成，显示日期、类型、主体和事件名称，逐件变化与出处可展开。缺日期的事件单列。

两种时间视野、建议数量、候选名及先后顺序均由当前资料决定。共用方法说明、检索与阅读记录就近折叠。影响当前判断的反证、实际测量与未证实结果的区别、适用和停试条件在默认正文可见。
