import calendar
import csv
import subprocess
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

OUTPUT_FILE = Path("manual_input.csv")
BC_WIDE_DIR = Path("Files")
CANADA_WIDE_DIR = Path("csv_folder")
WORKBOOK_FILE = Path("bridge_procurement_Analysis.xlsx")

FIELDNAMES = [
    "Data Source",
    "Project Title",
    "Tender Description",
    "Work Type",
    "Award Date",
    "Successful Vendor",
    "Issued by Organization",
    "Issued for Organization",
    "Award Total",
    "UNSPSC Description",
]


def get_workbook_mtime() -> float:
    return WORKBOOK_FILE.stat().st_mtime if WORKBOOK_FILE.exists() else 0.0


WORKBOOK_MTIME = get_workbook_mtime()


@st.cache_data
def load_lookup_values(workbook_mtime: float):
    df = pd.read_excel(WORKBOOK_FILE, sheet_name="Raw Data")

    def get_values(column, split_semicolon=False):
        values = set()
        for val in df[column].dropna():
            val = str(val).strip()
            if not val:
                continue
            if split_semicolon:
                for item in val.split(";"):
                    item = item.strip()
                    if item:
                        values.add(item)
            else:
                values.add(val)
        return sorted(values)

    return {
        "work_types": get_values("Work Type", split_semicolon=True),
        "vendors": get_values("Successful Vendor"),
        "issued_by": get_values("Issued by Organization"),
        "issued_for": get_values("Issued for Organization"),
    }


LOOKUPS = load_lookup_values(WORKBOOK_MTIME)


@st.cache_data
def load_excel_sheet(sheet_name: str, workbook_mtime: float) -> pd.DataFrame:
    return pd.read_excel(WORKBOOK_FILE, sheet_name=sheet_name)


def ensure_csv_exists():
    if not OUTPUT_FILE.exists():
        with OUTPUT_FILE.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            writer.writeheader()


def save_row(values):
    ensure_csv_exists()
    with OUTPUT_FILE.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writerow(values)


def delete_row(index: int):
    delete_rows([index])


def delete_rows(indices: list[int]):
    ensure_csv_exists()
    df = pd.read_csv(OUTPUT_FILE)
    if not indices:
        return
    df = df.drop(indices).reset_index(drop=True)
    df.to_csv(OUTPUT_FILE, index=False)


def update_row(index: int, values: dict):
    ensure_csv_exists()
    df = pd.read_csv(OUTPUT_FILE)
    for col in FIELDNAMES:
        if col in values:
            df.at[index, col] = values[col]
    df.to_csv(OUTPUT_FILE, index=False)


def run_script(script_name):
    return subprocess.run(
        [sys.executable, script_name],
        capture_output=True,
        text=True,
    )


def ensure_upload_directories() -> None:
    BC_WIDE_DIR.mkdir(exist_ok=True)
    CANADA_WIDE_DIR.mkdir(exist_ok=True)


def unique_destination_path(directory: Path, filename: str) -> Path:
    destination = directory / filename
    if not destination.exists():
        return destination

    suffix = Path(filename).suffix
    stem = Path(filename).stem
    counter = 1
    while True:
        candidate = directory / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def save_uploaded_files(uploaded_files, destination_dir: Path) -> list[str]:
    saved_files = []
    for uploaded_file in uploaded_files:
        destination = unique_destination_path(destination_dir, uploaded_file.name)
        with destination.open("wb") as target:
            target.write(uploaded_file.getbuffer())
        saved_files.append(destination.name)
    return saved_files


def refresh_workbook_view() -> None:
    st.cache_data.clear()
    st.rerun()


def autocomplete_or_custom(label, options, default="", key=""):
    options = sorted(set(str(x) for x in options if str(x).strip()))

    if default and str(default).strip() and default not in options:
        display_options = [default] + options
        select_index = 0
    else:
        display_options = options if options else [""]
        select_index = display_options.index(default) if default in display_options else 0

    return st.selectbox(
        label,
        display_options,
        index=select_index,
        key=f"{key}_select",
        accept_new_options=True,
        placeholder=f"Select or type a custom {label.lower()}",
    )


# ── Page setup ────────────────────────────────────────────────────────────────

ensure_csv_exists()
ensure_upload_directories()

st.set_page_config(page_title="Bridge Procurement", layout="wide")
st.title("🌉 Bridge Procurement")

dashboard_tab, manual_tab, excel_tab = st.tabs(["Dashboard", "Analysis", "Excel Viewer"])

if "edit_index" not in st.session_state:
    st.session_state.edit_index = None

