import csv
import glob
import os
import re
from pathlib import Path
import pandas as pd
from openpyxl.styles import numbers

# =====================================
# SETTINGS
# =====================================

folder_path = r"./Files"


def load_term_lists(csv_path: Path) -> dict[str, list[str]]:
    if not csv_path.exists():
        raise FileNotFoundError(f"Term list file not found: {csv_path}")

    term_lists: dict[str, list[str]] = {
        "bridge_terms": [],
        "activity": [],
        "uncertain_activity": [],
        "category": [],
        "competitors": [],
    }

    with csv_path.open("r", encoding="utf-8", newline="") as csvfile:
        reader = csv.DictReader(csvfile)
        headers = reader.fieldnames or []
        for row in reader:
            for header in headers:
                if header not in term_lists:
                    continue
                value = (row.get(header) or "").strip()
                if value and value not in term_lists[header]:
                    term_lists[header].append(value)

    return term_lists


_term_lists_file = Path(__file__).resolve().parent / "term_lists.csv"
_term_lists = load_term_lists(_term_lists_file)

bridge_terms = _term_lists["bridge_terms"]
activity_terms = _term_lists["activity"]
uncertain_activity_terms = _term_lists["uncertain_activity"]
category = _term_lists["category"]
competitors = _term_lists["competitors"]

activity_pattern = r"\b(?:{})\b".format(
    "|".join(map(re.escape, activity_terms))
)

uncertain_activity_pattern = r"\b(?:{})\b".format(
    "|".join(map(re.escape, uncertain_activity_terms))
)

competitor_pattern = r"\b(?:{})\b".format(
    "|".join(re.escape(t) for t in competitors)
)


def get_unique_matches(text, regex):
    matches = regex.findall(str(text))
    seen = set()
    ordered = []
    for match in matches:
        term = match.strip().lower()
        if term and term not in seen:
            seen.add(term)
            ordered.append(term)
    return ordered

bridge_pattern = r"\b(?:{})\b".format(
    "|".join(map(re.escape, bridge_terms))
)


def run_bc_wide() -> pd.DataFrame:
    results = []
    files = glob.glob(os.path.join(folder_path, "*.xlsx"))
    files.extend(glob.glob(os.path.join(folder_path, "*.csv")))

    for file_path in files:
        print(f"Processing: {os.path.basename(file_path)}")

        try:
            if file_path.lower().endswith(".csv"):
                try:
                    df = pd.read_csv(
                        file_path,
                        encoding="utf-8",
                        low_memory=False
                    )
                except UnicodeDecodeError:
                    df = pd.read_csv(
                        file_path,
                        encoding="latin1",
                        low_memory=False
                    )
            else:
                df = pd.read_excel(file_path)

            df.columns = [
                str(col).strip().lower()
                for col in df.columns
            ]

            project_col = None
            award_date_col = None
            vendor_col = None
            issued_by_col = None
            issued_for_col = None
            award_total_col = None

            for col in df.columns:
                if col in ["project title", "title", "project"]:
                    project_col = col
                elif col in [
                    "award date",
                    "date",
                    "date awarded",
                    "awarded"
                ]:
                    award_date_col = col
                elif col in [
                    "successful vendor",
                    "vendor",
                    "winning firm"
                ]:
                    vendor_col = col
                elif col in [
                    "issued by organization",
                    "issued by"
                ]:
                    issued_by_col = col
                elif col in [
                    "issued for organization",
                    "issued for"
                ]:
                    issued_for_col = col
                elif col in [
                    "award total",
                    "award value",
                    "contract value"
                ]:
                    award_total_col = col

            if project_col is None:
                print("  No project title column found.")
                continue

            text = df[project_col].astype(str)

            bridge_mask = text.str.contains(
                bridge_pattern,
                case=False,
                na=False,
                regex=True
            )

            activity_mask = text.str.contains(
                activity_pattern,
                case=False,
                na=False,
                regex=True
            )

            uncertain_activity_mask = text.str.contains(
                uncertain_activity_pattern,
                case=False,
                na=False,
                regex=True
            )

            vendor_text = (
                df[vendor_col].fillna("")
                if vendor_col
                else pd.Series("", index=df.index)
            ).astype(str)

            vendor_competitor_mask = vendor_text.str.contains(
                competitor_pattern,
                case=False,
                na=False,
                regex=True
            )

            matches = df[
                (bridge_mask & activity_mask)
                | (bridge_mask & uncertain_activity_mask & vendor_competitor_mask)
            ].copy()
            if len(matches) == 0:
                continue

            bridge_regex = re.compile(bridge_pattern, flags=re.IGNORECASE)
            activity_regex = re.compile(activity_pattern, flags=re.IGNORECASE)

            output = pd.DataFrame(index=matches.index)

            output["Data Source"] = os.path.basename(file_path)
            output["Project Title"] = matches[project_col]
            uncertain_activity_regex = re.compile(uncertain_activity_pattern, flags=re.IGNORECASE)

            output["Work Type"] = [
                "; ".join(
                    get_unique_matches(title, bridge_regex)
                    + get_unique_matches(title, activity_regex)
                    + (
                        get_unique_matches(title, uncertain_activity_regex)
                        if vendor_competitor_mask.loc[idx]
                        else []
                    )
                )
                for idx, title in matches[project_col].astype(str).items()
            ]

            output["Award Date"] = (
                matches[award_date_col]
                if award_date_col
                else ""
            )

            output["Successful Vendor"] = (
                matches[vendor_col]
                if vendor_col
                else ""
            )

            output["Issued by Organization"] = (
                matches[issued_by_col]
                if issued_by_col
                else ""
            )

            output["Issued for Organization"] = (
                matches[issued_for_col]
                if issued_for_col
                else ""
            )

            output["Award Total"] = (
                matches[award_total_col]
                if award_total_col
                else ""
            )

            results.append(output)

            print(f"  Found {len(output)} matches")

        except Exception as e:
            print(f"Error processing {file_path}")
            print(e)

    if results:
        final_df = pd.concat(results, ignore_index=True)
    else:
        final_df = pd.DataFrame(
            columns=[
                "Data Source",
                "Project Title",
                "Work Type",
                "Award Date",
                "Successful Vendor",
                "Issued by Organization",
                "Issued for Organization",
                "Award Total",
            ]
        )

    if "Award Date" in final_df.columns:
        final_df["Award Date"] = final_df["Award Date"].astype(str).str.replace("/", "-")
        final_df["Award Date"] = pd.to_datetime(final_df["Award Date"], errors="coerce").dt.strftime("%Y-%m-%d")

    print(f"\nFinished. {len(final_df)} total matches found.")
    return final_df


if __name__ == "__main__":
    run_bc_wide()
