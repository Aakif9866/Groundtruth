# Retrieval Configuration Comparison

Dataset: `synthetic` (version 1.1.0), 100 queries. Deltas are relative to the `baseline` configuration.

## Overall metrics

| configuration   |   chunk_size | retrieval_method   | reranker   | candidate_pool   |   recall@5 |   recall@10 |    mrr |   ndcg@10 |   delta_recall@10 |
|:----------------|-------------:|:-------------------|:-----------|:-----------------|-----------:|------------:|-------:|----------:|------------------:|
| baseline        |          300 | dense              | False      | full             |      0.975 |       0.985 | 0.8228 |    0.859  |             0     |
| chunk_change    |          100 | dense              | False      | full             |      0.985 |       0.99  | 0.779  |    0.8221 |             0.005 |
| hybrid          |          300 | hybrid             | False      | full             |      0.965 |       1     | 0.8658 |    0.8956 |             0.015 |
| reranker        |          300 | dense              | True       | full             |      0.985 |       0.995 | 0.9091 |    0.9279 |             0.01  |
| broken          |           40 | dense              | False      | 3                |      0.015 |       0.015 | 0.02   |    0.0161 |            -0.97  |


## Configuration details

| configuration   |   chunk_size |   chunk_overlap | retrieval_method   | embedding_model                        | reranker                             | candidate_pool   |
|:----------------|-------------:|----------------:|:-------------------|:---------------------------------------|:-------------------------------------|:-----------------|
| baseline        |          300 |              50 | dense              | sentence-transformers/all-MiniLM-L6-v2 | off                                  | full             |
| chunk_change    |          100 |              20 | dense              | sentence-transformers/all-MiniLM-L6-v2 | off                                  | full             |
| hybrid          |          300 |              50 | hybrid             | sentence-transformers/all-MiniLM-L6-v2 | off                                  | full             |
| reranker        |          300 |              50 | dense              | sentence-transformers/all-MiniLM-L6-v2 | cross-encoder/ms-marco-MiniLM-L-6-v2 | full             |
| broken          |           40 |               0 | dense              | sentence-transformers/all-MiniLM-L6-v2 | off                                  | 3                |


## Statistical analysis (paired bootstrap vs. baseline)

A delta is only treated as real when its 95% confidence interval excludes 0.

| candidate    | metric    |   delta | 95% CI           | reading                     |
|:-------------|:----------|--------:|:-----------------|:----------------------------|
| chunk_change | recall@10 |   0.005 | [-0.015, +0.030] | inconclusive: CI includes 0 |
| chunk_change | mrr       |  -0.044 | [-0.105, +0.018] | inconclusive: CI includes 0 |
| chunk_change | ndcg@10   |  -0.037 | [-0.084, +0.011] | inconclusive: CI includes 0 |
| hybrid       | recall@10 |   0.015 | [+0.000, +0.040] | inconclusive: CI includes 0 |
| hybrid       | mrr       |   0.043 | [-0.000, +0.089] | inconclusive: CI includes 0 |
| hybrid       | ndcg@10   |   0.037 | [+0.004, +0.071] | improvement: CI excludes 0  |
| reranker     | recall@10 |   0.01  | [+0.000, +0.030] | inconclusive: CI includes 0 |
| reranker     | mrr       |   0.086 | [+0.034, +0.140] | improvement: CI excludes 0  |
| reranker     | ndcg@10   |   0.069 | [+0.030, +0.109] | improvement: CI excludes 0  |
| broken       | recall@10 |  -0.97  | [-0.995, -0.935] | regression: CI excludes 0   |
| broken       | mrr       |  -0.803 | [-0.860, -0.742] | regression: CI excludes 0   |
| broken       | ndcg@10   |  -0.843 | [-0.888, -0.794] | regression: CI excludes 0   |


## Failure types


### baseline

```
Failure Type                 Count   Percentage
-----------------------------------------------
semantic_mismatch               12          40%
chunk_boundary                   8          27%
ranking_failure                  6          20%
distractor_confusion             2           7%
multi_hop_failure                1           3%
generic_term_collision           1           3%
```

