# pdf_tools.py
from pathlib import Path
from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject, BooleanObject

def fill_pdf(input_pdf: Path, output_pdf: Path, field_values: dict[str, str]) -> None:
    """
    Safe filler:
      - Text fields filled via update_page_form_field_values (correct encoding)
      - Buttons (checkbox/radio) handled manually using NameObject('/Yes'), NameObject('/1'), etc.

    field_values:
      - text fields: normal strings
      - checkbox fields: "Yes"  (because your checkboxes have /Yes and /Off)
      - radio fields: "1","2","3"... (because your radios have /1,/2,/3...)
    """
    reader = PdfReader(str(input_pdf))
    writer = PdfWriter()

    # Preserve the original PDF structure (IMPORTANT)
    writer.clone_document_from_reader(reader)

    # NeedAppearances uses PDF boolean type
    root = writer._root_object
    if "/AcroForm" in root:
        root["/AcroForm"].update({NameObject("/NeedAppearances"): BooleanObject(True)})

    # ---------- 1) Fill TEXT safely ----------
    # Only pass string values to text filling.
    # (Buttons will be done manually.)
    text_values = {k: ("" if v is None else str(v)) for k, v in field_values.items()}

    for page in writer.pages:
        # This handles text fields properly (escaping, encoding, etc.)
        writer.update_page_form_field_values(page, text_values)

    # ---------- 2) Fill BUTTONS manually ----------
    for page in writer.pages:
        annots = page.get("/Annots") or []
        for a in annots:
            annot = a.get_object()

            # Determine field name from widget or its parent
            t = annot.get("/T")
            parent_obj = None
            if t is not None:
                field_name = str(t)
                if annot.get("/Parent"):
                    parent_obj = annot["/Parent"].get_object()
            else:
                parent = annot.get("/Parent")
                if not parent:
                    continue
                parent_obj = parent.get_object()
                pt = parent_obj.get("/T")
                if pt is None:
                    continue
                field_name = str(pt)

            if field_name not in field_values:
                continue

            desired_raw = (field_values.get(field_name) or "").strip()
            if not desired_raw:
                continue

            # Buttons must use PDF NameObjects like /Yes or /1
            desired_name = NameObject(f"/{desired_raw}")

            ap = annot.get("/AP")
            if not ap or not ap.get("/N"):
                continue  # not a button widget

            n = ap["/N"]
            possible = {str(k).lstrip("/"): k for k in n.keys()}  # "Off","Yes","1","2",...

            # Reset to Off first (if exists)
            if "Off" in possible:
                annot.update({NameObject("/AS"): possible["Off"]})

            # Set appearance to desired if this widget supports it
            if desired_raw in possible:
                annot.update({NameObject("/AS"): possible[desired_raw]})

            # Set values:
            # - radios usually need parent /V
            # - checkboxes often need widget /V too
            annot.update({NameObject("/V"): desired_name})
            if parent_obj is not None:
                parent_obj.update({NameObject("/V"): desired_name})

    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    with open(output_pdf, "wb") as f:
        writer.write(f)