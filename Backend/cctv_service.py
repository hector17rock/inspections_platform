import os
import sqlite3
from datetime import datetime
from typing import List, Dict, Any
from fpdf import FPDF

from paths import FRONTEND_DIR, STATIC_DIR

DB_PATH = os.path.join(os.path.dirname(__file__), "audits.db")
UPLOAD_DIR = os.fspath(STATIC_DIR / "uploads" / "cctv_photos")
ARCHIVE_DIR = os.path.join(os.path.dirname(__file__), "audits_archive")

class CctvPDF(FPDF):
    def header(self):
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
            self.cell(0, 10, "WALMART AP - CCTV INVESTIGATION RECORD")
            
        # Right side aligned text
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(0, 30, 96)
        self.set_xy(110, 7)
        self.cell(96, 6, "RECORD DE INVESTIGACION CCTV", ln=True, align="R")
        self.set_font("Helvetica", "", 8.5)
        self.set_text_color(100, 116, 139)
        self.set_x(110)
        self.cell(96, 4, "Asset Protection Services", ln=True, align="R")
        
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
        self.cell(0, 10, f"Pagina {self.page_no()}/{{nb}} | Walmart Asset Protection", align="C")


def format_spanish_date(date_str: str) -> str:
    """Converts a YYYY-MM-DD date string into a beautiful Spanish 'Mes Día, Año' format."""
    if not date_str:
        return "N/A"
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        months = [
            "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
            "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
        ]
        return f"{months[dt.month - 1]} {dt.day}, {dt.year}"
    except Exception:
        return date_str


def safe_str(text: str) -> str:
    """Replaces common Spanish accented characters to ensure standard FPDF Latin-1 compatibility."""
    if not text:
        return ""
    replacements = {
        'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
        'Á': 'A', 'É': 'E', 'Í': 'I', 'Ó': 'O', 'Ú': 'U',
        'ñ': 'n', 'Ñ': 'N', 'ü': 'u', 'Ü': 'U'
    }
    cleaned = "".join(replacements.get(c, c) for c in text)
    return cleaned.encode('latin-1', 'replace').decode('latin-1')


def init_db():
    """Initializes the SQLite database with CCTV tables."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # CCTV Investigations main table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS cctv_investigations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        store_id TEXT NOT NULL,
        investigation_date TEXT NOT NULL,
        video_date TEXT NOT NULL,
        apasm TEXT NOT NULL,
        api TEXT NOT NULL,
        subject_name TEXT DEFAULT '',
        created_at TEXT NOT NULL,
        with_photos INTEGER NOT NULL, -- 0 = No, 1 = Yes
        notes TEXT
    )
    """)
    
    # CCTV Events/Timeline table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS cctv_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        investigation_id INTEGER NOT NULL,
        camera TEXT NOT NULL,
        time_stamp TEXT NOT NULL,
        description TEXT NOT NULL,
        photo_path TEXT,
        FOREIGN KEY (investigation_id) REFERENCES cctv_investigations (id) ON DELETE CASCADE
    )
    """)
    
    conn.commit()
    conn.close()
    
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    os.makedirs(ARCHIVE_DIR, exist_ok=True)


def save_investigation(
    store_id: str,
    investigation_date: str,
    video_date: str,
    apasm: str,
    api: str,
    subject_name: str,
    with_photos: bool,
    notes: str,
    events: List[Dict[str, Any]]
) -> int:
    """Saves a CCTV investigation and its timeline events."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    created_at = datetime.now().isoformat()
    photos_val = 1 if with_photos else 0
    
    cursor.execute("""
        INSERT INTO cctv_investigations 
        (store_id, investigation_date, video_date, apasm, api, subject_name, created_at, with_photos, notes) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (store_id, investigation_date, video_date, apasm, api, subject_name, created_at, photos_val, notes))
    
    investigation_id = cursor.lastrowid
    
    for event in events:
        cursor.execute("""
            INSERT INTO cctv_events 
            (investigation_id, camera, time_stamp, description, photo_path) 
            VALUES (?, ?, ?, ?, ?)
        """, (investigation_id, event["camera"], event["time_stamp"], event["description"], event.get("photo_path")))
        
    conn.commit()
    conn.close()
    return investigation_id


def get_all_investigations() -> List[Dict[str, Any]]:
    """Returns a list of all CCTV investigations with metadata."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM cctv_investigations ORDER BY created_at DESC")
    rows = cursor.fetchall()
    
    results = []
    for r in rows:
        dt = datetime.fromisoformat(r["created_at"])
        formatted_date = dt.strftime("%b %d, %Y - %I:%M %p")
        results.append({
            "id": r["id"],
            "store_id": r["store_id"],
            "investigation_date": r["investigation_date"],
            "formatted_investigation_date": format_spanish_date(r["investigation_date"]),
            "video_date": r["video_date"],
            "formatted_video_date": format_spanish_date(r["video_date"]),
            "apasm": r["apasm"],
            "api": r["api"],
            "subject_name": r["subject_name"],
            "created_at": r["created_at"],
            "formatted_date": formatted_date,
            "with_photos": bool(r["with_photos"]),
            "notes": r["notes"]
        })
        
    conn.close()
    return results


