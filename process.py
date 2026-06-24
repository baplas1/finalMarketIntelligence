from pathlib import Path

import pandas as pd
import re

INPUT_FILES = ["manual_input.csv"]
OUTPUT = "bridge_procurement_Analysis.xlsx"

vendor = [
    "Onsite",
    "Westrek",
    "AECOM",
    "All North",
    "Allnorth",
    "Allnorth Consultants",
    "Associated Engineering",
    "GHD",
    "Hatch",
    "ISI System Solutions",
    "ISL Engineering and Land Services",
    "ISL Engineering",
    "Jacobs",
    "McElhanney",
    "Morrison Hershfield",
    "Mott MacDonald",
    "Onsite Engineering",
    "Stantec",
    "T.Y. Lin",
    "TYLin",
    "WSP",
    "Parsons",
    "BASIS",
    "Spannovation",
    "CIMA",
    "DILLON",
    "Arup"
]


def clean_money(x):
    if pd.isna(x):
        return None

    x = str(x)
    x = re.sub(r"[^0-9.\-]", "", x)

    try:
        return float(x)
    except Exception:
        return None


def normalize_vendor_key(name):
    normalized = str(name).lower()
    normalized = re.sub(r"[^a-z0-9]+", "", normalized)
    return normalized.strip()


def find_canonical_vendor(normalized_name, vendor_map):
    if not normalized_name:
        return None

    exact_match = vendor_map.get(normalized_name)
    if exact_match:
        return normalized_name

    matches = [
        (key, base)
        for key, base in vendor_map.items()
        if key in normalized_name
    ]
    if not matches:
        return None

    return max(matches, key=lambda item: len(item[0]))[0]


def load_input_frame(input_path: str) -> pd.DataFrame | None:
    try:
        if input_path.lower().endswith(".csv"):
            return pd.read_csv(input_path)
        return pd.read_excel(input_path)
    except FileNotFoundError:
        print(f"Skipping missing input: {input_path}")
        return None


