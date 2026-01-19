from pypdf import PdfReader
PDF_PATH = "static/uploads/forms/NP_form.pdf"

reader = PdfReader(PDF_PATH)
fields = reader.get_fields()

if not fields:
    print("No form fields found in this PDF")
else:
    print("PDF: \n")
    for name, field in fields.items():
        print(name)