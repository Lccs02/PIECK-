from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent

CASES = {
    "01_noattack_nodefense": ("NoAttack", "NoDefense"),
    "02_pieckipe_nodefense": ("PIECK-IPE", "NoDefense"),
    "03_pieckuea_nodefense": ("PIECK-UEA", "NoDefense"),
    "04_pieckipe_regula": ("PIECK-IPE", "Regula"),
    "05_pieckuea_regula": ("PIECK-UEA", "Regula"),
}

PAPER = {
    "01_noattack_nodefense": {"er10": 0.23, "hr10": 57.16, "table": "Table III"},
    "02_pieckipe_nodefense": {"er10": 87.47, "hr10": 57.69, "table": "Table III"},
    "03_pieckuea_nodefense": {"er10": 93.39, "hr10": 57.69, "table": "Table III"},
    "04_pieckipe_regula": {"er10": 1.25, "hr10": 56.31, "table": "Table IV"},
    "05_pieckuea_regula": {"er10": 0.00, "hr10": 55.89, "table": "Table IV"},
}

ITER_RE = re.compile(
    r"Iteration\s+(?P<epoch>\d+)"
    r"(?:\(init\)|,\s+Round\s+(?P<round>\d+),\s+loss\s+=\s+(?P<loss>-?[0-9.]+)\s+\[[^]]+\])?"
    r",\s+\((?P<hr5>[0-9.]+),\s+(?P<hr10>[0-9.]+),\s+(?P<hr20>[0-9.]+)\)\s+on test"
    r",\s+\((?P<er5>[0-9.]+),\s+(?P<er10>[0-9.]+),\s+(?P<er20>[0-9.]+)\)\s+on target\."
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Parse PIECK MF-FRS logs into CSV summaries and figures."
    )
    parser.add_argument(
        "--results-dir",
        default="results",
        help="Directory containing logs/ and receiving data/ and figures/. Default: results",
    )
    parser.add_argument(
        "--expected-epochs",
        type=int,
        default=300,
        help="Expected final epoch in each log. Default: 300",
    )
    return parser.parse_args()