edit_mode = st.session_state.edit_index is not None
edit_row = {}


def show_metric_card(label: str, value) -> None:
    st.metric(label, value)


def render_chart_from_sheet(sheet_name: str, title: str, x_col: str, y_col: str, kind: str = "bar") -> None:
    try:
        chart_df = load_excel_sheet(sheet_name, WORKBOOK_MTIME)
    except Exception as exc:
        st.warning(f"{title}: unable to load sheet ({exc})")
        return

    if chart_df.shape[1] < 2:
        st.warning(f"{title}: not enough columns found in {sheet_name}.")
        return

    if x_col in chart_df.columns and y_col in chart_df.columns:
        chart_df = chart_df[[x_col, y_col]].copy()
    else:
        chart_df = chart_df.iloc[:, :2].copy()
        chart_df.columns = [x_col, y_col]

    chart_df = chart_df.dropna()
    if chart_df.empty:
        st.info(f"{title}: no data available.")
        return

    st.subheader(title)
    if kind == "line":
        st.line_chart(chart_df.set_index(x_col)[y_col])
    else:
        st.bar_chart(chart_df.set_index(x_col)[y_col])


with dashboard_tab:
    st.subheader("Workbook Dashboard")
    try:
        workbook = pd.ExcelFile(WORKBOOK_FILE)
        workbook_sheets = {sheet_name: load_excel_sheet(sheet_name, WORKBOOK_MTIME) for sheet_name in workbook.sheet_names}

        raw_data = workbook_sheets.get("Raw Data", pd.DataFrame())
        summary_data = workbook_sheets.get("Summary", pd.DataFrame())

        if not summary_data.empty and {"Metric", "Value"}.issubset(summary_data.columns):
            metric_map = dict(zip(summary_data["Metric"], summary_data["Value"]))
            metric_cols = st.columns(4)
            with metric_cols[0]:
                show_metric_card("Total Tenders", metric_map.get("Total Tenders", 0))
            with metric_cols[1]:
                show_metric_card("Total Award Value", metric_map.get("Total Award Value", 0))
            with metric_cols[2]:
                show_metric_card("Average Award", metric_map.get("Average Award", 0))
            with metric_cols[3]:
                show_metric_card("Unique Vendors", metric_map.get("Unique Vendors", 0))

        chart_left, chart_right = st.columns(2)
        with chart_left:
            render_chart_from_sheet("Tenders by Year", "Tenders by Year", "Year", "Tender Count", kind="line")
        with chart_right:
            render_chart_from_sheet("Award Value by Year", "Award Value by Year", "Year", "Award Value", kind="line")

        chart_left, chart_right = st.columns(2)
        with chart_left:
            render_chart_from_sheet("Top Vendors", "Top Vendors", "Vendor", "Awards")
        with chart_right:
            render_chart_from_sheet("Vendor Award Value", "Vendor Award Value", "Vendor", "Award Value")

        chart_left, chart_right = st.columns(2)
        with chart_left:
            render_chart_from_sheet("Top Organizations", "Top Organizations", "Organization", "Count")
        with chart_right:
            render_chart_from_sheet("Organizations by Value", "Organizations by Value", "Issued by Organization", "Award Value")

        chart_left, chart_right = st.columns(2)
        with chart_left:
            render_chart_from_sheet("Work Type Counts", "Work Type Counts", "Work Type", "Count")
        with chart_right:
            render_chart_from_sheet("Contract Value Distribution", "Contract Value Distribution", "Award Range", "Count")

        chart_left, chart_right = st.columns(2)
        with chart_left:
            render_chart_from_sheet("Asset Types", "Asset Types", "Asset Type", "Count")
        with chart_right:
            render_chart_from_sheet("Data Sources", "Data Sources", "Data Source", "Count")

        if not raw_data.empty:
            st.subheader("Raw Data Preview")
            st.dataframe(raw_data.head(25), use_container_width=True, height=350)
    except FileNotFoundError:
        st.warning("bridge_procurement_Analysis.xlsx was not found. Run process.py or main.py to generate it first.")

if edit_mode:
    edit_df = pd.read_csv(OUTPUT_FILE)
    edit_row = edit_df.iloc[st.session_state.edit_index].to_dict()
    st.info(f"✏️ Editing row {st.session_state.edit_index}")

