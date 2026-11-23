"""Run the analysis notebooks 01-08 in order, top to bottom, in fresh kernels.

    python run_all.py                    # extract GDP data only if data/<region>_obs.parquet is missing
    python run_all.py --no-extract       # never extract: fail if the extract is missing
    python run_all.py --force-extract    # re-extract from the GDP hourly AWS store (slow, ~16 GB RAM)
    python run_all.py --from 04          # start at notebook 04 (earlier results must exist)

Notebooks are executed in place, so their saved outputs match the results/ and figures/ files.
"""
import argparse
import os
import sys
import time
from pathlib import Path

import nbformat
from nbclient import NotebookClient

SRC = Path(__file__).resolve().parent / "src"
NOTEBOOKS = sorted(SRC.glob("0[1-8]_*.ipynb"))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = p.add_mutually_exclusive_group()
    g.add_argument("--force-extract", action="store_true", help="re-extract the raw GDP subset in notebook 01")
    g.add_argument("--no-extract", action="store_true", help="fail instead of extracting if the raw subset is missing")
    p.add_argument("--from", dest="start", default="01", help="first notebook number to run (default 01)")
    p.add_argument("--kernel", default="python3", help="Jupyter kernel name (default python3)")
    args = p.parse_args()

    # Read by src/config.py inside each kernel
    os.environ["GDP_EXTRACT"] = "force" if args.force_extract else "never" if args.no_extract else "auto"

    todo = [nb for nb in NOTEBOOKS if nb.name[:2] >= args.start]
    assert todo, f"no notebooks from {args.start}"
    total = time.perf_counter()
    for path in todo:
        t0 = time.perf_counter()
        print(f"running {path.name} ...", end=" ", flush=True)
        nb = nbformat.read(path, as_version=4)
        try:
            NotebookClient(nb, timeout=None, kernel_name=args.kernel,
                           resources={"metadata": {"path": str(SRC)}}).execute()
        except Exception:
            print("FAILED")
            nbformat.write(nb, path)          # keep the traceback in the notebook
            raise
        nbformat.write(nb, path)
        print(f"done in {time.perf_counter() - t0:.0f} s")
    print(f"all {len(todo)} notebooks finished in {time.perf_counter() - total:.0f} s")


if __name__ == "__main__":
    sys.exit(main())
