# 研发罗盘 0.4.0

根据研究目的解释技术现状与演进、探索研发机会或比较路线。使用 `SKILL.md` 作为入口。新增模式、现有路线与候选方向分开、日期类型、多点引用，以及报告和阅读清单的同源生成。

```text
python scripts/render_report.py assets/report-data.v2.example.json --bundle demo
python scripts/render_report.py --check-bundle demo
python -m unittest discover -s tests -v
```

仅依赖 Python 3.10+ 标准库。生成的主报告可单独离线打开，内含逐件清单、证据卡与研究数据。运行检索、原文阅读和内容复核仍由宿主与已授权工具完成；没有额外模型调用。

schema 1 兼容保留；旧格式不自动迁移，以免猜造日期类型和阅读记录。新研究见 references/output-format.md，旧格式见 references/output-format-v1.md。assets/report-data.v2.example.json 和 references/synthetic-demo.json 都是合成演示，不是专利事实。

当前维护版本与基线见 MAINTENANCE.md。修改记录见 CHANGELOG.md。
