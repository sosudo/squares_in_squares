# Vendored public source

`unitSquares/` is a minimal unchanged subset of https://github.com/Shubin123/unitSquares at commit `fe423cb11a483504f327ddc8eb251569ead7420d`, retrieved 2026-10-24. It is MIT licensed; the original LICENSE and README are retained. Included: geometry/construction code, submission exporter, public packing data and provenance index. It requires Node.js to generate the baseline; the optional website/Playwright dependencies are not required.

The packing data was merged by that project from public Kaggle notebook outputs. `unitSquares/data/kaggle/index.json` records each puzzle's notebook source. Sources include kirilltym, malyshevdanil and alexchilton; the original README describes their contributions. This is a public baseline, not a claim of original discovery.

The separate repository https://github.com/tiagocabo/kaggle-squares-in-squares at `9f4236dd436cb534aaf65ebd46ee072839976140` was inspected for documentation and a mirror of the competition metric v17. Its implementation is not vendored. The original official competition metric and rules still need to be checked on Kaggle.