with manual_tab:
    st.subheader("Upload Source Files")

    upload_col1, upload_col2 = st.columns(2)
    with upload_col1:
        bc_files = st.file_uploader(
            "Upload bcWide spreadsheets (.xlsx or .csv)",
            type=["xlsx", "csv"],
            accept_multiple_files=True,
            key="bcwide_upload",
        )
        if st.button("Save bcWide files to Files/", use_container_width=True):
            if not bc_files:
                st.warning("Select one or more bcWide files first.")
            else:
                saved = save_uploaded_files(bc_files, BC_WIDE_DIR)
                st.success(f"Saved {len(saved)} file(s) to Files/: {', '.join(saved)}")
                refresh_workbook_view()

    with upload_col2:
        canada_files = st.file_uploader(
            "Upload canadaWide spreadsheets (.csv)",
            type=["csv"],
            accept_multiple_files=True,
            key="canadawide_upload",
        )
        if st.button("Save canadaWide files to csv_folder/", use_container_width=True):
            if not canada_files:
                st.warning("Select one or more canadaWide CSV files first.")
            else:
                saved = save_uploaded_files(canada_files, CANADA_WIDE_DIR)
                st.success(f"Saved {len(saved)} file(s) to csv_folder/: {', '.join(saved)}")
                refresh_workbook_view()

    st.divider()
    # ── Input form ────────────────────────────────────────────────────────────

    col1, col2 = st.columns(2)

    with col1:
        project_title = st.text_input(
            "Project Title",
            value=edit_row.get("Project Title", "") if edit_mode else "",
        )

        work_type = autocomplete_or_custom(
            "Work Type",
            LOOKUPS["work_types"],
            edit_row.get("Work Type", "") if edit_mode else "",
            "work_type",
        )

        # ── Award date (year / month / day dropdowns) ────────────────────────
        date_col1, date_col2, date_col3 = st.columns(3)
        year_options = [str(y) for y in range(2019, date.today().year + 3)]
        month_names = [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December",
        ]

        with date_col1:
            default_year_idx = 0
            if edit_mode:
                try:
                    val = str(edit_row.get("Award Date", ""))
                    if val and val != "nan":
                        default_year_idx = year_options.index(val.split("-")[0])
                except Exception:
                    pass
            selected_year = st.selectbox("Year", year_options, index=default_year_idx, key="award_year")

        with date_col2:
            default_month_idx = date.today().month - 1
            if edit_mode:
                try:
                    val = str(edit_row.get("Award Date", ""))
                    if val and val != "nan":
                        default_month_idx = int(val.split("-")[1]) - 1
                except Exception:
                    pass
            selected_month = st.selectbox("Month", month_names, index=default_month_idx, key="award_month")

        month_number = month_names.index(selected_month) + 1
        max_day = calendar.monthrange(int(selected_year), month_number)[1]
        day_options = [str(d) for d in range(1, max_day + 1)]

        day_index = 0
        if edit_mode:
            try:
                val = str(edit_row.get("Award Date", ""))
                if val and val != "nan":
                    dv = val.split("-")[2]
                    if dv in day_options:
                        day_index = day_options.index(dv)
            except Exception:
                pass
        elif date.today().day <= max_day:
            day_index = date.today().day - 1

        with date_col3:
            selected_day = st.selectbox("Day", day_options, index=day_index, key="award_day")

        award_date = f"{selected_year}-{month_number:02}-{int(selected_day):02}"

        award_total = st.text_input(
            "Award Total",
            value=edit_row.get("Award Total", "") if edit_mode else "",
        )

    with col2:
        vendor = autocomplete_or_custom(
            "Successful Vendor",
            LOOKUPS["vendors"],
            edit_row.get("Successful Vendor", "") if edit_mode else "",
            "vendor",
        )

        issued_by = autocomplete_or_custom(
            "Issued by Organization",
            LOOKUPS["issued_by"],
            edit_row.get("Issued by Organization", "") if edit_mode else "",
            "issued_by",
        )

        issued_for = autocomplete_or_custom(
            "Issued for Organization",
            LOOKUPS["issued_for"],
            edit_row.get("Issued for Organization", "") if edit_mode else "",
            "issued_for",
        )

    description = st.text_area(
        "Tender Description",
        value=edit_row.get("Tender Description", "") if edit_mode else "",
        height=250,
    )

    submitted = st.button("💾 Save Row")

    if submitted:
        if not project_title.strip():
            st.error("Project Title is required.")
        else:
            values = {
                "Data Source": "manual",
                "Project Title": project_title,
                "Tender Description": description,
                "Work Type": work_type,
                "Award Date": award_date,
                "Successful Vendor": vendor,
                "Issued by Organization": issued_by,
                "Issued for Organization": issued_for,
                "Award Total": award_total,
                "UNSPSC Description": "",
            }

            if edit_mode:
                update_row(st.session_state.edit_index, values)
                st.success("Row updated successfully.")
                st.session_state.edit_index = None
            else:
                save_row(values)
                st.success("Row saved successfully.")
            st.rerun()

    # ── Script runners ────────────────────────────────────────────────────────

    st.divider()
    c1, c2 = st.columns(2)

    with c1:
        if st.button("▶ Run process.py", use_container_width=True):
            with st.spinner("Running process.py..."):
                result = run_script("process.py")
            if result.returncode == 0:
                st.success("process.py finished successfully.")
                refresh_workbook_view()
            else:
                st.error(result.stderr)
                st.code(result.stdout)

    with c2:
        if st.button("▶ Run main.py", use_container_width=True):
            with st.spinner("Running main.py..."):
                result = run_script("main.py")
            if result.returncode == 0:
                st.success("main.py finished successfully.")
                refresh_workbook_view()
            else:
                st.error(result.stderr)
                st.code(result.stdout)

    # ── CSV viewer ────────────────────────────────────────────────────────────

    st.divider()
    st.subheader("manual_input.csv Viewer")

    df = pd.read_csv(OUTPUT_FILE)

    if st.session_state.edit_index is not None:
        st.info(f"Editing row {st.session_state.edit_index}. Scroll up to modify and update.")

    # Multi-row table with bulk delete support
    selected = st.dataframe(
        df.drop(columns=["UNSPSC Description"], errors="ignore"),
        use_container_width=True,
        height=350,
        on_select="rerun",
        selection_mode="multi-row",
        key="csv_table",
    )

    selected_rows = selected.selection.rows if selected and selected.selection else []

    if selected_rows:
        valid_rows = sorted({idx for idx in selected_rows if 0 <= idx < len(df)})
        invalid_rows = len(selected_rows) - len(valid_rows)

        if valid_rows:
            if len(valid_rows) == 1:
                sel_idx = valid_rows[0]
                sel_title = df.iloc[sel_idx]["Project Title"]
                st.caption(f"Selected: **{sel_title}**")
            else:
                st.caption(f"Selected: **{len(valid_rows)} rows**")

            if invalid_rows:
                st.warning("One or more selected rows are no longer available and were ignored.")

            a1, a2 = st.columns(2)
            with a1:
                edit_disabled = len(valid_rows) != 1
                edit_button = st.button(
                    "✏️ Edit selected row",
                    use_container_width=True,
                    disabled=edit_disabled,
                    help="Select exactly one row to edit.",
                )
                if edit_button and not edit_disabled:
                    st.session_state.edit_index = valid_rows[0]
                    st.rerun()
            with a2:
                delete_label = "🗑️ Delete selected row" if len(valid_rows) == 1 else "🗑️ Delete selected rows"
                if st.button(delete_label, use_container_width=True):
                    delete_rows(valid_rows)
                    if st.session_state.edit_index in valid_rows:
                        st.session_state.edit_index = None
                    st.success("Selected row(s) deleted.")
                    st.rerun()
        else:
            st.warning("The selected rows no longer exist. Please select again.")

    with open(OUTPUT_FILE, "rb") as f:
        st.download_button(
            "⬇ Download manual_input.csv",
            f,
            file_name="manual_input.csv",
            use_container_width=True,
        )

    if st.session_state.edit_index is not None:
        if st.button("❌ Cancel Edit", use_container_width=True):
            st.session_state.edit_index = None
            st.rerun()

with excel_tab:
    st.subheader("bridge_procurement_Analysis.xlsx Viewer")
    try:
        with open("bridge_procurement_Analysis.xlsx", "rb") as f:
            st.download_button(
                "⬇ Download bridge_procurement_Analysis.xlsx",
                f,
                file_name="bridge_procurement_Analysis.xlsx",
                use_container_width=True,
            )

        workbook = pd.ExcelFile(WORKBOOK_FILE)
        sheet_tabs = st.tabs(workbook.sheet_names)

        for sheet_name, sheet_tab in zip(workbook.sheet_names, sheet_tabs):
            with sheet_tab:
                sheet_df = load_excel_sheet(sheet_name, WORKBOOK_MTIME)
                st.caption(f"{sheet_name} · {len(sheet_df)} rows · {len(sheet_df.columns)} columns")
                st.dataframe(sheet_df, use_container_width=True, height=550)
    except FileNotFoundError:
        st.warning("bridge_procurement_Analysis.xlsx was not found. Run process.py or main.py to generate it first.")