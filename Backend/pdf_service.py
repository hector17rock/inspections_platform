import os
from fpdf import FPDF
from datetime import datetime
from typing import Dict, Any

from paths import STATIC_DIR

class AuditPDF(FPDF):
    def header(self):
        # Clean white background with side-by-side logos (identical to print HTML)
        try:
            wm_logo_path = os.fspath(STATIC_DIR / "wm_logo.png")
            ap_logo_path = os.fspath(STATIC_DIR / "ap_logo.png")
            
            # Place Walmart logo
            if os.path.exists(wm_logo_path):
                self.image(wm_logo_path, x=10, y=8, h=10)
            
            # Vertical divider line (#cbd5e1)
            self.set_draw_color(203, 213, 225)
            self.line(46, 8, 46, 18)
            
            # Place AP logo
            if os.path.exists(ap_logo_path):
                self.image(ap_logo_path, x=49, y=8, h=10)
        except Exception:
            # Fallback title if logos fail
            self.set_font("Helvetica", "B", 11)
            self.set_text_color(0, 30, 96)
            self.set_xy(10, 8)
            self.cell(0, 10, "WALMART AP - TOURING FULFILLMENT OPD")
            
        # Right side aligned text
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(0, 30, 96)
        self.set_xy(110, 7)
        self.cell(96, 6, "REPORTE DE AUDITORÍA", ln=True, align="R")
        self.set_font("Helvetica", "", 8.5)
        self.set_text_color(100, 116, 139)
        self.set_x(110)
        self.cell(96, 4, "Touring Fulfillment OPD", ln=True, align="R")
        
        # Double navy line under the header banner
        self.set_draw_color(0, 30, 96)
        self.line(10, 21, 206, 21)
        self.line(10, 22, 206, 22)
        self.ln(10)

    def footer(self):
        # Page numbers
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f"Pagina {self.page_no()}/{{nb}} | Desarrollado por Hector & Toby", align="C")