def get_investigation_details(investigation_id: int) -> Dict[str, Any]:
    """Retrieves full details of a specific CCTV investigation."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM cctv_investigations WHERE id = ?", (investigation_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None
        
    dt = datetime.fromisoformat(row["created_at"])
    formatted_date = dt.strftime("%b %d, %Y - %I:%M %p")
    
    data = {
        "id": row["id"],
        "store_id": row["store_id"],
        "investigation_date": row["investigation_date"],
        "formatted_investigation_date": format_spanish_date(row["investigation_date"]),
        "video_date": row["video_date"],
        "formatted_video_date": format_spanish_date(row["video_date"]),
        "apasm": row["apasm"],
        "api": row["api"],
        "subject_name": row["subject_name"],
        "created_at": row["created_at"],
        "formatted_date": formatted_date,
        "with_photos": bool(row["with_photos"]),
        "notes": row["notes"],
        "events": []
    }
    
    cursor.execute("SELECT * FROM cctv_events WHERE investigation_id = ?", (investigation_id,))
    event_rows = cursor.fetchall()
    for e in event_rows:
        data["events"].append({
            "id": e["id"],
            "camera": e["camera"],
            "time_stamp": e["time_stamp"],
            "description": e["description"],
            "photo_path": e["photo_path"]
        })
        
    conn.close()
    return data


def delete_investigation(investigation_id: int):
    """Deletes an investigation, its events, and any associated image files."""
    data = get_investigation_details(investigation_id)
    if not data:
        return
        
    # Delete image files
    for event in data["events"]:
        if event["photo_path"]:
            full_path = FRONTEND_DIR / event["photo_path"].lstrip("/")
            if full_path.exists():
                try:
                    os.remove(full_path)
                except Exception:
                    pass
                    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM cctv_investigations WHERE id = ?", (investigation_id,))
    cursor.execute("DELETE FROM cctv_events WHERE investigation_id = ?", (investigation_id,))
    conn.commit()
    conn.close()


def generate_cctv_pdf(investigation: Dict[str, Any]) -> str:
    """Generates a professional PDF of the CCTV investigation matching the printable HTML design."""
    pdf = CctvPDF(orientation="P", unit="mm", format="letter")
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()
    
    # --- METADATA SECTION ---
    pdf.set_y(32)
    pdf.set_text_color(0, 30, 96) # var(--blue)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 6, "DETALLES DEL REGISTRO", ln=True)
    pdf.set_draw_color(226, 232, 240)
    pdf.line(10, 38, 206, 38)
    pdf.ln(3)
    
    # Metadata info grid (matches the 2-column layout in the HTML card)
    pdf.set_font("Helvetica", "B", 7.5)
    pdf.set_text_color(100, 116, 139) # var(--muted)
    pdf.cell(95, 4, "NUMERO DE TIENDA", ln=False)
    pdf.cell(95, 4, "SUJETO / ASOCIADO", ln=True)
    
    pdf.set_font("Helvetica", "", 9.5)
    pdf.set_text_color(30, 41, 59) # var(--text)
    pdf.cell(95, 5, f"Tienda #{investigation['store_id']}", ln=False)
    pdf.cell(95, 5, f"{safe_str(investigation['subject_name'] or 'N/A')}", ln=True)
    pdf.ln(2)
    
    pdf.set_font("Helvetica", "B", 7.5)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(95, 4, "FECHA DEL VIDEO", ln=False)
    pdf.cell(95, 4, "FECHA DE INVESTIGACION", ln=True)
    
    pdf.set_font("Helvetica", "", 9.5)
    pdf.set_text_color(30, 41, 59)
    pdf.cell(95, 5, f"{safe_str(investigation['formatted_video_date'])}", ln=False)
    pdf.cell(95, 5, f"{safe_str(investigation['formatted_investigation_date'])}", ln=True)
    pdf.ln(2)
    
    pdf.set_font("Helvetica", "B", 7.5)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(95, 4, "INVESTIGADOR (API)", ln=False)
    pdf.cell(95, 4, "SUPERVISOR (APASM)", ln=True)
    
    pdf.set_font("Helvetica", "", 9.5)
    pdf.set_text_color(30, 41, 59)
    pdf.cell(95, 5, f"{safe_str(investigation['api'])}", ln=False)
    pdf.cell(95, 5, f"{safe_str(investigation['apasm'])}", ln=True)
    pdf.ln(5)
    
    # --- RESUMEN EJECUTIVO / NOTAS ---
    if investigation["notes"]:
        pdf.set_fill_color(255, 255, 255)
        
        pdf.set_font("Helvetica", "B", 8.5)
        pdf.set_text_color(0, 30, 96)
        pdf.cell(0, 5, "NARRATIVA Y COMENTARIOS DEL CASO", ln=True)
        pdf.ln(1)
        pdf.set_font("Helvetica", "I", 9.5)
        pdf.set_text_color(30, 41, 59)
        pdf.multi_cell(0, 5, safe_str(investigation["notes"]))
        pdf.ln(4)
        
    # --- TIMELINE SECTION ---
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(0, 30, 96)
    pdf.cell(0, 6, "CRONOLOGIA DEL INCIDENTE", ln=True)
    pdf.set_draw_color(226, 232, 240)
    pdf.line(10, pdf.get_y() + 1, 206, pdf.get_y() + 1)
    pdf.ln(3)
    
    for idx, event in enumerate(investigation["events"]):
        # Header block matching .event-header-row style
        pdf.set_fill_color(241, 245, 249) # var(--gray-light)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(0, 30, 96)
        
        # Draw background band for header row
        header_y = pdf.get_y()
        pdf.rect(10, header_y, 196, 7, style="F")
        pdf.set_xy(12, header_y + 1)
        
        pdf.cell(40, 5, f"EVENTO #{idx+1}", ln=False)
        pdf.set_text_color(30, 41, 59)
        pdf.cell(100, 5, f"Camara: {safe_str(event['camera'])}", ln=False)
        pdf.set_text_color(100, 116, 139)
        pdf.cell(44, 5, f"{safe_str(event['time_stamp'])}", ln=True, align="R")
        pdf.ln(2)
        
        # Event Description
        pdf.set_font("Helvetica", "", 9.5)
        pdf.set_text_color(30, 41, 59)
        pdf.multi_cell(0, 5, safe_str(event["description"]))
        pdf.ln(2)
        
        # Photo rendering (if with_photos and photo exists)
        if investigation["with_photos"] and event["photo_path"]:
            full_img_path = FRONTEND_DIR / event["photo_path"].lstrip("/")
            if full_img_path.exists():
                try:
                    remaining_space = 279 - pdf.get_y() - 20
                    if remaining_space < 50:
                        pdf.add_page()
                    pdf.image(os.fspath(full_img_path), x=15, y=pdf.get_y(), h=45)
                    pdf.set_y(pdf.get_y() + 47)
                except Exception as ex:
                    pdf.set_font("Helvetica", "I", 8.5)
                    pdf.set_text_color(234, 17, 0)
                    pdf.cell(0, 5, f"[Error al cargar foto: {str(ex)}]", ln=True)
            else:
                pdf.set_font("Helvetica", "I", 8.5)
                pdf.set_text_color(100, 116, 139)
                pdf.cell(0, 5, "[Foto no encontrada en el servidor]", ln=True)
            pdf.ln(2)
            
    # --- SIGNATURE & CERTIFICATION BLOCK ---
    pdf.ln(4)
    # Check space for signature (requires ~40mm)
    if (279 - pdf.get_y() - 20) < 40:
        pdf.add_page()
        
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(0, 30, 96) # var(--blue)
    pdf.cell(0, 5, "COMPROMISO & CERTIFICACION DE REGISTROS", ln=True)
    pdf.ln(12) # Leave space for physical signature above the lines
    
    # Signature Lines
    sig_y = pdf.get_y()
    pdf.set_draw_color(0, 0, 0)
    pdf.line(10, sig_y, 90, sig_y)
    pdf.set_xy(10, sig_y + 1)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(30, 41, 59)
    pdf.cell(80, 5, f"Firma API (Investigador): {safe_str(investigation['api'])}", ln=False)
    
    pdf.line(116, sig_y, 196, sig_y)
    pdf.set_xy(116, sig_y + 1)
    pdf.cell(80, 5, f"Firma APASM (Supervisor): {safe_str(investigation['apasm'])}", ln=True)
    
    pdf.ln(4)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(100, 116, 139) # var(--muted)
    pdf.multi_cell(0, 4.5, safe_str("Este registro certifica la veracidad de los hechos observados y grabados en video de acuerdo con los protocolos de seguridad de Walmart Asset Protection."))

    clean_date = investigation["created_at"][:16].replace(":", "-").replace("T", "_")
    filename = f"Investigacion_CCTV_Tienda_{investigation['store_id']}_{clean_date}.pdf"
    filepath = os.path.join(ARCHIVE_DIR, filename)
    
    pdf.output(filepath)
    return filepath
