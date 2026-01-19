# utils/pdf_gen.py
import os
from datetime import datetime

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
)

styles = getSampleStyleSheet()

TITLE = ParagraphStyle(
    "TITLE", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=16, spaceAfter=6
)
H1 = ParagraphStyle(
    "H1", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=12, spaceBefore=6, spaceAfter=6
)
H2 = ParagraphStyle(
    "H2", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=13, spaceBefore=0, spaceAfter=10
)
P = ParagraphStyle(
    "P", parent=styles["Normal"], fontName="Helvetica", fontSize=9, leading=11
)
SM = ParagraphStyle(
    "SM", parent=styles["Normal"], fontName="Helvetica", fontSize=8.5, leading=10.5, textColor=colors.black
)

def _s(v) -> str:
    return (v or "").strip()

def _yn(v) -> str:
    v = _s(v).lower()
    if v == "yes":
        return "Yes"
    if v == "no":
        return "No"
    return ""

def _blank() -> str:
    # Style A: show blank line/box
    return " "

def _val_or_blank(v) -> str:
    return _s(v) if _s(v) else _blank()

def _p(text, style=SM) -> Paragraph:
    return Paragraph(text, style)

def _form_row(label: str, value: str):
    return [_p(f"<b>{label}</b>", SM), _p(_val_or_blank(value), SM)]

def _two_col_row(l1, v1, l2, v2):
    return [
        _p(f"<b>{l1}</b>", SM), _p(_val_or_blank(v1), SM),
        _p(f"<b>{l2}</b>", SM), _p(_val_or_blank(v2), SM),
    ]

def _table_2(data, col_widths):
    """
    2-column table: [Label | Value-underlined]
    """
    t = Table(data, colWidths=col_widths, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING", (0,0), (-1,-1), 3),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ("LINEBELOW", (1,0), (1,-1), 0.6, colors.black),
    ]))
    return t

def _table_4(data, col_widths):
    """
    4-column table: [L1 | V1-underlined | L2 | V2-underlined]
    """
    t = Table(data, colWidths=col_widths, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING", (0,0), (-1,-1), 3),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ("LINEBELOW", (1,0), (1,-1), 0.6, colors.black),
        ("LINEBELOW", (3,0), (3,-1), 0.6, colors.black),
    ]))
    return t

def _checkbox_grid(checked_items: list[str], cols: int = 3):
    """
    Show checked items with ☑ and leave others out.
    (If none checked, show a blank line.)
    """
    items = [f"☑ {c}" for c in (checked_items or [])]
    if not items:
        items = [" "]

    grid = []
    row = []
    for i, it in enumerate(items):
        row.append(_p(it, SM))
        if (i + 1) % cols == 0:
            grid.append(row)
            row = []
    if row:
        while len(row) < cols:
            row.append(_p("", SM))
        grid.append(row)

    t = Table(grid, colWidths=[(letter[0] - 72) / cols] * cols, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("TOPPADDING", (0,0), (-1,-1), 1),
        ("BOTTOMPADDING", (0,0), (-1,-1), 2),
    ]))
    return t

def _big_text_two_cols(left_title: str, left_text: str, right_title: str, right_text: str):
    """
    Two "big" boxes with underlines for text areas.
    """
    left_text_p = _p(_val_or_blank(left_text).replace("\n", "<br/>"), SM)
    right_text_p = _p(_val_or_blank(right_text).replace("\n", "<br/>"), SM)

    t = Table([
        [_p(f"<b>{left_title}</b>", SM), _p(f"<b>{right_title}</b>", SM)],
        [left_text_p, right_text_p]
    ], colWidths=[(letter[0]-72)/2]*2, hAlign="LEFT")

    t.setStyle(TableStyle([
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("TOPPADDING", (0,0), (-1,-1), 3),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ("LINEBELOW", (0,1), (0,1), 0.6, colors.black),
        ("LINEBELOW", (1,1), (1,1), 0.6, colors.black),
    ]))
    return t

