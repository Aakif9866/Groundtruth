"""Human-readable reports: comparison markdown/CSV, per-run report, HTML dashboard.

The dashboard is a single self-contained HTML file (inline CSS and inline SVG,
no JavaScript, no CDN) so it opens offline and diffs cleanly.
"""
from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

import pandas as pd

from src.evaluation.compare import compare_results
from src.evaluation.error_analysis import (
    FailureRecord, aggregate_failure_types, analyze_queries, format_summary_table,
)
from src.evaluation.evaluate import build_category_breakdown, build_comparison
from src.evaluation.statistics import BootstrapResult
from src.retrieval.configs import BASELINE_CONFIG_NAME
from src.retrieval.retriever import Retriever

METRIC_COLUMNS = ["recall@5", "recall@10", "mrr", "ndcg@10"]
CHART_COLORS = {"recall@10": "#2a6f97", "mrr": "#e07a1f", "ndcg@10": "#5b8c5a"}


def config_details(results: dict[str, dict]) -> pd.DataFrame:
    """One row per configuration with the settings that produced its numbers."""
    rows = []
    for name, res in results.items():
        c = res["config"]
        rows.append({
            "configuration": name,
            "chunk_size": c["chunk_size"],
            "chunk_overlap": c["chunk_overlap"],
            "retrieval_method": c["method"],
            "embedding_model": c.get("embedding_model"),
            "reranker": c.get("reranker_model") if c["reranker"] else "off",
            "candidate_pool": c.get("candidate_pool") or "full",
        })
    return pd.DataFrame(rows)


def failure_summaries(results: dict[str, dict], corpus: list[dict], golden: list[dict]) -> dict[str, list[tuple[str, int, float]]]:
    """Failure-type distribution per configuration, reusing already computed retrieval."""
    out = {}
    for name, res in results.items():
        retriever = Retriever(corpus, name, config=res["config"])
        retrieved = {q["query_id"]: q["retrieved"] for q in res["per_query"]}
        records, _ = analyze_queries(retriever, corpus, golden, retrieved=retrieved)
        out[name] = aggregate_failure_types(records)
    return out


def stats_versus_baseline(results: dict[str, dict], baseline: str = BASELINE_CONFIG_NAME) -> dict[str, dict[str, BootstrapResult]]:
    """Paired bootstrap of each non-baseline config against the baseline."""
    return {n: compare_results(results[baseline], r) for n, r in results.items() if n != baseline}


def _stats_frame(stats: dict[str, dict[str, BootstrapResult]]) -> pd.DataFrame:
    rows = []
    for name, per_metric in stats.items():
        for metric, r in per_metric.items():
            rows.append({
                "candidate": name, "metric": metric, "delta": f"{r.delta:+.3f}",
                "95% CI": f"[{r.ci_low:+.3f}, {r.ci_high:+.3f}]", "reading": r.verdict,
            })
    return pd.DataFrame(rows)


def render_comparison_markdown(results: dict[str, dict], dataset: str, dataset_version: str, n_queries: int,
                               failures: dict[str, list], stats: dict[str, dict[str, BootstrapResult]]) -> str:
    """Comparison report covering metrics, deltas, categories, statistics, errors, and config details."""
    comparison = build_comparison(results)
    category = build_category_breakdown(results)
    lines = [
        "# Retrieval Configuration Comparison\n",
        f"Dataset: `{dataset}` (version {dataset_version}), {n_queries} queries. "
        f"Deltas are relative to the `{BASELINE_CONFIG_NAME}` configuration.\n",
        "## Overall metrics\n", comparison.to_markdown(index=False),
        "\n\n## Configuration details\n", config_details(results).to_markdown(index=False),
        "\n\n## Statistical analysis (paired bootstrap vs. baseline)\n",
        "A delta is only treated as real when its 95% confidence interval excludes 0.\n",
    ]
    lines.append(_stats_frame(stats).to_markdown(index=False) if stats else "_No candidate configurations._")
    lines.append("\n\n## Failure types\n")
    for name, rows in failures.items():
        lines += [f"\n### {name}\n", "```", format_summary_table(rows) if rows else "no imperfect queries", "```"]
    lines.append("\n## Per-category breakdown\n")
    for name in comparison["configuration"]:
        sub = category[category["configuration"] == name].drop(columns=["configuration"])
        lines += [f"\n### {name}\n", sub.to_markdown(index=False)]
    return "\n".join(lines) + "\n"