### chunk_change

```
Failure Type                 Count   Percentage
-----------------------------------------------
chunk_boundary                  29          72%
distractor_confusion             4          10%
multi_hop_failure                2           5%
generic_term_collision           2           5%
semantic_mismatch                2           5%
ranking_failure                  1           2%
```

### hybrid

```
Failure Type                 Count   Percentage
-----------------------------------------------
semantic_mismatch                8          35%
ranking_failure                  8          35%
chunk_boundary                   6          26%
distractor_confusion             1           4%
```

### reranker

```
Failure Type                 Count   Percentage
-----------------------------------------------
ranking_failure                  5          31%
chunk_boundary                   4          25%
semantic_mismatch                4          25%
multi_hop_failure                1           6%
generic_term_collision           1           6%
distractor_confusion             1           6%
```

### broken

```
Failure Type                 Count   Percentage
-----------------------------------------------
candidate_pool_limitation       99         100%
```

## Per-category breakdown


### baseline

| category   |   recall@5 |   recall@10 |    mrr |   ndcg@10 |
|:-----------|-----------:|------------:|-------:|----------:|
| overall    |      0.975 |       0.985 | 0.8228 |    0.859  |
| precedent  |      1     |       1     | 0.8667 |    0.9012 |
| statute    |      1     |       1     | 0.8583 |    0.8946 |
| factual    |      0.95  |       0.95  | 0.6833 |    0.7512 |
| multi_hop  |      0.975 |       0.975 | 0.95   |    0.9316 |
| procedural |      0.95  |       1     | 0.7558 |    0.8164 |

### chunk_change

| category   |   recall@5 |   recall@10 |    mrr |   ndcg@10 |
|:-----------|-----------:|------------:|-------:|----------:|
| overall    |      0.985 |        0.99 | 0.779  |    0.8221 |
| precedent  |      1     |        1    | 0.875  |    0.9077 |
| statute    |      1     |        1    | 0.5333 |    0.652  |
| factual    |      1     |        1    | 0.7208 |    0.7924 |
| multi_hop  |      0.925 |        0.95 | 0.9667 |    0.9101 |
| procedural |      1     |        1    | 0.7992 |    0.8483 |

### hybrid

| category   |   recall@5 |   recall@10 |    mrr |   ndcg@10 |
|:-----------|-----------:|------------:|-------:|----------:|
| overall    |      0.965 |           1 | 0.8658 |    0.8956 |
| precedent  |      1     |           1 | 0.975  |    0.9815 |
| statute    |      1     |           1 | 0.8    |    0.8512 |
| factual    |      1     |           1 | 0.7833 |    0.8393 |
| multi_hop  |      0.975 |           1 | 0.95   |    0.9437 |
| procedural |      0.85  |           1 | 0.8205 |    0.862  |

### reranker

| category   |   recall@5 |   recall@10 |    mrr |   ndcg@10 |
|:-----------|-----------:|------------:|-------:|----------:|
| overall    |      0.985 |       0.995 | 0.9091 |    0.9279 |
| precedent  |      1     |       1     | 0.8542 |    0.8912 |
| statute    |      1     |       1     | 0.975  |    0.9815 |
| factual    |      0.95  |       1     | 0.8313 |    0.8735 |
| multi_hop  |      0.975 |       0.975 | 1      |    0.9807 |
| procedural |      1     |       1     | 0.885  |    0.9124 |

### broken

| category   |   recall@5 |   recall@10 |   mrr |   ndcg@10 |
|:-----------|-----------:|------------:|------:|----------:|
| overall    |      0.015 |       0.015 |  0.02 |    0.0161 |
| precedent  |      0.05  |       0.05  |  0.05 |    0.05   |
| statute    |      0     |       0     |  0    |    0      |
| factual    |      0     |       0     |  0    |    0      |
| multi_hop  |      0.025 |       0.025 |  0.05 |    0.0307 |
| procedural |      0     |       0     |  0    |    0      |