def generate_np_pdf(data: dict, conditions: list[str], out_dir="generated_forms") -> str:
    """
    Generates a NEW PDF (not filling a template) styled like the NP-info form.
    """
    os.makedirs(out_dir, exist_ok=True)

    last = _s(data.get("p_last", "Patient")).replace(" ", "")
    first = _s(data.get("p_first", "")).replace(" ", "")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(out_dir, f"{last}_{first}_{ts}.pdf")

    doc = SimpleDocTemplate(
        out_path,
        pagesize=letter,
        leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36
    )

    story = []

    # =========================
    # PAGE 1: Patient + Medical
    # =========================
    story.append(Paragraph("UNION DENTAL GROUP", TITLE))
    story.append(Paragraph(
        "We are pleased to welcome you to our office. Please take a few minutes to fill out this form as completely as possible.",
        P
    ))
    story.append(Spacer(1, 10))

    story.append(Paragraph("PATIENT INFORMATION", H1))

    # What you collect online (filled), plus blanks for the rest of the “look”
    pi = []
    pi.append(_two_col_row("First name", data.get("p_first"), "Last name", data.get("p_last")))
    pi.append(_two_col_row("Middle Initial", data.get("p_mi"), "Date of Birth", data.get("p_dob")))
    pi.append(_two_col_row("Cell Phone", data.get("p_cell_phone"), "Alternative Phone", data.get("p_alt_phone")))
    pi.append(_two_col_row("Sex", data.get("p_sex"), "Marital Status", data.get("p_marital")))
    pi.append(_form_row("Email", data.get("p_email")))

    # Format-only blanks (not collected online)
    pi.append(_form_row("Address", data.get("p_address")))  # optional if you collect it; blank otherwise
    pi.append(_two_col_row("City", data.get("p_city"), "State", data.get("p_state")))
    pi.append(_form_row("Zip", data.get("p_zip")))

    story.append(_table_4(pi, [92, 155, 98, 155]))
    story.append(Spacer(1, 10))

    # Responsible Party (format-only)
    story.append(Paragraph("RESPONSIBLE PARTY (If different than patient)", H1))
    rp = []
    rp.append(_two_col_row("First name", "", "Last name", ""))
    rp.append(_two_col_row("Middle Initial", "", "Date of Birth", ""))
    rp.append(_form_row("Address", ""))
    rp.append(_two_col_row("City", "", "State", ""))
    rp.append(_form_row("Zip", ""))
    rp.append(_two_col_row("Home Phone", "", "Cell Phone", ""))
    story.append(_table_4(rp, [92, 155, 98, 155]))
    story.append(Spacer(1, 10))

    story.append(Paragraph("MEDICAL HISTORY", H1))

    # Physician info (format-only blanks)
    phys = []
    phys.append(_two_col_row("Physician Name", "", "Telephone #", ""))
    phys.append(_form_row("Fax #", ""))
    story.append(_table_4(phys, [92, 155, 98, 155]))
    story.append(Spacer(1, 6))

    mh = []
    mh.append(_two_col_row("Serious illnesses or operations?", _yn(data.get("m_serious")), "Phen-Fen or Redux?", _yn(data.get("m_phenfen"))))
    mh.append(_form_row("If yes, describe", data.get("m_serious_desc")))
    story.append(_table_4(mh, [165, 82, 145, 108]))
    story.append(Spacer(1, 8))

    story.append(Paragraph("WOMEN", H1))
    w = []
    w.append(_two_col_row("Pregnant / trying to get pregnant?", _yn(data.get("w_pregnant")),
                          "Taking oral contraceptives?", _yn(data.get("w_ocp"))))
    w.append(_two_col_row("Nursing?", _yn(data.get("w_nursing")), "", ""))
    story.append(_table_4(w, [170, 75, 160, 95]))
    story.append(Spacer(1, 8))

    story.append(_p("<b>Mark all that applies to you:</b>", SM))
    story.append(_checkbox_grid(conditions, cols=3))
    story.append(Spacer(1, 8))

    story.append(_big_text_two_cols(
        "LIST ALL MEDICATIONS YOU ARE CURRENTLY TAKING", _s(data.get("m_meds")),
        "ALLERGIES", _s(data.get("m_allergies"))
    ))
    story.append(Spacer(1, 10))

    story.append(_p(
        "To the best of my knowledge, the questions on this form have been accurately answered. "
        "I understand that providing incorrect information can be dangerous to my health.",
        SM
    ))
    story.append(Spacer(1, 8))

    sig1 = []
    # Prefer unique names; fallback to your current duplicated names if you haven’t changed them yet
    sig1.append(_form_row("SIGNATURE OF PATIENT, PARENT, OR GUARDIAN", data.get("sig_med") or data.get("p_sig")))
    sig1.append(_form_row("DATE", data.get("sig_med_date") or data.get("p_date")))
    story.append(_table_2(sig1, [260, 260]))

    # =========================
    # PAGE 2: Insurance
    # =========================
    story.append(PageBreak())
    story.append(Paragraph("INSURANCE INFORMATION", H2))

    has_ins = _s(data.get("pi_has"))
    # Always show the insurance page format. If no insurance, keep blanks.
    story.append(Paragraph("PRIMARY INSURANCE", H1))

    ins = []
    ins.append(_two_col_row("Insurance Company", data.get("pi_company") if has_ins == "Yes" else "",
                            "Member ID", data.get("pi_member_id") if has_ins == "Yes" else ""))
    ins.append(_two_col_row("Group #", data.get("pi_group") if has_ins == "Yes" else "",
                            "Patient is Subscriber?", _yn(data.get("pi_is_subscriber")) if has_ins == "Yes" else ""))
    ins.append(_two_col_row("Subscriber Name", data.get("pi_subscriber") if (has_ins == "Yes" and _s(data.get("pi_is_subscriber")) == "No") else "",
                            "Subscriber DOB", data.get("pi_dob") if (has_ins == "Yes" and _s(data.get("pi_is_subscriber")) == "No") else ""))
    ins.append(_form_row("Relationship to Subscriber", data.get("pi_rel") if (has_ins == "Yes" and _s(data.get("pi_is_subscriber")) == "No") else ""))
    story.append(_table_4(ins, [120, 140, 120, 140]))
    story.append(Spacer(1, 10))

    # Format-only blanks for the rest of the insurance form look
    story.append(Paragraph("INSURANCE COMPANY ADDRESS (Not collected online)", H1))
    ins_addr = []
    ins_addr.append(_form_row("Address", ""))
    ins_addr.append(_two_col_row("City", "", "State", ""))
    ins_addr.append(_form_row("Zip", ""))
    story.append(_table_4(ins_addr, [92, 155, 98, 155]))
    story.append(Spacer(1, 10))

    story.append(Paragraph("EMPLOYER / BUSINESS ADDRESS (Not collected online)", H1))
    emp = []
    emp.append(_form_row("Employer", ""))
    emp.append(_form_row("Business Address", ""))
    emp.append(_two_col_row("City", "", "State", ""))
    emp.append(_form_row("Zip", ""))
    story.append(_table_4(emp, [92, 155, 98, 155]))
    story.append(Spacer(1, 12))

    story.append(Paragraph("SIGNATURE ON FILE", H1))
    story.append(_p(
        "I certify that I, and/or my dependent(s), have insurance coverage. I authorize payment of dental benefits "
        "to the dentist. I authorize the use of my signature on all insurance submissions.",
        SM
    ))
    story.append(Spacer(1, 8))

    # These fields may not exist in your web form — they’ll appear blank (Style A)
    so = []
    so.append(_form_row("Subscriber Name", data.get("sig_ins_name")))
    so.append(_form_row("Relationship to the patient", data.get("sig_ins_rel_patient")))
    so.append(_form_row("Subscriber Signature", data.get("sig_ins")))
    so.append(_form_row("Date", data.get("sig_ins_date")))
    story.append(_table_2(so, [200, 320]))

    # =========================
    # PAGE 3: Financial Policy
    # =========================
    story.append(PageBreak())
    story.append(Paragraph("PAYMENT IS DUE AT THE TIME OF SERVICE", H2))

    # You can optionally inject your clinic policy text from config/db; if empty, we keep a short placeholder.
    policy_text = _s(data.get("fin_policy_text"))
    if not policy_text:
        policy_text = (
            "Payment is due at the time of service. For your convenience, we accept cash, credit card, and other "
            "office-approved payment methods. Please ask the front desk if you have questions about insurance benefits "
            "or estimated out-of-pocket costs."
        )
    story.append(Paragraph(policy_text.replace("\n", "<br/>"), SM))
    story.append(Spacer(1, 10))

    story.append(_p(
        "<b>I HAVE READ THE POLICIES DESCRIBED IN THIS FORM. I AGREE TO ABIDE BY THE TERMS OUTLINED.</b>",
        SM
    ))
    story.append(Spacer(1, 10))

    # Financial acknowledgement signature fields (may be blank if you don't collect separately)
    fin = []
    fin.append(_form_row("Patient's Name", data.get("sig_fin_name") or data.get("p_name")))
    fin.append(_form_row("Patient's Signature", data.get("sig_fin") or data.get("p_sig")))
    fin.append(_form_row("Date", data.get("sig_fin_date") or data.get("p_date")))

    story.append(_table_2(fin, [200, 320]))

    doc.build(story)
    return out_path