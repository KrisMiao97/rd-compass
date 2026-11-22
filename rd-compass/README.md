# 研发罗盘 0.7.4

预研模板将关键建议、候选机制和观察条件写在对应决定旁。正式报告在第 8 章先给方向判断，在工程试验中集中展示重复的改选条件。旧研究数据可以直接生成报告。

需要新读专利时，罗盘先给出初筛后的清单和每件建议的阅读深度。使用者可以整组确认，也可以只改某件。约定清楚后，由专利阅读 Skill 执行；已指定的安排直接沿用。

当问题是“我们近期先验证什么、中长期提前积累什么”时，使用[未来趋势报告](references/foresight-method.md)。打开[可填写的 13 章网页](assets/foresight/template.html)即可查看各章的问题、证据和案例。

```text
python scripts/render_report.py --foresight-template 填写模板
python scripts/render_report.py assets/foresight/steam-oven.example.json --bundle 预研报告示例
python scripts/render_report.py --check-bundle 预研报告示例
```

内置示例用两件欧洲专利公开文本和一份仪器手册演示限定材料研究。实际项目请[按本项目的事实构建研究数据](references/foresight-format.md)。

根据研究目的解释技术现状与演进、探索研发机会或比较路线。使用 `SKILL.md` 作为入口。0.5.0 增加机会关联、共同情境比较和补证结果分支；保留现有路线与候选方向分开、明确日期类型、多点引用，以及报告和阅读清单的同源生成。

```text
python scripts/render_report.py assets/report-data.v2.example.json --bundle demo
python scripts/render_report.py --check-bundle demo
python -m unittest discover -s tests -v
```

仅依赖 Python 3.10+ 标准库。生成的主报告可单独离线打开，内含逐件清单、证据卡与研究数据。运行检索、原文阅读和内容复核仍由宿主与已授权工具完成；没有额外模型调用。

常规新研究采用 schema 3，首屏建议的原文、同工况对照及淘汰条件见 references/output-format.md。旧 schema 1/2 兼容保留，历史字段按实际读取。上面的 schema 2 示例和 references/synthetic-demo.json 都使用合成资料。

当前维护版本与基线见 MAINTENANCE.md。修改记录见 CHANGELOG.md。

## 机会、共同情境与关键补证

0.5.0 将 IfM、RAND、NASA 的公开方法落实为可选关联视图：机会连接产品能力与技术条件，候选使用共同情境比较，补证列出不同结果如何改变选择。功能分解与形态分析、JTBD、TRIZ、DOE 按问题触发，不默认全部使用。

```text
python scripts/render_report.py assets/report-data.methods.example.json --bundle methods-demo
python scripts/render_report.py references/kettle-method-case.json --bundle kettle-case
```

这些视图展示分析者填写并审核的内容，不执行 RDM 仿真、自动评分或试验。真实案例仅核查两件专利的有限技术内容，见 references/case-review.md。方法来源与实际应用深度可在报告中查看；不表示原机构背书。

本地 0.5.0 基于维护源 0.4.0 升级；未自动发布远端仓库。

## 0.5.1：先补查，再交付可顺读的报告

研究过程主动完成现有授权范围内可取得的关键补查，核查后更新技术解释与判断。新方法研究用 research_check 记录交付前回查，不能把可执行的关键工作留成用户待办。渲染器不代替检索或工程分析。

主报告恢复核心发现、产品与机制、路线差异、研发机会、条件与建议的顺序；已完成补查、台账及方法详情可展开。关键相反结果直接显示，旧数据的原文和关联仍保留。水壶示例重写了背景与结论标题，并将已完成的连接对象核查落实到正文；未做真实用户试用或性能试验。

本地 0.5.1 基于已保留的本地 0.5.0 升级，维护源仍为 0.4.0，未推送远端。

## 0.5.2：恢复技术时间图

在产品背景之后、现有路线之前，保留原有按日期排列的技术卡片和目录入口。水壶示例补入两件文献已核验的公开／授权事件；事件先后不代表技术继承或上市。精简报告时保留已有可靠节点，未知日期继续主动核查或说明缺口。

本地 0.5.2 保留 0.5.1 的阅读层级与主动补证要求，尚未发布远端。

## 0.5.3：条件判断与技术时间图

首屏的条件判断直接说明路线取舍，技术时间图用简短特点概括节点，并可直达对应路线和证据。现行阅读与补证规则见 DESIGN.md。
