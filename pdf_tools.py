from pypdf import PdfReader, PdfWriter
from pathlib import Path

def fill_pdf_form(input_pdf: Path, output_pdf: Path, field_values: dict[str, str]) -> None:
    reader = PdfReader(str(input_pdf))
    writer = PdfWriter()

    for page in reader.pages:
        writer.add_page(page)
    
    for page in writer.pages:
        writer.update_page_form_field_values(page, field_values)

    # Improve rendering of filled values in many PDF viewers
    if "/AcroForm" in reader.trailer["/Root"]:
        writer._root_object.update({"/AcroForm": reader.trailer["/Root"]["/AcroForm"]})
        writer._root_object["/AcroForm"].update({"/NeedAppearances": True})
    

    output_pdf.parent.mkdir(parent=True, exist_ok=True)
    with open(output_pdf, "wb") as f:
        writer.write(f)