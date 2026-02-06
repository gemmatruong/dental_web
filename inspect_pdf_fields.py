# debug_pdf_buttons.py
from pypdf import PdfReader
from pathlib import Path

PDF = Path("static/uploads/forms/NP_form.pdf")  # adjust if needed

def get_widget_on_states(annot):
    """
    For a checkbox/radio widget, the /AP /N dict keys include possible states:
    usually /Off and one or more "on" states like /Yes, /1, /Male, etc.
    """
    ap = annot.get("/AP")
    if not ap:
        return []
    n = ap.get("/N")
    if not n:
        return []
    keys = list(n.keys())
    # keys are Name objects like '/Off', '/Yes'
    return [str(k) for k in keys]

reader = PdfReader(str(PDF))

print("=== Fields from get_fields() ===")
fields = reader.get_fields() or {}
for name, f in fields.items():
    ft = f.get("/FT")
    if ft in ("/Btn",):  # buttons = checkbox/radio
        print(f"\nField: {name}")
        print("  /FT:", ft)
        print("  /Ff:", f.get("/Ff"))  # flags help determine checkbox vs radio
        print("  /V :", f.get("/V"))
        # If there are /Kids, they are widgets (different positions/options)
        kids = f.get("/Kids") or []
        print("  kids:", len(kids))

print("\n=== Widget appearance states per page (what values actually work) ===")
for pi, page in enumerate(reader.pages):
    annots = page.get("/Annots") or []
    for a in annots:
        annot = a.get_object()
        t = annot.get("/T")
        ft = annot.get("/FT")
        if ft == "/Btn" or (t and str(t) in fields and fields[str(t)].get("/FT") == "/Btn"):
            name = str(t) if t else "(no /T on widget)"
            states = get_widget_on_states(annot)
            if states:
                print(f"Page {pi+1}  Field {name}  states: {states}")