import pandas as pd
import csv
import os
import glob
import re
from pathlib import Path

folder_path = "./csv_folder"


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
activity = _term_lists["activity"]
uncertain_activity = _term_lists["uncertain_activity"]
category = _term_lists["category"]
competitors = _term_lists["competitors"]

bridge_terms_pattern = r"\b(?:{})\b".format("|".join(re.escape(t) for t in bridge_terms))
activity_pattern = r"\b(?:{})\b".format("|".join(re.escape(t) for t in activity))
category_pattern = r"\b(?:{})\b".format("|".join(re.escape(t) for t in category))
uncertain_activity_pattern = r"\b(?:{})\b".format("|".join(re.escape(t) for t in uncertain_activity))
competitor_pattern = r"\b(?:{})\b".format("|".join(re.escape(t) for t in competitors))

def normalize_columns(columns):
    return [str(col).strip().lower() for col in columns]


def find_best_column(columns, candidates):
    for candidate in candidates:
        candidate = candidate.lower()
        if candidate in columns:
            return candidate
    return None


def get_series(df, col):
    if col and col in df.columns:
        return df[col].fillna("").astype(str)
    return pd.Series("", index=df.index)


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


def clean_text(text):
    s = str(text)

    replacements = {
        "â€“": "-", "â€”": "-", "â€˜": "'", "â€™": "'",
        "â€œ": '"', "â€�": '"', "â€¢": "*", "Â": "",
        "–": "-", "—": "-", "‘": "'", "’": "'",
        "“": '"', "”": '"', "…": "...",
        "\x00": "", "\t": " ", "\n": " ", "\r": " ",
        "\u200b": "", "\u2028": " ", "\u2029": " ", "\u00a0": " ",
    }

    for bad, good in replacements.items():
        s = s.replace(bad, good)

    return re.sub(r"\s+", " ", s).strip()


def normalize_date_string(text):
    date_text = str(text).strip()
    if not date_text:
        return ""

    date_text = date_text.replace("/", "-")
    parsed = pd.to_datetime(date_text, errors="coerce")
    if pd.isna(parsed):
        return date_text
    return parsed.strftime("%Y-%m-%d")


