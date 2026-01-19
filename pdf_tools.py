from pypdf import PdfReader, PdfWriter
from pypdf.generic import (
    DictionaryObject,
    NameObject,
    BooleanObject,
    ArrayObject,
)
from pathlib import Path


def fill_pdf_form(input_pdf: Path, output_pdf: Path, field_values: dict) -> None:
    reader = PdfReader(str(input_pdf))
    writer = PdfWriter()

    for page in reader.pages:
        writer.add_page(page)

    # CREATE or COPY /AcroForm BEFORE filling fields
    writer_root = writer._root_object
    reader_root = reader.trailer["/Root"]

    if "/AcroForm" in reader_root:
        # Copy existing AcroForm from template
        writer_root[NameObject("/AcroForm")] = reader_root["/AcroForm"]
    else:
        # Create a new AcroForm if template truly has none
        writer_root[NameObject("/AcroForm")] = DictionaryObject({
            NameObject("/Fields"): ArrayObject(),
        })

    # Force appearance rendering
    writer_root["/AcroForm"][NameObject("/NeedAppearances")] = BooleanObject(True)

    for page in writer.pages:
        writer.update_page_form_field_values(page, field_values)

    # Write file
    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    with open(output_pdf, "wb") as f:
        writer.write(f)
