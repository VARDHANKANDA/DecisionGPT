# RESEARCH_QUESTION_AND_CONTRIBUTIONS

## Question retained, but narrowed

The candidate question in the brief — "when and why do ML retail-demand forecasts outperform strong simple baselines, and how do loss functions and aggregation levels affect that comparison?" — is **kept only in a narrowed form**, because the literature review (`LITERATURE_REVIEW.md`) shows that the second half is established theory (Gneiting 2011; Kolassa 2016, 2020; Prestwich et al. 2014; Hyndman & Koehler 2006; the temporal/cross-sectional hierarchy literature). A study cannot claim novelty for the *existence* of loss- and aggregation-dependence.

**Primary question (see `EXPERIMENT_PROTOCOL.md` §1).** Under endpoint-matched validation selection and never-scored evaluation windows, does a boosted model beat the best simple baseline on item-day pooled WAPE and on subset-day aggregate WAPE; how large is the difference with dependence-aware uncertainty; does the original v1 negative result survive when median-type objectives are in the candidate set; and does the answer replicate across stores, horizons and windows?

**Primary hypothesis.** H1 (item-day, model vs best matched baseline) per cell on W2; H3 (aggregate endpoint) and H2 (objective effect) are the key secondary hypotheses.

## What is established, tested, and unknown

| | content |
|---|---|
| **Established** | the optimal point forecast depends on the scoring function; absolute error ↔ median, squared error ↔ mean; conventional measures can mis-rank intermittent-demand forecasters; boosted trees are strong on M5 and Kaggle retail data; temporal/cross-sectional aggregation changes forecasting problems |
| **Tested here** | size, location (segments, datasets, horizons) and replication of the item-day vs aggregate difference between validation-selected boosted models and a large prespecified baseline set, under a written freeze, with paired two-way dependence-aware inference |
| **What the results will establish** | for these three M5 stores and one retail wholesaler, these windows, these model families and objectives: whether H1/H3 hold, by how much, and with what uncertainty |
| **Unknown after the study** | generalisation to other data, categories, horizons, deep/foundation/probabilistic models, other metrics (scaled, probabilistic), decision-cost objectives, causal effects of features |

## Contribution classification

Incremental empirical contribution (structured replication-extension of established theory on public data), with reproducible code and stored predictions where the data licence allows. **Not** a new method, metric or theorem. If the confirmatory results merely re-confirm the theoretical expectation, the manuscript will say so and position itself as a careful empirical illustration or reproducibility-oriented evaluation, and a venue is chosen accordingly.

## What would change the framing

* If median-type models beat strong baselines at the item-day endpoint across most confirmatory cells **and** mean-type models win the aggregate endpoint: the contribution is the quantified endpoint dependence and the demonstration that the v1 deficit was an objective–metric mismatch (still established in principle).
* If median-type boosted models still lose to simple baselines: the contribution is the stronger negative result (baseline strength on sparse demand) and the mismatch explanation is rejected for these data.
* If results are inconclusive or mixed: reported as such; no additional model search is added to rescue the result.