def run_process(extra_frames: list[pd.DataFrame] | None = None) -> None:
    frames = []
    if extra_frames:
        for frame in extra_frames:
            if frame is not None and not frame.empty:
                frames.append(frame)

    for input_path in INPUT_FILES:
        frame = load_input_frame(input_path)
        if frame is not None:
            frames.append(frame)

    if not frames:
        raise FileNotFoundError(
            f"No input files found. Expected one of: {', '.join(INPUT_FILES)}"
        )

    df = pd.concat(frames, ignore_index=True, sort=False)

    for drop_col in ["Search Text", "UNSPSC Description"]:
        if drop_col in df.columns:
            df.drop(columns=[drop_col], inplace=True)

    for col in [
        "Data Source",
        "Project Title",
        "Work Type",
        "Award Date",
        "Successful Vendor",
        "Issued by Organization",
        "Award Total",
    ]:
        if col not in df.columns:
            df[col] = ""

    df["Award Value"] = df["Award Total"].apply(clean_money)

    df["Award Date"] = df["Award Date"].astype(str).str.replace("/", "-")
    df["Award Date"] = pd.to_datetime(df["Award Date"], errors="coerce")
    df["Year"] = df["Award Date"].dt.year

    csv_vendors = [
        v.strip()
        for v in df["Successful Vendor"].fillna("").astype(str).unique()
        if v.strip()
    ]

    vendor_map = {}
    for base_vendor in vendor:
        normalized = normalize_vendor_key(base_vendor)
        if normalized and normalized not in vendor_map:
            vendor_map[normalized] = base_vendor

    for csv_vendor in csv_vendors:
        normalized = normalize_vendor_key(csv_vendor)
        if not normalized:
            continue

        canonical_key = find_canonical_vendor(normalized, vendor_map)
        if canonical_key is None:
            vendor_map[normalized] = csv_vendor
            vendor.append(csv_vendor)

    work = (
        df["Work Type"]
        .fillna("")
        .str.split(";")
        .explode()
        .str.strip()
    )

    work = work[work != ""]

    work_counts = (
        work.value_counts()
        .rename_axis("Work Type")
        .reset_index(name="Count")
    )

    asset_words = [
        "bridge",
        "culvert",
        "overpass",
        "underpass",
        "viaduct",
        "retaining wall",
        "deck",
        "pier",
        "abutment"
    ]

    asset_counts = []
    text = (
        df["Project Title"].fillna("") +
        " " +
        df["Work Type"].fillna("")
    ).str.lower()

    for asset in asset_words:
        asset_counts.append({
            "Asset Type": asset,
            "Count": text.str.contains(asset, regex=False).sum()
        })

    asset_counts = pd.DataFrame(asset_counts)

    bins = [
        0,
        50000,
        100000,
        250000,
        500000,
        1000000,
        5000000,
        float("inf")
    ]

    labels = [
        "<50k",
        "50k-100k",
        "100k-250k",
        "250k-500k",
        "500k-1M",
        "1M-5M",
        ">5M"
    ]

    hist = (
        pd.cut(df["Award Value"], bins=bins, labels=labels)
          .value_counts()
          .sort_index()
          .reset_index()
    )

    hist.columns = ["Award Range", "Count"]

    summary = pd.DataFrame({
        "Metric":[
            "Total Tenders",
            "Total Award Value",
            "Average Award",
            "Median Award",
            "Unique Vendors",
            "Unique Organizations"
        ],
        "Value":[
            len(df),
            df["Award Value"].sum(),
            df["Award Value"].mean(),
            df["Award Value"].median(),
            df["Successful Vendor"].nunique(),
            df["Issued by Organization"].nunique()
        ]
    })

    with pd.ExcelWriter(OUTPUT, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Raw Data", index=False)

        from openpyxl.styles import numbers
        ws = writer.sheets["Raw Data"]
        if "Award Date" in df.columns:
            col_idx = df.columns.get_loc("Award Date") + 1
            for row in ws.iter_rows(min_row=2, max_row=ws.max_row, min_col=col_idx, max_col=col_idx):
                for cell in row:
                    cell.number_format = 'YYYY-MM-DD'

        summary.to_excel(writer, sheet_name="Summary", index=False)

        (
            df.groupby("Year")
              .size()
              .reset_index(name="Tender Count")
              .to_excel(writer,
                        sheet_name="Tenders by Year",
                        index=False)
        )

        (
            df.groupby("Year")["Award Value"]
              .sum()
              .reset_index()
              .to_excel(writer,
                        sheet_name="Award Value by Year",
                        index=False)
        )

        vendor_counts = (
            df["Successful Vendor"]
              .fillna("")
              .astype(str)
              .apply(normalize_vendor_key)
              .apply(lambda norm: find_canonical_vendor(norm, vendor_map))
              .dropna()
              .value_counts()
        )

        top_vendor_names = [vendor_map[normalized] for normalized in vendor_map]
        top_vendors = pd.DataFrame({
            "Vendor": top_vendor_names,
            "Awards": [int(vendor_counts.get(normalize_vendor_key(v), 0)) for v in top_vendor_names]
        }).sort_values(["Awards", "Vendor"], ascending=[False, True]).reset_index(drop=True)

        top_vendors.to_excel(writer, sheet_name="Top Vendors", index=False)

        canonical_vendor_keys = (
            df["Successful Vendor"]
              .fillna("")
              .astype(str)
              .apply(normalize_vendor_key)
              .apply(lambda norm: find_canonical_vendor(norm, vendor_map))
        )

        df["Canonical Vendor"] = canonical_vendor_keys.map(
            lambda key: vendor_map[key] if key in vendor_map else ""
        )

        (
            df[df["Canonical Vendor"] != ""]
              .groupby("Canonical Vendor")["Award Value"]
              .sum()
              .sort_values(ascending=False)
              .reset_index()
              .rename(columns={"Canonical Vendor": "Vendor"})
              .to_excel(writer,
                        sheet_name="Vendor Award Value",
                        index=False)
        )

        (
            df["Issued by Organization"]
              .value_counts()
              .reset_index()
              .rename(columns={
                  "index":"Organization",
                  "Issued by Organization":"Count"
              })
              .to_excel(writer,
                        sheet_name="Top Organizations",
                        index=False)
        )

        (
            df.groupby("Issued by Organization")["Award Value"]
              .sum()
              .sort_values(ascending=False)
              .reset_index()
              .to_excel(writer,
                        sheet_name="Organizations by Value",
                        index=False)
        )

        work_counts.to_excel(
            writer,
            sheet_name="Work Type Counts",
            index=False
        )

        (
            df["Data Source"]
              .value_counts()
              .reset_index()
              .rename(columns={
                  "index":"Data Source",
                  "Data Source":"Count"
              })
              .to_excel(writer,
                        sheet_name="Data Sources",
                        index=False)
        )

        hist.to_excel(
            writer,
            sheet_name="Contract Value Distribution",
            index=False
        )

        asset_counts.to_excel(
            writer,
            sheet_name="Asset Types",
            index=False
        )

    print(f"Saved to {OUTPUT}")


if __name__ == "__main__":
    run_process()