def generate_audit_pdf(audit: Dict[str, Any]) -> str:
    """Generates a highly professional PDF file for the audit and returns its path."""
    pdf = AuditPDF(orientation="P", unit="mm", format="letter")
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()
    
    # --- METADATA SECTION ---
    pdf.set_y(32)
    pdf.set_text_color(30, 41, 59)  # Dark slate gray
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 6, "DATOS DE LA AUDITORIA", ln=True)
    pdf.set_draw_color(226, 232, 240)  # Light border
    pdf.line(10, 38, 206, 38)
    pdf.ln(2)
    
    # Grid info
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(45, 6, f"Tienda: #{audit['store_id']}", ln=False)
    pdf.cell(55, 6, f"Semana Fiscal: {audit['week_number'] or 'N/A'}", ln=False)
    pdf.cell(0, 6, f"Fecha: {audit['formatted_date']}", ln=True)
    pdf.ln(4)
    
    # --- SCORE CARD SECTION ---
    score = audit["score"]
    if score >= 90:
        bg_r, bg_g, bg_b = 232, 245, 233  # light green
        text_r, text_g, text_b = 42, 135, 3  # Walmart AP Green
        lbl = "SOBRESALIENTE"
    elif score >= 80:
        bg_r, bg_g, bg_b = 255, 253, 231  # light yellow
        text_r, text_g, text_b = 180, 83, 9   # Gold warning
        lbl = "NECESITA MEJORA"
    else:
        bg_r, bg_g, bg_b = 255, 235, 235  # light red
        text_r, text_g, text_b = 234, 17, 0   # Walmart AP Red
        lbl = "INSATISFACTORIO / CRITICO"
        
    pdf.set_fill_color(bg_r, bg_g, bg_b)
    pdf.set_draw_color(text_r, text_g, text_b)
    pdf.rect(10, pdf.get_y(), 196, 16, "DF")
    
    pdf.set_y(pdf.get_y() + 2)
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(text_r, text_g, text_b)
    pdf.cell(90, 12, f"SCORE DE CUMPLIMIENTO: {score}%", ln=False, align="C")
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(100, 12, f"CALIFICACION: {lbl}", ln=True, align="C")
    pdf.ln(6)
    
    # --- EXECUTIVE INSIGHTS ---
    pdf.set_fill_color(239, 246, 255)  # Light blue
    pdf.set_draw_color(191, 219, 254)
    pdf.rect(10, pdf.get_y(), 196, 18, "DF")
    pdf.set_y(pdf.get_y() + 2)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(0, 30, 96)
    pdf.cell(0, 4, "RESUMEN EJECUTIVO DE AP:", ln=True)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(30, 41, 59)
    if score >= 90:
        insight = "El departamento de OPD demuestra un alto nivel de cumplimiento operativo y controles robustos. Siga manteniendo estos estandares."
    elif score >= 80:
        insight = "Se detectaron algunas brechas menores en controles o seguridad. Se recomienda seguimiento con el Coach de OPD en las proximas 48 horas."
    else:
        insight = "ATENCION: Se identificaron vulnerabilidades criticas en la seguridad y/o cumplimiento. Se requiere plan de accion correctivo firmado inmediato."
    pdf.cell(0, 5, insight, ln=True)
    pdf.ln(6)
    
    # --- GENERAL NOTES (IF ANY) ---
    if audit["notes"]:
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(100, 116, 139)
        pdf.cell(0, 5, "COMENTARIOS GENERALES Y PLAN DE ACCION:", ln=True)
        pdf.set_font("Helvetica", "I", 9)
        pdf.set_text_color(30, 41, 59)
        pdf.multi_cell(0, 5, audit["notes"])
        pdf.ln(4)

    # --- CATEGORY RESPONSES ---
    # Group responses
    grouped = {}
    for r in audit["responses"]:
        if r["category"] not in grouped:
            grouped[r["category"]] = []
        grouped[r["category"]].append(r)
        
    for category, items in grouped.items():
        # Category header band
        pdf.set_fill_color(241, 245, 249)  # very light gray
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(0, 113, 206)
        pdf.cell(0, 7, f" {category.upper()}", ln=True, fill=True)
        pdf.ln(1)
        
        for r in items:
            pdf.set_font("Helvetica", "", 9.5)
            pdf.set_text_color(30, 41, 59)
            
            # Print question (wrapped to avoid overflowing the page margins)
            start_x = pdf.get_x()
            start_y = pdf.get_y()
            pdf.multi_cell(165, 5, f"[-] {r['question']}")
            end_y = pdf.get_y()
            
            # Print response badge next to the question
            pdf.set_xy(start_x + 165, start_y)
            if r["status"] == "yes":
                pdf.set_text_color(42, 135, 3)
                pdf.set_font("Helvetica", "B", 9)
                pdf.cell(31, 5, "CUMPLE", ln=True, align="R")
            elif r["status"] == "no":
                pdf.set_text_color(234, 17, 0)
                pdf.set_font("Helvetica", "B", 9)
                pdf.cell(31, 5, "NO CUMPLE", ln=True, align="R")
            else:
                pdf.set_text_color(100, 116, 139)
                pdf.set_font("Helvetica", "B", 9)
                pdf.cell(31, 5, "N/A", ln=True, align="R")
                
            # If there was a comment/fail explanation
            pdf.set_y(max(end_y, pdf.get_y()))
            if r["status"] == "no" and r["comment"]:
                pdf.set_x(15)
                pdf.set_font("Helvetica", "BI", 8.5)
                pdf.set_text_color(153, 27, 27)
                pdf.multi_cell(181, 4.5, f"Hallazgo: {r['comment']}")
                pdf.ln(1)
            elif r["comment"]:
                pdf.set_x(15)
                pdf.set_font("Helvetica", "I", 8.5)
                pdf.set_text_color(100, 116, 139)
                pdf.multi_cell(181, 4.5, f"Nota: {r['comment']}")
                pdf.ln(1)
                
            pdf.ln(1)
        pdf.ln(2)
        
    # --- SIGNATURE BLOCK ---
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(120, 53, 15)  # dark gold
    pdf.cell(0, 5, "COMPROMISO & FIRMAS DE CIERRE", ln=True)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(120, 53, 15)
    pdf.multi_cell(0, 4, "Este reporte certifica que se realizo el Touring Fulfillment OPD conforme a las guias de Walmart de Proteccion de Activos. Los hallazgos identificados como 'NO CUMPLE' requieren una solucion inmediata.")
    pdf.ln(6)
    
    # Signature Lines side-by-side
    sig_y = pdf.get_y()
    pdf.set_text_color(120, 53, 15)
    pdf.set_font("Helvetica", "", 8.5)
    pdf.line(10, sig_y + 8, 90, sig_y + 8)
    pdf.set_xy(10, sig_y + 9)
    pdf.cell(80, 5, "Firma AP Investigator", ln=False)
    
    pdf.line(116, sig_y + 8, 196, sig_y + 8)
    pdf.set_xy(116, sig_y + 9)
    if audit.get("discussed_with") and audit.get("discussed_with") != "No fue discutida con un Gerente":
        pdf.cell(80, 5, f"Firma Gerente ({audit['discussed_with'][:20]}...)", ln=True)
    else:
        pdf.cell(80, 5, "Firma Coach/TL/Gerente OPD", ln=True)

    # Save to file path inside audits_archive
    archive_dir = os.path.join(os.path.dirname(__file__), "audits_archive")
    os.makedirs(archive_dir, exist_ok=True)
    clean_date = audit["created_at"][:16].replace(":", "-").replace("T", "_")
    filename = f"Auditoria_Fulfillment_Tienda_{audit['store_id']}_{clean_date}.pdf"
    filepath = os.path.join(archive_dir, filename)
    
    pdf.output(filepath)
    return filepath


