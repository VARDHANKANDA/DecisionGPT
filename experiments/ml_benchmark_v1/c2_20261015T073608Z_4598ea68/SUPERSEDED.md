# Superseded

This run used every column of `customers.csv` except the id and target, including `support_tickets` and `discount_usage_rate`, which the
production churn pipeline deliberately excludes (a business cannot supply them at inference). It therefore did not use the same permissible
information as the production model. It is kept unchanged as a record of the first attempt; use the later `c2_*` run
(production `FEATURE_COLUMNS`). Superseded 2026-10-15 by the benchmark author (its figures were seen in the console before the report was finalised, and are not used in docs/ML_BENCHMARK_REPORT.md).
