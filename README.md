# PIECK Reproduction (MF-FRS / ML-100K)

This repository contains a reproducible PyTorch implementation package for the
PIECK experiment used in the course report
`机器学习与安全_PIECK_课程完整实验报告_程硕.docx`.

The reproduced paper is:

> Jun Zhang, Huan Li, Dazhong Rong, Yan Zhao, Ke Chen, and Lidan Shou.
> Preventing the Popular Item Embedding Based Attack in Federated Recommendations.
> IEEE ICDE 2024.

The repository focuses on the MF-FRS setting with the ML-100K dataset. It keeps
the original reproduction code structure under `MF-FRS/`, adds a Python
experiment runner, and includes the logs, CSV summaries, and figures used by the
final course report.

## Repository Structure

```text
.
├── MF-FRS/                  # Matrix-factorization federated recommender code
│   ├── main.py              # Single-run training entry
│   ├── attack.py            # PIECK-IPE and PIECK-UEA attack logic
│   ├── client.py            # Normal clients and Regula client-side defense
│   ├── server.py            # Federated item-embedding aggregation
│   └── Data/ML-100K/        # Preprocessed ML-100K split used by the run
├── run_experiments.py       # Python runner for the five report experiments
├── parse_results.py         # Log parser, CSV summarizer, and figure generator
├── requirements.txt         # Tested Python package versions
└── results/
    ├── logs/                # Full training logs for the five 300-epoch runs
    ├── data/                # Parsed metrics and paper-comparison tables
    ├── figures/             # ER@10, HR@10, and loss curves
    ├── environment.txt      # Recorded hardware/software environment
    └── run_status.csv       # Completion status of the five runs
```

## Environment

The submitted reproduction was tested with:

| Component | Version |
| --- | --- |
| OS | Windows 11 64-bit |
| Python | 3.12.11, Anaconda Torch2 environment |
| PyTorch | 2.8.0+cu126 |
| NumPy | 2.1.2 |
| Matplotlib | 3.10.7 |
| CUDA | PyTorch CUDA 12.6 |
| GPU | NVIDIA GeForce RTX 4060 Laptop GPU, 8188 MiB |

Install the tested CUDA environment:

```bash
python -m pip install -r requirements.txt
```

For a CPU-only environment, install the CPU PyTorch wheel instead of the CUDA
wheel, then install the remaining packages:

```bash
python -m pip install torch==2.8.0 --index-url https://download.pytorch.org/whl/cpu
python -m pip install numpy==2.1.2 matplotlib==3.10.7
```

CPU execution is supported by the scripts, but the full 300-epoch five-case run
is expected to be much slower than the GPU run.

## Reproduction Commands

Run all five experiments with the same 300-epoch setting used in the report:

```bash
python run_experiments.py --epochs 300 --device cuda:0
```

The runner skips an experiment when the corresponding log already reached the
requested final epoch. Use `--force` to overwrite and rerun logs:

```bash
python run_experiments.py --epochs 300 --device cuda:0 --force
```

Run a subset:

```bash
python run_experiments.py --cases 02_pieckipe_nodefense 03_pieckuea_nodefense --epochs 300 --device cuda:0
```

Check the commands without launching training:

```bash
python run_experiments.py --dry-run
```

Regenerate CSV summaries and figures from existing logs:

```bash
python parse_results.py --expected-epochs 300
```

The five report cases are:

| Case ID | Attack | Defense | Popular item size |
| --- | --- | --- | --- |
| `01_noattack_nodefense` | NoAttack | NoDefense | 150 |
| `02_pieckipe_nodefense` | PIECK-IPE | NoDefense | 10 |
| `03_pieckuea_nodefense` | PIECK-UEA | NoDefense | 150 |
| `04_pieckipe_regula` | PIECK-IPE | Regula | 10 |
| `05_pieckuea_regula` | PIECK-UEA | Regula | 150 |

## Results Used in the Course Report

The included logs all reached epoch 300. The final metrics parsed from
`results/data/final_metrics.csv` are:

| Attack | Defense | Loss | HR@5 | HR@10 | HR@20 | ER@5 | ER@10 | ER@20 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| NoAttack | NoDefense | 0.0488 | 35.52 | 54.29 | 71.58 | 0.00 | 0.11 | 0.23 |
| PIECK-IPE | NoDefense | 0.0488 | 37.22 | 54.40 | 73.91 | 79.16 | 80.87 | 82.80 |
| PIECK-UEA | NoDefense | 0.0529 | 36.80 | 53.76 | 72.43 | 87.13 | 88.38 | 88.95 |
| PIECK-IPE | Regula | -0.9209 | 38.07 | 58.32 | 75.93 | 2.62 | 4.44 | 7.29 |
| PIECK-UEA | Regula | -0.8704 | 38.49 | 55.99 | 75.29 | 10.02 | 10.82 | 12.76 |

Comparison with the paper values recorded in the report:

| Case | Reproduced ER@10 | Paper ER@10 | ER@10 gap | Reproduced HR@10 | Paper HR@10 | HR@10 gap |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| NoAttack + NoDefense | 0.11 | 0.23 | -0.12 | 54.29 | 57.16 | -2.87 |
| PIECK-IPE + NoDefense | 80.87 | 87.47 | -6.60 | 54.40 | 57.69 | -3.29 |
| PIECK-UEA + NoDefense | 88.38 | 93.39 | -5.01 | 53.76 | 57.69 | -3.93 |
| PIECK-IPE + Regula | 4.44 | 1.25 | +3.19 | 58.32 | 56.31 | +2.01 |
| PIECK-UEA + Regula | 10.82 | 0.00 | +10.82 | 55.99 | 55.89 | +0.10 |

The reproduction does not exactly match every number in the paper, but it
matches the main trend used in the report: PIECK-IPE and PIECK-UEA greatly
increase target exposure under no defense, while Regula substantially reduces
target exposure without collapsing HR@10.

## Curves

Target exposure:

![ER@10 curves](results/figures/er10_curves.png)

Recommendation utility:

![HR@10 curves](results/figures/hr10_curves.png)

Training loss:

![Loss curves](results/figures/loss_curves.png)

## Verification Checklist

Use these files to verify the submitted reproduction:

| File | Purpose |
| --- | --- |
| `results/logs/01-05_*.log` | Full stdout logs for every 300-epoch run |
| `results/run_status.csv` | Per-case completion status and log path |
| `results/environment.txt` | Recorded Python, PyTorch, CUDA, GPU, OS, and CPU information |
| `results/data/metrics_by_epoch.csv` | Parsed metrics for every epoch and case |
| `results/data/final_metrics.csv` | Final epoch metrics used in the report table |
| `results/data/paper_comparison.csv` | Reproduced values compared with paper Table III / IV |
| `results/data/summary.json` | Machine-readable reproduction summary |
| `results/figures/*.png` | Curves inserted into the report |

Recommended local validation:

```bash
python -m compileall MF-FRS parse_results.py run_experiments.py
python parse_results.py --expected-epochs 300
python run_experiments.py --dry-run
```

## References

[1] Jun Zhang, Huan Li, Dazhong Rong, Yan Zhao, Ke Chen, and Lidan Shou.
Preventing the Popular Item Embedding Based Attack in Federated Recommendations.
IEEE ICDE 2024.

[2] Xiangnan He, Lizi Liao, Hanwang Zhang, Liqiang Nie, Xia Hu, and Tat-Seng
Chua. Neural Collaborative Filtering. WWW 2017.

[3] H. Brendan McMahan, Eider Moore, Daniel Ramage, Seth Hampson, and Blaise
Agüera y Arcas. Communication-Efficient Learning of Deep Networks from
Decentralized Data. AISTATS 2017.

[4] Eugene Bagdasaryan, Andreas Veit, Yiqing Hua, Deborah Estrin, and Vitaly
Shmatikov. How to Backdoor Federated Learning. AISTATS 2020.

[5] Minghong Fang, Xiaoyu Cao, Jinyuan Jia, and Neil Zhenqiang Gong. Local Model
Poisoning Attacks to Byzantine-Robust Federated Learning. USENIX Security 2020.