def _svg_grouped_bars(comparison: pd.DataFrame) -> str:
    names = list(comparison["configuration"])
    metrics = ["recall@10", "mrr", "ndcg@10"]
    width, height, pad_l, pad_b, pad_t = 760, 300, 40, 50, 20
    plot_h = height - pad_b - pad_t
    group_w = (width - pad_l - 10) / max(len(names), 1)
    bar_w = group_w / (len(metrics) + 1)
    parts = [f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="Metrics by configuration" class="chart">']
    for frac in (0, 0.25, 0.5, 0.75, 1.0):
        y = pad_t + plot_h * (1 - frac)
        parts.append(f'<line x1="{pad_l}" x2="{width-10}" y1="{y:.1f}" y2="{y:.1f}" class="grid"/>')
        parts.append(f'<text x="{pad_l-6}" y="{y+4:.1f}" text-anchor="end" class="tick">{frac:.2f}</text>')
    for i, name in enumerate(names):
        gx = pad_l + i * group_w
        for j, m in enumerate(metrics):
            val = float(comparison.iloc[i][m])
            h = plot_h * val
            x = gx + bar_w * (j + 0.5)
            y = pad_t + plot_h - h
            parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w*0.9:.1f}" height="{h:.1f}" fill="{CHART_COLORS[m]}">'
                         f'<title>{html.escape(name)} {m}: {val:.3f}</title></rect>')
        parts.append(f'<text x="{gx+group_w/2:.1f}" y="{height-pad_b+18}" text-anchor="middle" class="tick">{html.escape(name)}</text>')
    parts.append("</svg>")
    legend = "".join(f'<span class="key"><i style="background:{c}"></i>{m}</span>' for m, c in CHART_COLORS.items())
    return "".join(parts) + f'<div class="legend">{legend}</div>'


def _html_table(df: pd.DataFrame) -> str:
    return df.to_html(index=False, border=0, escape=True, classes="tbl")


def _failure_bars(rows: list[tuple[str, int, float]]) -> str:
    if not rows:
        return "<p>No imperfect queries.</p>"
    items = "".join(
        f'<div class="frow"><span class="fname">{html.escape(t)}</span>'
        f'<span class="fbar"><b style="width:{pct:.0f}%"></b></span><span class="fnum">{n} ({pct:.0f}%)</span></div>'
        for t, n, pct in rows)
    return f'<div class="fail">{items}</div>'


DASHBOARD_CSS = """
:root{--bg:#fff;--fg:#1c2530;--muted:#5d6b7a;--line:#dde3ea;--card:#f6f8fa}
@media(prefers-color-scheme:dark){:root{--bg:#12171d;--fg:#e6ebf0;--muted:#9aa7b4;--line:#2a343f;--card:#1a212a}}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
main{max-width:980px;margin:0 auto;padding:24px 16px 48px}
h1{font-size:24px;margin:0 0 4px}h2{font-size:18px;margin:32px 0 8px}h3{font-size:15px;margin:16px 0 6px}
.sub{color:var(--muted);margin:0 0 16px}
.tbl{border-collapse:collapse;width:100%;font-size:13px;background:var(--card)}
.tbl th,.tbl td{padding:6px 10px;border-bottom:1px solid var(--line);text-align:right}
.tbl th:first-child,.tbl td:first-child{text-align:left}
.scroll{overflow-x:auto}
.chart{width:100%;height:auto}.grid{stroke:var(--line)}.tick{fill:var(--muted);font-size:11px}
.legend{display:flex;gap:16px;font-size:13px;color:var(--muted);margin-top:4px}
.key i{display:inline-block;width:10px;height:10px;margin-right:6px;border-radius:2px}
.fail{font-size:13px}.frow{display:flex;align-items:center;gap:8px;margin:2px 0}
.fname{width:190px}.fbar{flex:1;background:var(--card);height:10px;border-radius:3px;overflow:hidden}
.fbar b{display:block;height:100%;background:#c0563b}.fnum{width:80px;text-align:right;color:var(--muted)}
"""


def render_dashboard_html(results: dict[str, dict], dataset: str, dataset_version: str, n_queries: int,
                          failures: dict[str, list], stats: dict[str, dict[str, BootstrapResult]]) -> str:
    """Self-contained HTML dashboard."""
    comparison = build_comparison(results)
    category = build_category_breakdown(results)
    cat_tables = "".join(
        f"<h3>{html.escape(n)}</h3><div class='scroll'>{_html_table(category[category['configuration']==n].drop(columns=['configuration']))}</div>"
        for n in comparison["configuration"])
    fail_blocks = "".join(f"<h3>{html.escape(n)}</h3>{_failure_bars(r)}" for n, r in failures.items())
    stats_html = _html_table(_stats_frame(stats)) if stats else "<p>No candidate configurations.</p>"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Groundtruth Evaluation Dashboard</title><style>{DASHBOARD_CSS}</style></head><body><main>
