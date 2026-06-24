import calendar
import csv
import subprocess
import sys
from datetime import date
from pathlib import Path
import tkinter as tk
from tkinter import messagebox
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText
import pandas as pd

OUTPUT_FILE = Path("manual_input.csv")
ANALYSIS_FILE = Path("bridge_procurement_Analysis.xlsx")
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


def load_recommendations() -> dict[str, list[str]]:
    recommendations = {
        "Work Type": [],
        "Successful Vendor": [],
        "Issued by Organization": [],
        "Issued for Organization": [],
    }

    if not ANALYSIS_FILE.exists():
        return recommendations

    try:
        df = pd.read_excel(ANALYSIS_FILE, sheet_name="Raw Data")
    except Exception:
        return recommendations

    def add_values(field: str, values: pd.Series) -> None:
        seen = set(recommendations[field])
        for value in values.fillna("").astype(str):
            cleaned = value.strip()
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                recommendations[field].append(cleaned)

    if "Work Type" in df.columns:
        work_values = (
            df["Work Type"]
            .fillna("")
            .astype(str)
            .str.split(";")
            .explode()
            .str.strip()
        )
        add_values("Work Type", work_values)

    for field in ["Successful Vendor", "Issued by Organization", "Issued for Organization"]:
        if field in df.columns:
            add_values(field, df[field])

    return recommendations