def run_canada_wide2() -> pd.DataFrame:
    all_filtered_dfs = []
    csv_files = glob.glob(os.path.join(folder_path, "*.csv"))

    if not csv_files:
        print("No CSV files found in csv_folder.")
        return

    for file_path in csv_files:
        print(f"\nProcessing: {file_path}")

        try:
            try:
                df = pd.read_csv(file_path, encoding="utf-8", low_memory=False)
            except UnicodeDecodeError:
                df = pd.read_csv(file_path, encoding="latin1", low_memory=False)

            df.columns = normalize_columns(df.columns)

            column_map = {
                "Project Title": find_best_column(
                    df.columns,
                    ["title-titre-eng", "title", "title-titre"]
                ),
                "Award Date": find_best_column(
                    df.columns,
                    [
                        "contractawarddate-dateattributioncontrat",
                        "publicationdate-datepublication",
                        "contractstartdate-contratdatedebut",
                        "contractenddate-datefincontrat",
                    ]
                ),
                "Successful Vendor": find_best_column(
                    df.columns,
                    [
                        "supplierlegalname-nomlegalfournisseur-eng",
                        "supplierstandardizedname-nomnormalisefournisseur-eng",
                        "supplieroperatingname-nomcommercialfournisseur-eng",
                    ]
                ),
                "Issued by Organization": find_best_column(
                    df.columns,
                    ["contractingentityname-nomentitcontractante-eng"]
                ),
                "Issued for Organization": find_best_column(
                    df.columns,
                    ["enduserentitiesname-nomentitesutilisateurfinal-eng"]
                ),
                "Award Total": find_best_column(
                    df.columns,
                    ["totalcontractvalue-valeurtotalcontrat", "contractamount-montantcontrat"]
                ),
                "Tender Description": find_best_column(
                    df.columns,
                    ["tenderdescription-descriptionappeloffres-eng"]
                ),
                "UNSPSC": find_best_column(
                    df.columns,
                    ["unspscdescription-eng"]
                ),
            }

            title_col = column_map["Project Title"]
            desc_col = column_map["Tender Description"]
            unspsc_col = column_map["UNSPSC"]

            if title_col is None and desc_col is None:
                print("Skipping file because no title or tender description column found.")
                continue

            title_text = get_series(df, title_col).apply(clean_text)
            desc_text = get_series(df, desc_col).apply(clean_text)
            unspsc_text = get_series(df, unspsc_col).apply(clean_text)
            vendor_text = get_series(df, column_map["Successful Vendor"]).apply(clean_text)

            df["_search_text"] = title_text + " " + desc_text
            df["_unspsc_text"] = unspsc_text

            title_bridge_match = title_text.str.contains(bridge_terms_pattern, case=False, na=False)
            desc_bridge_match = desc_text.str.contains(bridge_terms_pattern, case=False, na=False)
            bridge_match = title_bridge_match | desc_bridge_match

            title_activity_match = title_text.str.contains(activity_pattern, case=False, na=False)
            desc_activity_match = desc_text.str.contains(activity_pattern, case=False, na=False)
            activity_match = title_activity_match | desc_activity_match

            category_match = df["_unspsc_text"].str.contains(category_pattern, case=False, na=False)

            title_uncertain_activity_match = title_text.str.contains(uncertain_activity_pattern, case=False, na=False)
            desc_uncertain_activity_match = desc_text.str.contains(uncertain_activity_pattern, case=False, na=False)
            uncertain_activity_match = title_uncertain_activity_match | desc_uncertain_activity_match

            vendor_competitor_match = vendor_text.str.contains(
                competitor_pattern,
                case=False,
                na=False,
            )

            filtered_by_desc_of_work = df[
                (bridge_match & (activity_match | category_match)) | (bridge_match & uncertain_activity_match & vendor_competitor_match)
            ].copy()

            print("Title column:", title_col)
            print("Description column:", desc_col)
            print("Bridge in title only:", int((title_bridge_match & ~desc_bridge_match).sum()))
            print("Bridge in desc only:", int((~title_bridge_match & desc_bridge_match).sum()))
            print("Bridge in both:", int((title_bridge_match & desc_bridge_match).sum()))
            print("Final matched rows:", len(filtered_by_desc_of_work))

            if filtered_by_desc_of_work.empty:
                continue

            filtered_by_desc_of_work["source_file"] = os.path.basename(file_path)

            output_df = pd.DataFrame()
            output_df["Data Source"] = filtered_by_desc_of_work["source_file"]
            output_df["Project Title"] = get_series(filtered_by_desc_of_work, title_col).apply(clean_text)
            output_df["Tender Description"] = get_series(filtered_by_desc_of_work, desc_col).apply(clean_text)
            output_df["Search Text"] = filtered_by_desc_of_work["_search_text"]

            bridge_regex = re.compile(bridge_terms_pattern, flags=re.IGNORECASE)
            activity_regex = re.compile(activity_pattern, flags=re.IGNORECASE)
            uncertain_activity_regex = re.compile(uncertain_activity_pattern, flags=re.IGNORECASE)

            output_df["Work Type"] = [
                "; ".join(
                    get_unique_matches(text, bridge_regex)
                    + get_unique_matches(text, activity_regex)
                    + (get_unique_matches(text, uncertain_activity_regex) if vendor_competitor_match.loc[idx] else [])
                )
                for idx, text in zip(filtered_by_desc_of_work.index, filtered_by_desc_of_work["_search_text"].astype(str))
            ]

            output_df["Award Date"] = get_series(filtered_by_desc_of_work, column_map["Award Date"]).apply(normalize_date_string)
            output_df["Successful Vendor"] = get_series(filtered_by_desc_of_work, column_map["Successful Vendor"])
            output_df["Issued by Organization"] = get_series(filtered_by_desc_of_work, column_map["Issued by Organization"])
            output_df["Issued for Organization"] = get_series(filtered_by_desc_of_work, column_map["Issued for Organization"])
            output_df["Award Total"] = get_series(filtered_by_desc_of_work, column_map["Award Total"])
            output_df["UNSPSC Description"] = get_series(filtered_by_desc_of_work, unspsc_col).apply(clean_text)

            all_filtered_dfs.append(output_df)

        except Exception as e:
            print(f"Error processing {file_path}")
            print(e)

    if all_filtered_dfs:
        final_df = pd.concat(all_filtered_dfs, ignore_index=True)
    else:
        final_df = pd.DataFrame()

    print("\nDone. Combined output prepared in memory")
    print(f"Total matched rows: {len(final_df)}")
    return final_df


if __name__ == "__main__":
    run_canada_wide2()
