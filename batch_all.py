import glob, os, sys, zipfile, io
from app import process_uploads

DOWNLOADS = "C:/Users/Gokul Jayachandran/Downloads"

FILES = [
    "July_Part-I.pdf", "July_Part-II.pdf",
    "August_Part-2(List_of_tables).pdf",
    "September_Part-2(List_of_tables).pdf",
    "October.pdf", "November.pdf", "December.pdf", "January.pdf",
    "FRMarch2025.pdf",
    "April_Part-I_Synopsis.pdf", "April_Part-II_List_of_tables.pdf",
    "May_Part-2.pdf", "June.pdf",
    "FlashReport_July_2025.pdf", "FlashReport_August_2025.pdf",
    "FlashReport_October_2025.pdf", "FlashReport_November_2025.pdf",
    "FlashReport_December_2025.pdf",
    "FlashReport_January_2026.pdf", "FlashReport_February_2026.pdf",
    "FlashReport_March_2026.pdf", "FlashReport_April2026.pdf",
    "FlashReport_May2026.pdf", "FlashReport_June_2026.pdf",
    "FlashReport_July_2026.pdf",
]

files = []
missing = []
for name in FILES:
    path = os.path.join(DOWNLOADS, name)
    if os.path.exists(path):
        files.append((name, open(path, "rb")))
    else:
        missing.append(name)

print(f"Processing {len(files)} files, {len(missing)} missing: {missing}")
sys.stdout.flush()

results = process_uploads(files)
for _, f in files:
    f.close()

out_path = os.path.join(DOWNLOADS, "paimana_all_2024_2026_extracted.zip")
with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
    for key, df in results.items():
        zf.writestr(f"{key}.csv", df.to_csv(index=False))
        months = sorted(df["report_month"].unique().tolist()) if not df.empty else []
        print(f"{key}: {len(df)} rows, months: {months}")
        sys.stdout.flush()

print(f"Wrote {out_path}")
