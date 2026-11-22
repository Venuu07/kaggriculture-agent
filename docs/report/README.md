# Project report

`Kaggriculture_Major_Project_Report.pdf` is the final report. To rebuild after edits:

```bash
pip install weasyprint
```
```bash
cd docs/report
```
```bash
python build_report.py
```

`build_report.py` needs the screenshots and charts in `img/` (copy them from `docs/img/` and `results/`). Names, guide, dates and all text are at the top of `build_report.py`.
