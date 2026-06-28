from __future__ import annotations

import argparse
import csv
import os
import platform
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SOURCE_DIR = ROOT / "MF-FRS"

CASES = [
    {"case_id": "01_noattack_nodefense", "attack": "NoAttack", "defense": "NoDefense", "size": 150},
    {"case_id": "02_pieckipe_nodefense", "attack": "PIECKIPE", "defense": "NoDefense", "size": 10},
    {"case_id": "03_pieckuea_nodefense", "attack": "PIECKUEA", "defense": "NoDefense", "size": 150},
    {"case_id": "04_pieckipe_regula", "attack": "PIECKIPE", "defense": "Regula", "size": 10},
    {"case_id": "05_pieckuea_regula", "attack": "PIECKUEA", "defense": "Regula", "size": 150},
]


def default_device() -> str:
    try:
        import torch

        return "cuda:0" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="运行 PIECK MF-FRS 复现实验，并在完成后解析结果。"
    )
    parser.add_argument("--python", default=sys.executable, help="用于运行 MF-FRS/main.py 的 Python 解释器。")
    parser.add_argument("--epochs", type=int, default=300, help="每组实验训练轮数。默认：300")
    parser.add_argument("--device", default=default_device(), help="Torch 运行设备。默认：有 GPU 时为 cuda:0，否则为 cpu")
    parser.add_argument("--dataset", default="ML-100K", help="MF-FRS/Data/ 下的数据集名称。默认：ML-100K")
    parser.add_argument(
        "--results-dir",
        default="results",
        help="日志、解析结果、曲线图和运行状态的输出目录。默认：results",
    )
    parser.add_argument(
        "--cases",
        nargs="+",
        default=["all"],
        help="要运行的实验编号，或使用 all 运行全部。例如：--cases 02_pieckipe_nodefense 03_pieckuea_nodefense",
    )
    parser.add_argument("--force", action="store_true", help="即使日志已达到 --epochs，也强制重新运行对应实验。")
    parser.add_argument("--skip-parse", action="store_true", help="实验完成后不自动运行 parse_results.py。")
    parser.add_argument("--dry-run", action="store_true", help="只打印命令，不实际启动训练。")
    return parser.parse_args()


