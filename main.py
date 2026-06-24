from pathlib import Path

from bcWide import run_bc_wide
from canadaWide2 import run_canada_wide2
from process import run_process

BASE_DIR = Path(__file__).resolve().parent


def main() -> None:
    print("Starting market intelligence pipeline...")
    bc_df = run_bc_wide()
    canada_df = run_canada_wide2()
    run_process([bc_df, canada_df])

    final_output = BASE_DIR / "bridge_procurement_Analysis.xlsx"
    print("\nPipeline complete.")
    print(f"Final output from process.py: {final_output}")


if __name__ == "__main__":
    main()
