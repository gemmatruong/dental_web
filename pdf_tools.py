# pdf_tools.py
from pathlib import Path
from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject, DictionaryObject, BooleanObject

def fill_pdf_form_strict(input_pdf: Path, output_pdf: Path, field_values: dict[str, str]) -> None:
    """
    field_values:
      - Text fields (/Tx): normal strings
      - Checkbox fields (/Btn): use "Yes" to check (because your PDF has /Yes,/Off)
      - Radio fields (/Btn): use export values like "1", "2", "3", ... (because your PDF uses /1,/2,...)
    """
    reader = PdfReader(str(input_pdf))
    writer = PdfWriter()

    # Copy pages
    for page in reader.pages:
        writer.add_page(page)

    # Copy AcroForm so writer knows it’s a form PDF
    root = reader.trailer["/Root"]
    if "/AcroForm" in root:
        writer._root_object.update({NameObject("/AcroForm"): root["/AcroForm"]})
    else:
        writer._root_object.update({NameObject("/AcroForm"): DictionaryObject()})

    writer._root_object["/AcroForm"].update({NameObject("/NeedAppearances"): BooleanObject(True)})

    # --- 1) Fill text fields using pypdf helper ---
    # We only let pypdf handle text fields; buttons are handled manually below.
    for page in writer.pages:
        # only keep non-button-ish values here; safest is to just pass everything
        # (it won’t hurt), but button handling is below anyway
        writer.update_page_form_field_values(page, field_values)

    # --- 2) Manual button handling: set /V on parent AND /AS on widgets ---
    # Gather widgets by field name
    widgets_by_name = {}

    for page in writer.pages:
        annots = page.get("/Annots") or []
        for a in annots:
            annot = a.get_object()

            # Find field name: widget /T or parent /T
            t = annot.get("/T")
            parent_obj = None
            if t is not None:
                field_name = str(t)
            else:
                parent = annot.get("/Parent")
                if not parent:
                    continue
                parent_obj = parent.get_object()
                pt = parent_obj.get("/T")
                if pt is None:
                    continue
                field_name = str(pt)

            # Only care about fields we are filling
            if field_name not in field_values:
                continue

            # Save widget + parent reference
            if parent_obj is None:
                # if widget had /T, its parent might still exist; not required
                parent = annot.get("/Parent")
                parent_obj = parent.get_object() if parent else None

            widgets_by_name.setdefault(field_name, []).append((annot, parent_obj))

    # Apply states per field
    for field_name, widgets in widgets_by_name.items():
        desired = (field_values.get(field_name) or "").strip()
        if not desired:
            continue

        # desired PDF name object: /Yes, /1, /2, etc.
        desired_name = NameObject(f"/{desired}")

        # 2a) Set parent field /V to desired (critical for radios)
        # Find first non-null parent_obj
        parent_obj = next((p for (_, p) in widgets if p is not None), None)
        if parent_obj is not None:
            parent_obj.update({NameObject("/V"): desired_name})

        # 2b) Set all widget /AS to /Off, then set matching widget /AS to desired
        for annot, _ in widgets:
            ap = annot.get("/AP")
            if not ap:
                continue
            n = ap.get("/N")
            if not n:
                continue

            # possible states keys like /Off, /Yes, /1, /2...
            possible_states = set(n.keys())

            # set Off if available
            if NameObject("/Off") in possible_states:
                annot.update({NameObject("/AS"): NameObject("/Off")})

            # if this widget supports the desired state, set it
            if desired_name in possible_states:
                annot.update({NameObject("/AS"): desired_name})

    # Write out
    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    with open(output_pdf, "wb") as f:
        writer.write(f)