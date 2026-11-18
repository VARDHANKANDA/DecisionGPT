"""Convert an UCI Online Retail workbook to CSV (streaming; raw workbook untouched). Usage: python xlsx_to_csv.py SRC.xlsx DST.csv"""
import sys, csv, time, openpyxl
src, dst = sys.argv[1], sys.argv[2]
t=time.time()
wb = openpyxl.load_workbook(src, read_only=True, data_only=True)
n=0
with open(dst, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f); hdr_written=False
    for ws in wb.worksheets:
        first=True
        for row in ws.iter_rows(values_only=True):
            if first:
                first=False
                if not hdr_written: w.writerow(list(row)+["source_sheet"]); hdr_written=True
                continue
            w.writerow([("" if v is None else (v.isoformat(sep=" ") if hasattr(v,"isoformat") else v)) for v in row]+[ws.title]); n+=1
        print("sheet", ws.title, "done; rows so far", n, flush=True)
print("rows", n, "secs", round(time.time()-t))
