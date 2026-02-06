from pathlib import Path
from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject, BooleanObject


def fill_pdf(
    input_pdf: Path,
    output_pdf: Path,
    field_values: dict[str, str],
) -> None:
    """
    field_values rules:
      - Text fields: string
      - Checkboxes: "Yes" or ""   (PDF export value)
      - Radio buttons: "1","2","3"... (PDF export value)
    """

    reader = PdfReader(str(input_pdf))
    writer = PdfWriter()

    # 1️⃣ Clone ENTIRE document (keeps AcroForm + widgets)
    writer.clone_document_from_reader(reader)

    # 2️⃣ Force appearance regeneration
    root = writer._root_object
    if "/AcroForm" not in root:
        raise RuntimeError("PDF does not contain an AcroForm")

    root["/AcroForm"].update({
        NameObject("/NeedAppearances"): BooleanObject(True)
    })

    # Get field metadata ONCE
    fields = reader.get_fields() or {}

    # ---------------------------
    # Fill TEXT fields ONLY
    # ---------------------------
    text_values: dict[str, str] = {}

    for name, info in fields.items():
        if info.get("/FT") == "/Tx" and name in field_values:
            value = field_values.get(name)
            text_values[name] = "" if value is None else str(value)

    for page in writer.pages:
        writer.update_page_form_field_values(
            page,
            text_values,
            auto_regenerate=False,
        )

    # -----------------------------------
    # Fill CHECKBOXES + RADIO BUTTONS
    # -----------------------------------
    for page in writer.pages:
        annots = page.get("/Annots") or []
        for ref in annots:
            annot = ref.get_object()

            # Resolve field name (widget or parent)
            parent = annot.get("/Parent")
            field_obj = parent.get_object() if parent else annot
            field_name = field_obj.get("/T")

            if not field_name:
                continue

            field_name = str(field_name)
            if field_name not in field_values:
                continue

            raw_value = (field_values.get(field_name) or "").strip()
            if not raw_value:
                continue

            ap = annot.get("/AP")
            if not ap or "/N" not in ap:
                continue  # not a button widget

            normal_states = ap["/N"]
            possible = {
                str(k).lstrip("/"): k
                for k in normal_states.keys()
            }

            # Reset to Off first
            if "Off" in possible:
                annot.update({NameObject("/AS"): possible["Off"]})

            # Apply desired state
            if raw_value in possible:
                desired_state = possible[raw_value]
                annot.update({NameObject("/AS"): desired_state})

                # Radios need parent /V
                field_obj.update({
                    NameObject("/V"): NameObject(f"/{raw_value}")
                })

    # Write PDF
    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    with open(output_pdf, "wb") as f:
        writer.write(f)