class AvailabilityPDF(FPDF):
    def header(self):
        try:
            wm_logo_path = os.fspath(STATIC_DIR / "wm_logo.png")
            ap_logo_path = os.fspath(STATIC_DIR / "ap_logo.png")
            
            if os.path.exists(wm_logo_path):
                self.image(wm_logo_path, x=10, y=8, h=10)
            
            self.set_draw_color(203, 213, 225)
            self.line(46, 8, 46, 18)
            
            if os.path.exists(ap_logo_path):
                self.image(ap_logo_path, x=49, y=8, h=10)
        except Exception:
            self.set_font("Helvetica", "B", 11)
            self.set_text_color(0, 30, 96)
            self.set_xy(10, 8)
            self.cell(0, 10, "WALMART AP - AVAILABILITY AUDIT MARKET 801")
            
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(0, 30, 96)
        self.set_xy(110, 7)
        self.cell(96, 6, "REPORTE DE DISPONIBILIDAD", ln=True, align="R")
        self.set_font("Helvetica", "", 8.5)
        self.set_text_color(100, 116, 139)
        self.set_x(110)
        self.cell(96, 4, "Availability Audit - Market 801", ln=True, align="R")
        
        self.set_draw_color(0, 30, 96)
        self.line(10, 21, 206, 21)
        self.line(10, 22, 206, 22)
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f"Pagina {self.page_no()}/{{nb}} | Desarrollado por Hector & Toby", align="C")