def resolve_results_dir(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = ROOT / path
    return path


def select_cases(values: list[str]) -> list[dict[str, object]]:
    if values == ["all"] or "all" in values:
        return CASES
    available = {str(case["case_id"]): case for case in CASES}
    unknown = [value for value in values if value not in available]
    if unknown:
        names = ", ".join(available)
        raise SystemExit(f"未知实验编号：{', '.join(unknown)}。可用编号：{names}")
    return [available[value] for value in values]


def read_text(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-16", "gb18030"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def log_reached_epoch(log_path: Path, epochs: int) -> bool:
    if not log_path.exists():
        return False
    return re.search(rf"^Iteration\s+{epochs},", read_text(log_path), flags=re.MULTILINE) is not None


def build_command(args: argparse.Namespace, case: dict[str, object]) -> list[str]:
    return [
        args.python,
        "main.py",
        "--device",
        args.device,
        "--epochs",
        str(args.epochs),
        "--dataset",
        args.dataset,
        "--path",
        "Data/",
        "--size",
        str(case["size"]),
        "--attack",
        str(case["attack"]),
        "--defense",
        str(case["defense"]),
    ]


def run_and_log(command: list[str], cwd: Path, log_path: Path) -> int:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8", newline="") as log_file:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        assert process.stdout is not None
        for line in process.stdout:
            print(line, end="")
            log_file.write(line)
        return process.wait()


def write_status(results_dir: Path, rows: list[dict[str, object]]) -> None:
    path = results_dir / "run_status.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["case_id", "attack", "defense", "epochs", "exit_code", "complete", "log"]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def collect_environment(python_exe: str, results_dir: Path) -> None:
    code = (
        "import sys, platform\n"
        "print('Python=' + sys.version.replace(chr(10), ' '))\n"
        "try:\n"
        "    import torch\n"
        "    print('PyTorch=' + torch.__version__)\n"
        "    print('TorchCUDA=' + str(torch.version.cuda))\n"
        "    print('CUDAAvailable=' + str(torch.cuda.is_available()))\n"
        "    print('CUDADeviceCount=' + str(torch.cuda.device_count()))\n"
        "    print('GPU=' + (torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'none'))\n"
        "except Exception as exc:\n"
        "    print('PyTorchImportError=' + repr(exc))\n"
        "try:\n"
        "    import numpy\n"
        "    print('NumPy=' + numpy.__version__)\n"
        "except Exception as exc:\n"
        "    print('NumPyImportError=' + repr(exc))\n"
        "try:\n"
        "    import matplotlib\n"
        "    print('Matplotlib=' + matplotlib.__version__)\n"
        "except Exception as exc:\n"
        "    print('MatplotlibImportError=' + repr(exc))\n"
        "print('Platform=' + platform.platform())\n"
        "print('Processor=' + platform.processor())\n"
    )
    resolved_python = shutil.which(python_exe) or python_exe
    lines = [
        "CapturedAt=" + datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %z"),
        "PythonExe=" + str(Path(resolved_python).resolve()),
        "ProjectRoot=" + str(ROOT),
    ]
    result = subprocess.run(
        [python_exe, "-c", code],
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    lines.extend(result.stdout.splitlines())
    nvidia = subprocess.run(
        ["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"],
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if nvidia.returncode == 0 and nvidia.stdout.strip():
        lines.append("NvidiaSMI=" + nvidia.stdout.strip())
    lines.append("OS=" + platform.platform())
    lines.append("CPU=" + platform.processor())
    results_dir.mkdir(parents=True, exist_ok=True)
    (results_dir / "environment.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def quote_command(command: list[str]) -> str:
    return subprocess.list2cmdline(command) if os.name == "nt" else " ".join(command)


def main() -> None:
    args = parse_args()
    selected_cases = select_cases(args.cases)
    results_dir = resolve_results_dir(args.results_dir)
    logs_dir = results_dir / "logs"

    if args.dry_run:
        print(f"项目根目录：{ROOT}")
        print(f"源码目录：{SOURCE_DIR}")
        print(f"结果目录：{results_dir}")
        for case in selected_cases:
            print(f"[dry-run] {case['case_id']}: {quote_command(build_command(args, case))}")
        return

    collect_environment(args.python, results_dir)
    status_rows: list[dict[str, object]] = []
    for case in selected_cases:
        case_id = str(case["case_id"])
        log_path = logs_dir / f"{case_id}.log"
        try:
            relative_log = log_path.relative_to(ROOT).as_posix()
        except ValueError:
            relative_log = str(log_path)

        if not args.force and log_reached_epoch(log_path, args.epochs):
            print(f"[skip] {case_id} 已到达 Iteration {args.epochs}，跳过")
            status_rows.append(
                {
                    "case_id": case_id,
                    "attack": case["attack"],
                    "defense": case["defense"],
                    "epochs": args.epochs,
                    "exit_code": 0,
                    "complete": True,
                    "log": relative_log,
                }
            )
            write_status(results_dir, status_rows)
            continue

        command = build_command(args, case)
        print(f"[run] {case_id}: {quote_command(command)}")
        exit_code = run_and_log(command, SOURCE_DIR, log_path)
        complete = log_reached_epoch(log_path, args.epochs)
        status_rows.append(
            {
                "case_id": case_id,
                "attack": case["attack"],
                "defense": case["defense"],
                "epochs": args.epochs,
                "exit_code": exit_code,
                "complete": complete,
                "log": relative_log,
            }
        )
        write_status(results_dir, status_rows)
        if exit_code != 0 or not complete:
            raise SystemExit(f"实验失败或提前停止：{case_id}, exit={exit_code}, complete={complete}")

    if not args.skip_parse:
        parse_command = [
            args.python,
            str(ROOT / "parse_results.py"),
            "--expected-epochs",
            str(args.epochs),
            "--results-dir",
            str(results_dir),
        ]
        print(f"[parse] {quote_command(parse_command)}")
        subprocess.run(parse_command, cwd=ROOT, check=True)


if __name__ == "__main__":
    main()