def resolve_results_dir(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = ROOT / path
    return path


def read_log(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-16", "gb18030"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def parse_log(case_id: str, path: Path, expected_epochs: int) -> list[dict[str, object]]:
    text = read_log(path)
    if "Traceback (most recent call last)" in text:
        raise RuntimeError(f"Traceback found in {path}")

    attack, defense = CASES[case_id]
    rows: list[dict[str, object]] = []
    for match in ITER_RE.finditer(text):
        values = match.groupdict()
        row: dict[str, object] = {
            "case_id": case_id,
            "attack": attack,
            "defense": defense,
            "epoch": int(values["epoch"]),
            "round": int(values["round"]) if values["round"] else 0,
            "loss": float(values["loss"]) if values["loss"] else "",
        }
        for key in ("hr5", "hr10", "hr20", "er5", "er10", "er20"):
            row[key] = float(values[key]) * 100.0
        rows.append(row)

    expected_rows = expected_epochs + 1
    if not rows or rows[-1]["epoch"] != expected_epochs:
        raise RuntimeError(f"{path.name} did not reach Iteration {expected_epochs}")
    if len(rows) != expected_rows:
        raise RuntimeError(f"{path.name} expected {expected_rows} metric rows, got {len(rows)}")
    return rows


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def make_plots(all_rows: list[dict[str, object]], figures_dir: Path) -> None:
    import matplotlib.pyplot as plt

    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    figures_dir.mkdir(parents=True, exist_ok=True)

    colors = {
        "01_noattack_nodefense": "#4B5563",
        "02_pieckipe_nodefense": "#E67E22",
        "03_pieckuea_nodefense": "#C0392B",
        "04_pieckipe_regula": "#2E86C1",
        "05_pieckuea_regula": "#16A085",
    }
    grouped = {case_id: [row for row in all_rows if row["case_id"] == case_id] for case_id in CASES}

    for metric, title, ylabel, filename in (
        ("loss", "训练 Loss 曲线", "Loss", "loss_curves.png"),
        ("hr10", "推荐性能 HR@10", "HR@10 (%)", "hr10_curves.png"),
        ("er10", "目标物品曝光率 ER@10", "ER@10 (%)", "er10_curves.png"),
    ):
        fig, ax = plt.subplots(figsize=(10.5, 5.2), dpi=180)
        for case_id, rows in grouped.items():
            rows_for_plot = rows[1:] if metric == "loss" else rows
            x = [int(row["epoch"]) for row in rows_for_plot]
            y = [float(row[metric]) for row in rows_for_plot]
            attack, defense = CASES[case_id]
            ax.plot(
                x,
                y,
                label=f"{attack} + {defense}",
                linewidth=1.7,
                color=colors[case_id],
            )
        ax.set_title(title, fontsize=15, fontweight="bold")
        ax.set_xlabel("Epoch")
        ax.set_ylabel(ylabel)
        ax.grid(True, alpha=0.22)
        ax.legend(fontsize=8.5, ncol=2, frameon=False)
        if metric in {"hr10", "er10"}:
            ax.set_ylim(0, 105)
        fig.tight_layout()
        fig.savefig(figures_dir / filename, bbox_inches="tight")
        plt.close(fig)


def build_summary(finals: list[dict[str, object]], comparison: list[dict[str, object]], rows: int) -> dict[str, object]:
    uea_attack_er = float(next(row for row in finals if row["case_id"] == "03_pieckuea_nodefense")["er10"])
    uea_defense_er = float(next(row for row in finals if row["case_id"] == "05_pieckuea_regula")["er10"])
    return {
        "rows": rows,
        "runs": len(finals),
        "all_reached_epoch_300": True,
        "pieckuea_attack_effective": bool(uea_attack_er > 50),
        "regula_uea_substantially_reduces_er": bool(uea_defense_er <= 0.2 * uea_attack_er),
        "regula_uea_below_10pct": bool(uea_defense_er < 10),
        "all_metrics_within_5pp": all(bool(row["within_5pp_both"]) for row in comparison),
    }


def main() -> None:
    args = parse_args()
    results_dir = resolve_results_dir(args.results_dir)
    logs_dir = results_dir / "logs"
    data_dir = results_dir / "data"
    figures_dir = results_dir / "figures"
    data_dir.mkdir(parents=True, exist_ok=True)

    all_rows: list[dict[str, object]] = []
    for case_id in CASES:
        log_path = logs_dir / f"{case_id}.log"
        if not log_path.exists():
            raise FileNotFoundError(log_path)
        all_rows.extend(parse_log(case_id, log_path, args.expected_epochs))

    fields = ["case_id", "attack", "defense", "epoch", "round", "loss", "hr5", "hr10", "hr20", "er5", "er10", "er20"]
    write_csv(data_dir / "metrics_by_epoch.csv", all_rows, fields)

    finals = [row for row in all_rows if row["epoch"] == args.expected_epochs]
    write_csv(data_dir / "final_metrics.csv", finals, fields)

    comparison: list[dict[str, object]] = []
    for row in finals:
        case_id = str(row["case_id"])
        paper = PAPER[case_id]
        er_gap = float(row["er10"]) - paper["er10"]
        hr_gap = float(row["hr10"]) - paper["hr10"]
        comparison.append(
            {
                "case_id": case_id,
                "attack": row["attack"],
                "defense": row["defense"],
                "paper_table": paper["table"],
                "reproduced_er10": round(float(row["er10"]), 4),
                "paper_er10": paper["er10"],
                "er10_gap_pp": round(er_gap, 4),
                "reproduced_hr10": round(float(row["hr10"]), 4),
                "paper_hr10": paper["hr10"],
                "hr10_gap_pp": round(hr_gap, 4),
                "within_5pp_both": abs(er_gap) <= 5.0 and abs(hr_gap) <= 5.0,
            }
        )
    write_csv(data_dir / "paper_comparison.csv", comparison, list(comparison[0].keys()))

    summary = build_summary(finals, comparison, len(all_rows))
    (data_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    make_plots(all_rows, figures_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
