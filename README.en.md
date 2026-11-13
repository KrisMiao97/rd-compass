# R&D Compass · 研发罗盘

[简体中文](README.md) · English · **v0.4.0**

**Explain why a product needs a technology, how existing approaches work and evolve, and which product changes are worth investigating.** Choose a report structure that fits the research question.

[Download WorkBuddy v0.4.0](workbuddy/rd-compass-workbuddy-0.4.0.zip?raw=1) · [Download the offline demo](docs/rd-compass-synthetic-demo.zip?raw=1) · [View the new synthetic input](rd-compass/assets/report-data.v2.example.json)

## Three research purposes

| Purpose | Main questions |
|---|---|
| Technical understanding and evolution | Product context, problems, dated disclosures, mechanisms and changes |
| R&D opportunity exploration | Proposed capabilities, comparisons, costs and conditions |
| Route comparison and project preparation | Trade-offs under stated goals and constraints, with a plan when requested |

Modes can be combined. Existing approaches and future opportunities are distinct, linked concepts. Research priority and a comparison baseline do not mean superior measured performance. A technical explanation does not automatically become a test assignment.

## A fictional demo

[![A synthetic filter-maintenance report with context, approaches, opportunities and evidence.](docs/preview.png)](docs/rd-compass-synthetic-demo.zip?raw=1)

Fixed and removable connections illustrate how maintenance access differs. All sources, identifiers and dates are fictional. Unzip and open `index.html` to explore the Chinese-language report without an account, API key or Python. The earlier humidifier input remains available for compatibility checks.

## What's new

- Purpose-aware report order; existing approaches and candidate opportunities are linked separately.
- Explicit event dates and types; time order does not imply inheritance or adoption.
- Separate reading, review and card associations, with multiple locations in one source.
- A report, reading catalog, CSV, research data and hash manifest generated from one input.
- Content review separated from structural checks; schema 1 remains supported without fabricated migration data.

## Get started

Install the [rd-compass](rd-compass/) folder in an Agent Skills host. For WorkBuddy, upload the v0.4.0 ZIP through **Add skill → Upload skill**; see [update instructions](workbuddy/UPDATE.md). The [existing WorkBuddy sharing page](https://www.workbuddy.cn/share/asset?shareCode=esemC6pAN0SejrTocd72G5&sig=wvpo9epwGbdBVx04) is retained; publishing this package does not update that listing automatically.

Use the skill independently or reuse records from [Patent Perspectives](https://github.com/KrisMiao97/patent-perspectives) or patent-batch-reader. Real research uses your material and authorized data sources. Instructions and report text are primarily Chinese; the WorkBuddy entry has bilingual discovery metadata.

Python 3.10+, standard library only:

```sh
python rd-compass/scripts/render_report.py rd-compass/assets/report-data.v2.example.json --bundle demo
python rd-compass/scripts/render_report.py --check-bundle demo
python -m unittest discover -s rd-compass/tests -v
python scripts/package_release.py
```

32 automated tests pass. Offline reports were checked at five viewport widths. The WorkBuddy ZIP is checked by extraction and execution, not by claiming a completed client import. These checks do not validate patent facts or prove a source was read.

[Changelog](CHANGELOG.md) · [Data format](rd-compass/references/output-format.md) · [WorkBuddy listing copy](workbuddy/marketplace-copy.md)
