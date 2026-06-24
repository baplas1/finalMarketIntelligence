import csv
import importlib.util
from pathlib import Path

SOURCE_MODULE = Path("term_lists_source.py")
OUTPUT_FILE = Path("term_lists.csv")


def load_term_lists() -> dict[str, list[str]]:
    if not SOURCE_MODULE.exists():
        raise FileNotFoundError(f"Term source file not found: {SOURCE_MODULE}")

    spec = importlib.util.spec_from_file_location("term_lists_source", SOURCE_MODULE)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    return {
        "bridge_terms": list(getattr(module, "bridge_terms", [])),
        "activity": list(getattr(module, "activity_terms", [])),
        "uncertain_activity": list(getattr(module, "uncertain_activity_terms", [])),
        "category": list(getattr(module, "category", [])),
        "competitors": list(getattr(module, "competitors", [])),
    }


def write_csv(term_lists: dict[str, list[str]]) -> None:
    headers = ["bridge_terms", "activity", "uncertain_activity", "category", "competitors"]
    rows = []
    max_rows = max(len(term_lists[column]) for column in headers)

    for i in range(max_rows):
        row = [term_lists[column][i] if i < len(term_lists[column]) else "" for column in headers]
        rows.append(row)

    with OUTPUT_FILE.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(headers)
        writer.writerows(rows)


if __name__ == "__main__":
    term_lists = load_term_lists()
    write_csv(term_lists)
    print(f"Exported term lists to {OUTPUT_FILE}")