def ensure_csv_exists() -> None:
    if not OUTPUT_FILE.exists():
        with OUTPUT_FILE.open("w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=FIELDNAMES)
            writer.writeheader()


def save_row(values: dict[str, str]) -> None:
    ensure_csv_exists()
    with OUTPUT_FILE.open("a", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=FIELDNAMES)
        writer.writerow(values)


def delete_row(index: int) -> None:
    ensure_csv_exists()
    df = pd.read_csv(OUTPUT_FILE)
    df = df.drop(index).reset_index(drop=True)
    df.to_csv(OUTPUT_FILE, index=False)


def update_row(index: int, values: dict[str, str]) -> None:
    ensure_csv_exists()
    df = pd.read_csv(OUTPUT_FILE)
    for col in FIELDNAMES:
        if col in values:
            df.at[index, col] = values[col]
    df.to_csv(OUTPUT_FILE, index=False)


def clear_fields(entries: dict[str, tk.Entry], description_widget: ScrolledText) -> None:
    for name, entry in entries.items():
        if isinstance(entry, ttk.Combobox):
            entry.set("")
        else:
            entry.delete(0, tk.END)
    description_widget.delete("1.0", tk.END)


def on_save(entries: dict[str, tk.Entry], description_widget: ScrolledText, edit_index: list) -> None:
    values = {name: entry.get().strip() for name, entry in entries.items()}
    values["Tender Description"] = description_widget.get("1.0", tk.END).strip()
    values["Data Source"] = "manual"

    year = values.pop("Award Date", "")
    month = values.pop("Award Month", "")
    day = values.pop("Award Day", "")
    if year and month and day:
        month_number = [
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        ].index(month) + 1
        values["Award Date"] = f"{int(year):04}-{month_number:02}-{int(day):02}"
    else:
        values["Award Date"] = ""

    if not values["Project Title"]:
        messagebox.showwarning("Missing Value", "Project Title is required.")
        return
    try:
        if edit_index[0] is not None:
            update_row(edit_index[0], values)
            messagebox.showinfo("Updated", f"Row updated in {OUTPUT_FILE}")
            edit_index[0] = None
        else:
            save_row(values)
            messagebox.showinfo("Saved", f"Row saved to {OUTPUT_FILE}")
        clear_fields(entries, description_widget)
    except Exception as exc:
        messagebox.showerror("Operation Failed", str(exc))


def run_process() -> None:
    try:
        result = subprocess.run(
            [sys.executable, "process.py"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            messagebox.showinfo("Process Complete", "process.py finished successfully.")
        else:
            messagebox.showerror(
                "Process Failed",
                f"Return code: {result.returncode}\n\nStdout:\n{result.stdout}\n\nStderr:\n{result.stderr}",
            )
    except Exception as exc:
        messagebox.showerror("Execution Failed", str(exc))


def run_main() -> None:
    try:
        result = subprocess.run(
            [sys.executable, "main.py"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            messagebox.showinfo("Main Complete", "main.py finished successfully.")
        else:
            messagebox.showerror(
                "Main Failed",
                f"Return code: {result.returncode}\n\nStdout:\n{result.stdout}\n\nStderr:\n{result.stderr}",
            )
    except Exception as exc:
        messagebox.showerror("Execution Failed", str(exc))


def build_gui() -> None:
    root = tk.Tk()
    root.title("Bridge Procurement Manual Input")
    root.geometry("1200x900")

    recommendations = load_recommendations()

    main_frame = ttk.Frame(root, padding=16)
    main_frame.pack(fill="both", expand=True)

    title_label = ttk.Label(main_frame, text="🌉 Bridge Procurement Manual Input", font=(None, 18, "bold"))
    title_label.pack(anchor="w", pady=(0, 16))

    input_frame = ttk.Frame(main_frame)
    input_frame.pack(fill="x", pady=(0, 16))

    entries: dict[str, tk.Entry] = {}

    left_frame = ttk.Frame(input_frame)
    left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

    right_frame = ttk.Frame(input_frame)
    right_frame.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

    input_frame.columnconfigure(0, weight=1)
    input_frame.columnconfigure(1, weight=1)

    left_fields = [
        "Project Title",
        "Work Type",
        "Award Total",
    ]

    right_fields = [
        "Successful Vendor",
        "Issued by Organization",
        "Issued for Organization",
        "UNSPSC Description",
    ]

    for row, field in enumerate(left_fields, start=0):
        label = ttk.Label(left_frame, text=field)
        label.grid(row=row, column=0, sticky="w", pady=6)
        if field == "Work Type":
            entry = ttk.Combobox(left_frame, values=recommendations[field], state="normal")
        else:
            entry = ttk.Entry(left_frame)
        entry.grid(row=row, column=1, sticky="ew", pady=6)
        left_frame.columnconfigure(1, weight=1)
        entries[field] = entry

    for row, field in enumerate(right_fields):
        label = ttk.Label(right_frame, text=field)
        label.grid(row=row, column=0, sticky="w", pady=6)
        if field in recommendations:
            entry = ttk.Combobox(right_frame, values=recommendations[field], state="normal")
        else:
            entry = ttk.Entry(right_frame)
        entry.grid(row=row, column=1, sticky="ew", pady=6)
        right_frame.columnconfigure(1, weight=1)
        entries[field] = entry

    row = len(left_fields)
    date_label = ttk.Label(left_frame, text="Award Date")
    date_label.grid(row=row, column=0, sticky="w", pady=6)

    date_frame = ttk.Frame(left_frame)
    date_frame.grid(row=row, column=1, sticky="ew", pady=6)
    date_frame.columnconfigure((0, 1, 2), weight=1)

    year_values = [str(year) for year in range(2019, date.today().year + 3)]
    month_values = [
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ]

    year_combobox = ttk.Combobox(date_frame, values=year_values, state="readonly")
    year_combobox.set(str(date.today().year))
    year_combobox.grid(row=0, column=0, sticky="ew", padx=(0, 4))

    month_combobox = ttk.Combobox(date_frame, values=month_values, state="readonly")
    month_combobox.set(month_values[date.today().month - 1])
    month_combobox.grid(row=0, column=1, sticky="ew", padx=(0, 4))

    day_values = [str(day) for day in range(1, calendar.monthrange(date.today().year, date.today().month)[1] + 1)]
    day_combobox = ttk.Combobox(date_frame, values=day_values, state="readonly")
    day_combobox.set(str(date.today().day))
    day_combobox.grid(row=0, column=2, sticky="ew")

    def update_day_options(event=None) -> None:
        try:
            selected_year = int(year_combobox.get())
            selected_month = month_values.index(month_combobox.get()) + 1
            days = [str(day) for day in range(1, calendar.monthrange(selected_year, selected_month)[1] + 1)]
            day_combobox.config(values=days)
            if day_combobox.get() not in days:
                day_combobox.set(days[-1])
        except Exception:
            pass

    year_combobox.bind("<<ComboboxSelected>>", update_day_options)
    month_combobox.bind("<<ComboboxSelected>>", update_day_options)

    entries["Award Date"] = year_combobox
    entries["Award Month"] = month_combobox
    entries["Award Day"] = day_combobox

    description_frame = ttk.Frame(main_frame)
    description_frame.pack(fill="both", expand=True, pady=(0, 16))

    desc_label = ttk.Label(description_frame, text="Tender Description")
    desc_label.pack(anchor="w")

    description_widget = ScrolledText(description_frame, height=12, wrap="word")
    description_widget.pack(fill="both", expand=True, pady=(8, 0))

    button_frame = ttk.Frame(main_frame)
    button_frame.pack(fill="x", pady=(16, 0))

    edit_index = [None]

    def on_save_wrapper():
        on_save(entries, description_widget, edit_index)
        load_csv_preview()

    save_button = ttk.Button(button_frame, text="💾 Save Row", command=on_save_wrapper)
    save_button.pack(side="left", padx=8)

    run_process_button = ttk.Button(button_frame, text="▶ Run process.py", command=run_process)
    run_process_button.pack(side="left", padx=8)

    run_main_button = ttk.Button(button_frame, text="▶ Run main.py", command=run_main)
    run_main_button.pack(side="left", padx=8)

    clear_button = ttk.Button(button_frame, text="Clear", command=lambda: clear_fields(entries, description_widget))
    clear_button.pack(side="left", padx=8)

    quit_button = ttk.Button(button_frame, text="Quit", command=root.destroy)
    quit_button.pack(side="left", padx=8)

    def load_csv_preview():
        for row in tree.get_children():
            tree.delete(row)
        ensure_csv_exists()
        with OUTPUT_FILE.open("r", encoding="utf-8", newline="") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                values = [row.get(col, "") for col in columns]
                tree.insert("", "end", values=values)

    def on_edit():
        selected = tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select a row to edit.")
            return
        row_index = tree.index(selected[0])
        edit_index[0] = row_index
        df = pd.read_csv(OUTPUT_FILE)
        row_data = df.iloc[row_index]
        entries["Project Title"].delete(0, tk.END)
        entries["Project Title"].insert(0, str(row_data.get("Project Title", "")))
        entries["Work Type"].delete(0, tk.END)
        entries["Work Type"].insert(0, str(row_data.get("Work Type", "")))
        entries["Award Total"].delete(0, tk.END)
        entries["Award Total"].insert(0, str(row_data.get("Award Total", "")))
        entries["Successful Vendor"].delete(0, tk.END)
        entries["Successful Vendor"].insert(0, str(row_data.get("Successful Vendor", "")))
        entries["Issued by Organization"].delete(0, tk.END)
        entries["Issued by Organization"].insert(0, str(row_data.get("Issued by Organization", "")))
        entries["Issued for Organization"].delete(0, tk.END)
        entries["Issued for Organization"].insert(0, str(row_data.get("Issued for Organization", "")))
        entries["UNSPSC Description"].delete(0, tk.END)
        entries["UNSPSC Description"].insert(0, str(row_data.get("UNSPSC Description", "")))
        description_widget.delete("1.0", tk.END)
        description_widget.insert("1.0", str(row_data.get("Tender Description", "")))
        award_date_str = str(row_data.get("Award Date", ""))
        if award_date_str and award_date_str != "nan":
            parts = award_date_str.split("-")
            if len(parts) == 3:
                entries["Award Date"].set(parts[0])
                month_idx = int(parts[1]) - 1
                month_values = [
                    "January",
                    "February",
                    "March",
                    "April",
                    "May",
                    "June",
                    "July",
                    "August",
                    "September",
                    "October",
                    "November",
                    "December",
                ]
                if 0 <= month_idx < len(month_values):
                    entries["Award Month"].set(month_values[month_idx])
                entries["Award Day"].set(parts[2].lstrip("0") or "1")
        messagebox.showinfo("Edit Mode", "Row loaded. Modify and save to update.")

    def on_delete():
        selected = tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select a row to delete.")
            return
        row_index = tree.index(selected[0])
        if messagebox.askyesno("Confirm Delete", "Are you sure you want to delete this row?"):
            delete_row(row_index)
            messagebox.showinfo("Deleted", "Row deleted successfully.")
            load_csv_preview()

    action_frame = ttk.Frame(main_frame)
    action_frame.pack(fill="x", pady=(8, 0))

    edit_button = ttk.Button(action_frame, text="✏️ Edit Selected", command=on_edit)
    edit_button.pack(side="left", padx=8)

    delete_button = ttk.Button(action_frame, text="🗑️ Delete Selected", command=on_delete)
    delete_button.pack(side="left", padx=8)

    cancel_button = ttk.Button(action_frame, text="❌ Cancel Edit", command=lambda: [edit_index.__setitem__(0, None), clear_fields(entries, description_widget)])
    cancel_button.pack(side="left", padx=8)

    preview_frame = ttk.Labelframe(main_frame, text="Current CSV")
    preview_frame.pack(fill="both", expand=True, pady=(16, 0))

    columns = FIELDNAMES
    tree = ttk.Treeview(preview_frame, columns=columns, show="headings", height=10)
    for col in columns:
        tree.heading(col, text=col)
        tree.column(col, width=120, anchor="w")
    tree.pack(fill="both", expand=True, pady=(8, 0))

    load_csv_preview()

    root.columnconfigure(0, weight=1)
    ensure_csv_exists()
    root.mainloop()


if __name__ == "__main__":
    build_gui()