<h1>Groundtruth evaluation dashboard</h1>
<p class="sub">Dataset <b>{html.escape(dataset)}</b> v{html.escape(dataset_version)} &middot; {n_queries} queries &middot; deltas vs. <b>{BASELINE_CONFIG_NAME}</b></p>
<h2>Overall metrics</h2>{_svg_grouped_bars(comparison)}
<div class="scroll">{_html_table(comparison)}</div>
<h2>Configuration details</h2><div class="scroll">{_html_table(config_details(results))}</div>
<h2>Statistical analysis (paired bootstrap, 95% CI)</h2>
<p class="sub">A difference counts only if the interval excludes 0.</p><div class="scroll">{stats_html}</div>
<h2>Failure types</h2>{fail_blocks}
<h2>Per-category breakdown</h2>{cat_tables}
</main></body></html>
"""


def build_summary(results: dict[str, dict], dataset: str, dataset_version: str, n_queries: int,
                  failures: dict[str, list], stats: dict[str, dict[str, BootstrapResult]]) -> dict[str, Any]:
    """Machine-readable summary (used by the web UI): metrics, config details, statistics, failure types."""
    details = config_details(results).set_index("configuration").to_dict("index")
    return {
        "dataset": dataset,
        "dataset_version": dataset_version,
        "query_count": n_queries,
        "baseline": BASELINE_CONFIG_NAME,
        "configs": {
            name: {"details": details[name], "metrics": res["metrics"]} for name, res in results.items()
        },
        "stats": {
            cand: {m: {"delta": r.delta, "ci_low": r.ci_low, "ci_high": r.ci_high, "ci_level": r.ci_level,
                       "verdict": r.verdict} for m, r in per_metric.items()}
            for cand, per_metric in stats.items()
        },
        "failures": {
            name: [{"type": t, "count": n, "percent": round(pct, 1)} for t, n, pct in rows]
            for name, rows in failures.items()
        },
    }


def write_comparison_reports(results: dict[str, dict], corpus: list[dict], golden: list[dict], dataset: str,
                             dataset_version: str, out_dir: Path) -> None:
    """Write comparison.md, comparison.csv, summary.json and dashboard.html into ``out_dir``."""
    out_dir.mkdir(parents=True, exist_ok=True)
    failures = failure_summaries(results, corpus, golden)
    stats = stats_versus_baseline(results)
    comparison = build_comparison(results)
    extras = config_details(results).drop(columns=["chunk_size", "retrieval_method", "candidate_pool"]).rename(
        columns={"reranker": "reranker_model"})
    comparison.merge(extras, on="configuration").assign(dataset=dataset, dataset_version=dataset_version).to_csv(
        out_dir / "comparison.csv", index=False)
    (out_dir / "comparison.md").write_text(
        render_comparison_markdown(results, dataset, dataset_version, len(golden), failures, stats))
    (out_dir / "summary.json").write_text(json.dumps(
        build_summary(results, dataset, dataset_version, len(golden), failures, stats), indent=2, default=str))
    (out_dir / "dashboard.html").write_text(
        render_dashboard_html(results, dataset, dataset_version, len(golden), failures, stats))


def render_run_report(meta: dict[str, Any], failure_rows: list[tuple[str, int, float]]) -> str:
    """Markdown report for a single experiment run."""
    cfg, m = meta["config"], meta["metrics"]
    overall = m["overall"]
    lines = [
        f"# Run report: {meta['experiment_name']}\n",
        f"- Run ID: `{meta['run_id']}`", f"- Timestamp (UTC): {meta['timestamp']}",
        f"- Dataset: `{meta['dataset']}` v{meta['dataset_version']} ({meta['query_count']} queries)\n",
        "## Configuration\n",
        f"- Retrieval method: {cfg['method']}", f"- Chunk size / overlap: {cfg['chunk_size']} / {cfg['chunk_overlap']}",
        f"- Candidate pool: {cfg.get('candidate_pool') or 'full'}", f"- Embedding model: {cfg.get('embedding_model')}",
        f"- Reranker: {cfg.get('reranker_model') or 'off'}\n",
        "## Overall metrics\n",
        "| Recall@5 | Recall@10 | MRR | nDCG@10 |", "|---:|---:|---:|---:|",
        f"| {overall['recall@5']:.3f} | {overall['recall@10']:.3f} | {overall['mrr']:.3f} | {overall['ndcg@10']:.3f} |\n",
        "## By category\n", "| Category | Recall@10 | MRR | nDCG@10 |", "|---|---:|---:|---:|",
    ]
    lines += [f"| {c} | {v['recall@10']:.3f} | {v['mrr']:.3f} | {v['ndcg@10']:.3f} |" for c, v in m.items() if c != "overall"]
    lines += ["", "## Failure types\n", "```", format_summary_table(failure_rows) if failure_rows else "no imperfect queries", "```", ""]
    return "\n".join(lines)