def generate_availability_pdf(audit: Dict[str, Any]) -> str:
    """Generates a highly professional PDF for the Availability Audit."""
    pdf = AvailabilityPDF(orientation="P", unit="mm", format="letter")
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()
    
    # --- METADATA SECTION ---
    pdf.set_y(32)
    pdf.set_text_color(30, 41, 59)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 6, "DATOS DE LA AUDITORIA DE DISPONIBILIDAD", ln=True)
    pdf.set_draw_color(226, 232, 240)
    pdf.line(10, 38, 206, 38)
    pdf.ln(2)
    
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(45, 6, f"Tienda: #{audit['store_id']}", ln=False)
    pdf.cell(55, 6, f"Semana Fiscal: {audit['week_number'] or 'N/A'}", ln=False)
    pdf.cell(0, 6, f"Auditor AP: {audit['auditor_name']}", ln=True)
    
    pdf.cell(100, 6, f"Fecha: {audit['formatted_date']}", ln=False)
    pdf.cell(0, 6, f"Discutida Con: {audit['discussed_with'] or 'No indicada'}", ln=True)
    pdf.ln(4)
    
    # --- VALUE DISPLAY CARD ---
    val = audit["total_understated_value"]
    pdf.set_fill_color(239, 246, 255)  # Light blue
    pdf.set_draw_color(0, 113, 206)     # Walmart Blue
    pdf.rect(10, pdf.get_y(), 196, 16, "DF")
    
    pdf.set_y(pdf.get_y() + 2)
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(0, 30, 96)
    pdf.cell(90, 12, f"VALOR SUBESTIMADO (PI): ${val:.2f}", ln=False, align="C")
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(100, 12, f"ESTADO DE AUDITORIA: COMPLETA", ln=True, align="C")
    pdf.ln(6)
    
    # --- GENERAL NOTES ---
    if audit.get("notes"):
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(100, 116, 139)
        pdf.cell(0, 5, "COMENTARIOS GENERALES Y OBSERVACIONES:", ln=True)
        pdf.set_font("Helvetica", "I", 9)
        pdf.set_text_color(30, 41, 59)
        pdf.multi_cell(0, 5, audit["notes"])
        pdf.ln(4)

    # --- MODULAR ITEMS ---
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(0, 30, 96)
    pdf.cell(0, 6, "MODULARES Y ITEMS EVALUADOS", ln=True)
    pdf.ln(1)
    
    for item in audit["modular_items"]:
        pdf.set_fill_color(241, 245, 249)
        pdf.set_font("Helvetica", "B", 9.5)
        pdf.set_text_color(0, 113, 206)
        pdf.cell(0, 6, f" Dept {item['department']} | Modular {item['modular_verified']} (Secuencia: {item['modular_sequence']})", ln=True, fill=True)
        
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(30, 41, 59)
        
        # Details
        pdf.cell(60, 5, f"Fecha Verif: {item['verification_date']}", ln=False)
        pdf.cell(70, 5, f"Outs Verificados: {item['outs_verified']}", ln=False)
        pdf.cell(0, 5, f"PI Understated: {item['understated_pi_found']}", ln=True)
        
        if item['understated_pi_found'] == 'SI':
            pdf.set_font("Helvetica", "B", 8.5)
            pdf.set_text_color(153, 27, 27)
            pdf.cell(0, 5, f"  >> Items Encontrados: {item['items_found']} | Corregidos: {item['items_corrected']} | Valor: ${item['understated_value']:.2f}", ln=True)
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(30, 41, 59)
            
        # Sub-items with UPC and QTY
        if item.get("details"):
            pdf.set_font("Helvetica", "B", 8.5)
            pdf.set_text_color(0, 30, 96)
            pdf.cell(0, 5, "  >> Detalle de Productos (UPC / QTY):", ln=True)
            pdf.set_font("Helvetica", "", 8.5)
            pdf.set_text_color(51, 65, 85)
            for d in item["details"]:
                lbl_t = "Out con On Hand (OH)" if d["item_type"] == "OH" else "PI Understated"
                pdf.cell(0, 4.5, f"     * [{lbl_t}] UPC: {d['upc']} | Cantidad (QTY): {d['qty']}", ln=True)
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(30, 41, 59)
            
        if item.get("comments"):
            pdf.set_font("Helvetica", "I", 8.5)
            pdf.set_text_color(100, 116, 139)
            pdf.multi_cell(0, 4.5, f"  Comentario: {item['comments']}")
            pdf.ln(1)
        pdf.ln(2)
        
    # --- PROCESS VALIDATION ---
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(0, 30, 96)
    pdf.cell(0, 6, "VALIDACION DE PROCESOS (TRASTIENDA)", ln=True)
    pdf.ln(1)
    
    processes = [
        ("Vagones finalizados (Semanal)", audit["process_vagones_status"], audit["process_vagones_comments"]),
        ("Pin point diariamente (10 Semanal)", audit["process_pinpoint_status"], audit["process_pinpoint_comments"])
    ]
    
    for title, status, comment in processes:
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(30, 41, 59)
        pdf.cell(100, 5, f"- {title}:", ln=False)
        
        if status == "SI" or status == "X" or status == "yes":
            pdf.set_text_color(42, 135, 3)
            pdf.cell(30, 5, "SI", ln=True)
        elif status == "NO" or status == "no":
            pdf.set_text_color(234, 17, 0)
            pdf.cell(30, 5, "NO", ln=True)
        else:
            pdf.set_text_color(100, 116, 139)
            pdf.cell(30, 5, "N/A", ln=True)
            
        if comment:
            pdf.set_x(15)
            pdf.set_font("Helvetica", "I", 8.5)
            pdf.set_text_color(100, 116, 139)
            pdf.multi_cell(181, 4, f"Obs: {comment}")
            pdf.ln(1)
        pdf.ln(1)
        
    # Render Process 3 (Bines & Topes)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(30, 41, 59)
    pdf.cell(100, 5, "- Bines cumplen con estandares (15 Semanal):", ln=False)
    
    status = audit["process_bines_status"]
    if status == "SI" or status == "X" or status == "yes":
        pdf.set_text_color(42, 135, 3)
        pdf.cell(30, 5, "SI", ln=True)
    elif status == "NO" or status == "no":
        pdf.set_text_color(234, 17, 0)
        pdf.cell(30, 5, "NO", ln=True)
    else:
        pdf.set_text_color(100, 116, 139)
        pdf.cell(30, 5, "N/A", ln=True)
        
    # Render Bines findings list
    import json
    bines_list = []
    try:
        bines_list = json.loads(audit["process_bines_comments"])
    except Exception:
        if audit.get("process_bines_comments") or audit.get("process_bines_loc"):
            bines_list = [{"loc": audit.get("process_bines_loc", ""), "comments": audit.get("process_bines_comments", "")}]
            
    if bines_list:
        pdf.set_x(15)
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(0, 30, 96)
        pdf.cell(0, 4, "  Hallazgos en Bines (Backroom):", ln=True)
        pdf.set_font("Helvetica", "I", 8)
        pdf.set_text_color(100, 116, 139)
        for b in bines_list:
            loc_str = f"[{b['loc']}] " if b.get('loc') else ""
            pdf.set_x(18)
            pdf.cell(0, 4, f"* {loc_str}{b['comments']}", ln=True)
            
    # Render Topes findings list
    topes_list = []
    try:
        topes_list = json.loads(audit["process_topes_comments"])
    except Exception:
        if audit.get("process_topes_comments") or audit.get("process_topes_loc"):
            topes_list = [{"loc": audit.get("process_topes_loc", ""), "comments": audit.get("process_topes_comments", "")}]
            
    if topes_list:
        pdf.ln(1)
        pdf.set_x(15)
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(0, 30, 96)
        pdf.cell(0, 4, "  Hallazgos en Topes (Risers):", ln=True)
        pdf.set_font("Helvetica", "I", 8)
        pdf.set_text_color(100, 116, 139)
        for t in topes_list:
            loc_str = f"[{t['loc']}] " if t.get('loc') else ""
            pdf.set_x(18)
            pdf.cell(0, 4, f"* {loc_str}{t['comments']}", ln=True)
            
    # Render WACOS findings list
    wacos_list = []
    try:
        wacos_list = json.loads(audit["process_wacos_comments"])
    except Exception:
        if audit.get("process_wacos_comments") or audit.get("process_wacos_loc"):
            wacos_list = [{"loc": audit.get("process_wacos_loc", ""), "comments": audit.get("process_wacos_comments", "")}]
            
    if wacos_list:
        pdf.ln(1)
        pdf.set_x(15)
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(0, 30, 96)
        pdf.cell(0, 4, "  Hallazgos en WACOS:", ln=True)
        pdf.set_font("Helvetica", "I", 8)
        pdf.set_text_color(100, 116, 139)
        for w in wacos_list:
            loc_str = f"[{w['loc']}] " if w.get('loc') else ""
            pdf.set_x(18)
            pdf.cell(0, 4, f"* {loc_str}{w['comments']}", ln=True)
    pdf.ln(1)

    # --- SIGNATURE BLOCK ---
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(120, 53, 15)
    pdf.cell(0, 5, "COMPROMISO & SIGNATURES", ln=True)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(120, 53, 15)
    pdf.multi_cell(0, 4, "Reporte de Auditoria de Disponibilidad de Inventario en Piso de Ventas y Procesos de Trastienda OPD. Se asumen compromisos de correccion inmediata de modular sequence y PI Understated.")
    pdf.ln(6)
    
    sig_y = pdf.get_y()
    pdf.line(10, sig_y + 8, 90, sig_y + 8)
    pdf.set_xy(10, sig_y + 9)
    pdf.cell(80, 5, "Firma AP Investigator / Auditor", ln=True)

    archive_dir = os.path.join(os.path.dirname(__file__), "audits_archive")
    os.makedirs(archive_dir, exist_ok=True)
    clean_date = audit["created_at"][:16].replace(":", "-").replace("T", "_")
    filename = f"Auditoria_Availability_Tienda_{audit['store_id']}_{clean_date}.pdf"
    filepath = os.path.join(archive_dir, filename)
    
    pdf.output(filepath)
    return filepath
