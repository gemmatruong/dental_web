# # check_pdf_safe.py
from pypdf import PdfReader
from pathlib import Path

# PDF_PATH = Path("filled_forms/Truong_Gemma_20260123_233456.pdf")  # change to your actual output file

# def safe_name(x):
#     try:
#         return str(x)
#     except Exception:
#         return repr(x)

# def inspect_pdf(path: Path, keys_to_check=None):
#     keys_to_check = set(keys_to_check or ["sex", "health_Diabetes"])
#     r = PdfReader(str(path))
#     found = {k: [] for k in keys_to_check}
#     print("Scanning:", path)
#     for pi, page in enumerate(r.pages, start=1):
#         annots = page.get("/Annots")
#         if not annots:
#             continue
#         for a in annots:
#             try:
#                 annot = a.get_object()
#             except Exception:
#                 continue

#             # Try to get the field name (widget /T or Parent /T)
#             t = annot.get("/T")
#             if t is not None:
#                 field_name = safe_name(t)
#             else:
#                 parent = annot.get("/Parent")
#                 if parent:
#                     try:
#                         parent_obj = parent.get_object()
#                         pt = parent_obj.get("/T")
#                         field_name = safe_name(pt) if pt is not None else None
#                     except Exception:
#                         field_name = None
#                 else:
#                     field_name = None

#             if not field_name:
#                 # no name available; skip or print for debugging
#                 continue

#             # normalize name (remove surrounding parentheses if present)
#             field_name = field_name.strip()

#             # Read the widget's /AS (appearance state) and widget /V if present
#             as_val = annot.get("/AS")
#             v_val = annot.get("/V")

#             # Sometimes the parent holds the /V value
#             parent_v = None
#             try:
#                 parent = annot.get("/Parent")
#                 if parent:
#                     p = parent.get_object()
#                     parent_v = p.get("/V")
#             except Exception:
#                 parent_v = None

#             # If this field is one we care about, record it
#             if field_name in keys_to_check:
#                 found[field_name].append({
#                     "page": pi,
#                     "annot_obj": repr(annot)[:120],
#                     "widget_AS": safe_name(as_val),
#                     "widget_V": safe_name(v_val),
#                     "parent_V": safe_name(parent_v),
#                 })

#     # Print results
#     for k in keys_to_check:
#         items = found.get(k) or []
#         if not items:
#             print(f"[NOT FOUND] field '{k}' not found as widget on any page.")
#             continue
#         print(f"\nField '{k}' occurrences:")
#         for it in items:
#             print(f" page {it['page']}: widget /AS = {it['widget_AS']}, widget /V = {it['widget_V']}, parent /V = {it['parent_V']}")

# if __name__ == "__main__":
#     if not PDF_PATH.exists():
#         print("Error: PDF not found at", PDF_PATH)
#         print("List files in uploads/filled_forms/ to confirm the filename.")
#     else:
#         inspect_pdf(PDF_PATH, keys_to_check=["sex", "serious-illness", "health_Diabetes"])

reader = PdfReader(Path("static/uploads/forms/NP_form.pdf"))

for page_num, page in enumerate(reader.pages, start=1):
    annots = page.get("/Annots") or []
    for ref in annots:
        annot = ref.get_object()
        if annot.get("/FT") != "/Btn":
            continue

        name = annot.get("/T")
        if not name:
            continue

        ap = annot.get("/AP")
        if not ap or "/N" not in ap:
            continue

        states = [str(k) for k in ap["/N"].keys()]
        print(f"{name} (page {page_num}) → {states}")