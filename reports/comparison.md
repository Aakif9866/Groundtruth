# Retrieval Configuration Comparison

Overall metrics, deltas relative to the `baseline` configuration:

| configuration   |   chunk_size | retrieval_method   | reranker   | candidate_pool   |   recall@5 |   recall@10 |    mrr |   ndcg@10 |   delta_recall@10 |
|:----------------|-------------:|:-------------------|:-----------|:-----------------|-----------:|------------:|-------:|----------:|------------------:|
| baseline        |          300 | dense              | False      | full             |      0.975 |       0.985 | 0.8228 |    0.859  |             0     |
| chunk_change    |          100 | dense              | False      | full             |      0.985 |       0.99  | 0.779  |    0.8221 |             0.005 |
| hybrid          |          300 | hybrid             | False      | full             |      0.965 |       1     | 0.8658 |    0.8956 |             0.015 |
| reranker        |          300 | dense              | True       | full             |      0.985 |       0.995 | 0.9091 |    0.9279 |             0.01  |
| broken          |           40 | dense              | False      | 3                |      0.015 |       0.015 | 0.02   |    0.0161 |            -0.97  |


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
