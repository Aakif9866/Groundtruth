# Retrieval Configuration Comparison

Dataset: `real_world` (version 1.0.0), 19 queries. Deltas are relative to the `baseline` configuration.

## Overall metrics

| configuration   |   chunk_size | retrieval_method   | reranker   | candidate_pool   |   recall@5 |   recall@10 |    mrr |   ndcg@10 |   delta_recall@10 |
|:----------------|-------------:|:-------------------|:-----------|:-----------------|-----------:|------------:|-------:|----------:|------------------:|
| baseline        |          300 | dense              | False      | full             |     1      |      1      | 0.9737 |    0.9741 |            0      |
| chunk_change    |          100 | dense              | False      | full             |     1      |      1      | 0.8772 |    0.9108 |            0      |
| hybrid          |          300 | hybrid             | False      | full             |     1      |      1      | 0.9737 |    0.9764 |            0      |
| reranker        |          300 | dense              | True       | full             |     1      |      1      | 1      |    1      |            0      |
| broken          |           40 | dense              | False      | 3                |     0.0526 |      0.0526 | 0.0526 |    0.0526 |           -0.9474 |


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
| chunk_change | recall@10 |   0     | [+0.000, +0.000] | inconclusive: CI includes 0 |
| chunk_change | mrr       |  -0.096 | [-0.211, +0.000] | inconclusive: CI includes 0 |
| chunk_change | ndcg@10   |  -0.063 | [-0.137, +0.000] | inconclusive: CI includes 0 |
| hybrid       | recall@10 |   0     | [+0.000, +0.000] | inconclusive: CI includes 0 |
| hybrid       | mrr       |   0     | [+0.000, +0.000] | inconclusive: CI includes 0 |
| hybrid       | ndcg@10   |   0.002 | [-0.013, +0.019] | inconclusive: CI includes 0 |
| reranker     | recall@10 |   0     | [+0.000, +0.000] | inconclusive: CI includes 0 |
| reranker     | mrr       |   0.026 | [+0.000, +0.079] | inconclusive: CI includes 0 |
| reranker     | ndcg@10   |   0.026 | [+0.000, +0.071] | inconclusive: CI includes 0 |
| broken       | recall@10 |  -0.947 | [-1.000, -0.842] | regression: CI excludes 0   |
| broken       | mrr       |  -0.921 | [-1.000, -0.789] | regression: CI excludes 0   |
| broken       | ndcg@10   |  -0.921 | [-1.000, -0.797] | regression: CI excludes 0   |


## Failure types


### baseline

```
Failure Type                 Count   Percentage
-----------------------------------------------
chunk_boundary                   1         100%
```

### chunk_change

```
Failure Type                 Count   Percentage
-----------------------------------------------
semantic_mismatch                1          25%
generic_term_collision           1          25%
distractor_confusion             1          25%
chunk_boundary                   1          25%
```

### hybrid

```
Failure Type                 Count   Percentage
-----------------------------------------------
chunk_boundary                   1         100%
```

### reranker

```
no imperfect queries
```

### broken

```
Failure Type                 Count   Percentage
-----------------------------------------------
candidate_pool_limitation       18         100%
```

## Per-category breakdown


### baseline

| category   |   recall@5 |   recall@10 |    mrr |   ndcg@10 |
|:-----------|-----------:|------------:|-------:|----------:|
| overall    |          1 |           1 | 0.9737 |    0.9741 |
| precedent  |          1 |           1 | 0.9375 |    0.9539 |
| statute    |          1 |           1 | 1      |    1      |
| procedural |          1 |           1 | 1      |    1      |
| factual    |          1 |           1 | 1      |    1      |
| multi_hop  |          1 |           1 | 1      |    0.9591 |

### chunk_change

| category   |   recall@5 |   recall@10 |    mrr |   ndcg@10 |
|:-----------|-----------:|------------:|-------:|----------:|
| overall    |          1 |           1 | 0.8772 |    0.9108 |
| precedent  |          1 |           1 | 0.875  |    0.9077 |
| statute    |          1 |           1 | 1      |    1      |
| procedural |          1 |           1 | 0.6667 |    0.75   |
| factual    |          1 |           1 | 1      |    1      |
| multi_hop  |          1 |           1 | 0.7778 |    0.8479 |

### hybrid

| category   |   recall@5 |   recall@10 |    mrr |   ndcg@10 |
|:-----------|-----------:|------------:|-------:|----------:|
| overall    |          1 |           1 | 0.9737 |    0.9764 |
| precedent  |          1 |           1 | 0.9375 |    0.9539 |
| statute    |          1 |           1 | 1      |    1      |
| procedural |          1 |           1 | 1      |    1      |
| factual    |          1 |           1 | 1      |    1      |
| multi_hop  |          1 |           1 | 1      |    0.9732 |

### reranker

| category   |   recall@5 |   recall@10 |   mrr |   ndcg@10 |
|:-----------|-----------:|------------:|------:|----------:|
| overall    |          1 |           1 |     1 |         1 |
| precedent  |          1 |           1 |     1 |         1 |
| statute    |          1 |           1 |     1 |         1 |
| procedural |          1 |           1 |     1 |         1 |
| factual    |          1 |           1 |     1 |         1 |
| multi_hop  |          1 |           1 |     1 |         1 |

### broken

| category   |   recall@5 |   recall@10 |    mrr |   ndcg@10 |
|:-----------|-----------:|------------:|-------:|----------:|
| overall    |     0.0526 |      0.0526 | 0.0526 |    0.0526 |
| precedent  |     0.125  |      0.125  | 0.125  |    0.125  |
| statute    |     0      |      0      | 0      |    0      |
| procedural |     0      |      0      | 0      |    0      |
| factual    |     0      |      0      | 0      |    0      |
| multi_hop  |     0      |      0      | 0      |    0      |
