import os
import sqlite3
from datetime import datetime
from typing import List, Dict, Any

DB_PATH = os.path.join(os.path.dirname(__file__), "audits.db")

AUDIT_CATEGORIES = {
    "Safety": [
        "Check for damaged equipment (carts, dollies, handles). Remove from use any damaged equipment and order repair/replacement.",
        "Verify totes on carts are stacked no more than five high and the corner brackets are intact.",
        "Check the freezers/coolers for ice buildup.",
        "Verify associates wear safety vests when dispensing.",
        "Verify associates use handles to pull orders to cars when dispensing."
    ],
    "Controls": [
        "Verify the access door is alarmed and only opened with a key card or fob.",
        "Verify the keypad code is not the store number, a repetitive (1111) number, or sequential (1234) numbers.",
        "Verify the high-ticket cage is locked and only contains items considered high ticket.",
        "Verify there are no personal belongings in the store fulfillment area.",
        "Verify that Alpha keys are secured.",
        "Verify all removed merchandise protection devices are returned to their storage location."
    ],
    "Audits": [
        "Verify QCs are completed in GIF.",
        "Best practice: verify orders with high ticket items or quantities that seem out of the ordinary.",
        "Verify orders needing attention are worked within 24 hours. These are items that are expired, rescheduled, cancelled, returned, or orders to receive (ex. special order tires)."
    ],
    "Reporting": [
        "Use the Keybox report on AP1 to verify keys were returned and were returned by the same person who checked them out.",
        "Use the ISA Detail Report section of the Store ISA Report on AP1 to review nil pick adjustments.",
        "Use the Claims Disposition report on AP1 to verify team leads are processing claims."
    ],
    "Spark Shop / Delivery": [
        "Verify associates know the process for reporting driver issues, both critical and non-critical.",
        "Verify AP associates know how to enter Spark Shopping and Delivery incidents in Auror.",
        "Verify the Return with Me process, including item accuracy and QR code use."
    ],
    "Claims": [
        "Verify claims are processed.",
        "Verify returns are either returned to stock or processed as a claim."
    ]
}

def init_db():
    """Initializes the SQLite database with proper schema."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Audits main table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS audits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        store_id TEXT NOT NULL,
        auditor_name TEXT NOT NULL,
        created_at TEXT NOT NULL,
        score REAL NOT NULL,
        notes TEXT,
        week_number TEXT DEFAULT '',
        discussed_with TEXT DEFAULT ''
    )
    """)
    
    # Check if columns exist, if not add them (for backward compatibility)
    try:
        cursor.execute("ALTER TABLE audits ADD COLUMN week_number TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass
        
    try:
        cursor.execute("ALTER TABLE audits ADD COLUMN discussed_with TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass
    
    # Audit responses/questions table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS audit_responses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        audit_id INTEGER NOT NULL,
        category TEXT NOT NULL,
        question TEXT NOT NULL,
        status TEXT NOT NULL, -- 'yes', 'no', 'na'
        comment TEXT,
        FOREIGN KEY (audit_id) REFERENCES audits (id) ON DELETE CASCADE
    )
    """)
    
    conn.commit()
    conn.close()

def get_questions_schema() -> Dict[str, List[str]]:
    """Returns the checklist category and question mapping."""
    return AUDIT_CATEGORIES

def save_audit(store_id: str, auditor_name: str, responses: List[Dict[str, Any]], notes: str = "", week_number: str = "", discussed_with: str = "") -> int:
    """Saves a complete audit report and calculates the final score."""
    # Score calculation: Yes / (Yes + No) as percentage
    yes_count = sum(1 for r in responses if r["status"] == "yes")
    no_count = sum(1 for r in responses if r["status"] == "no")
    total_eval = yes_count + no_count
    score = (yes_count / total_eval * 100.0) if total_eval > 0 else 100.0
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    created_at = datetime.now().isoformat()
    
    cursor.execute(
        "INSERT INTO audits (store_id, auditor_name, created_at, score, notes, week_number, discussed_with) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (store_id, auditor_name, created_at, score, notes, week_number, discussed_with)
    )
    audit_id = cursor.lastrowid
    
    for r in responses:
        cursor.execute(
            "INSERT INTO audit_responses (audit_id, category, question, status, comment) VALUES (?, ?, ?, ?, ?)",
            (audit_id, r["category"], r["question"], r["status"], r.get("comment", ""))
        )
        
    conn.commit()
    conn.close()
    return audit_id

def get_all_audits() -> List[Dict[str, Any]]:
    """Returns list of all saved audits with metadata."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, store_id, auditor_name, created_at, score, notes, week_number, discussed_with FROM audits ORDER BY created_at DESC")
    rows = cursor.fetchall()
    
    audits = []
    for r in rows:
        # Format the datetime nicely
        dt = datetime.fromisoformat(r["created_at"])
        formatted_date = dt.strftime("%b %d, %Y - %I:%M %p")
        audits.append({
            "id": r["id"],
            "store_id": r["store_id"],
            "auditor_name": r["auditor_name"],
            "created_at": r["created_at"],
            "formatted_date": formatted_date,
            "score": round(r["score"], 1),
            "notes": r["notes"],
            "week_number": r["week_number"] if "week_number" in r.keys() else "",
            "discussed_with": r["discussed_with"] if "discussed_with" in r.keys() else ""
        })
        
    conn.close()
    return audits

def get_audit_details(audit_id: int) -> Dict[str, Any]:
    """Retrieves metadata and all responses for a single audit ID."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, store_id, auditor_name, created_at, score, notes, week_number, discussed_with FROM audits WHERE id = ?", (audit_id,))
    audit_row = cursor.fetchone()
    if not audit_row:
        conn.close()
        return None
        
    dt = datetime.fromisoformat(audit_row["created_at"])
    formatted_date = dt.strftime("%b %d, %Y - %I:%M %p")
    
    audit_data = {
        "id": audit_row["id"],
        "store_id": audit_row["store_id"],
        "auditor_name": audit_row["auditor_name"],
        "created_at": audit_row["created_at"],
        "formatted_date": formatted_date,
        "score": round(audit_row["score"], 1),
        "notes": audit_row["notes"],
        "week_number": audit_row["week_number"] if "week_number" in audit_row.keys() else "",
        "discussed_with": audit_row["discussed_with"] if "discussed_with" in audit_row.keys() else "",
        "responses": []
    }
    
    cursor.execute("SELECT id, category, question, status, comment FROM audit_responses WHERE audit_id = ?", (audit_id,))
    response_rows = cursor.fetchall()
    
    for r in response_rows:
        audit_data["responses"].append({
            "category": r["category"],
            "question": r["question"],
            "status": r["status"],
            "comment": r["comment"]
        })
        
    conn.close()
    return audit_data

def delete_audit(audit_id: int):
    """Deletes an audit and its cascading responses."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM audits WHERE id = ?", (audit_id,))
    cursor.execute("DELETE FROM audit_responses WHERE audit_id = ?", (audit_id,))
    conn.commit()
    conn.close()

def export_audit_to_file(audit_id: int) -> str:
    """Exports audit details to a beautiful, readable text report file on disk."""
    audit = get_audit_details(audit_id)
    if not audit:
        return ""
        
    archive_dir = os.path.join(os.path.dirname(__file__), "audits_archive")
    os.makedirs(archive_dir, exist_ok=True)
    
    # Create clean file name (replace special characters)
    clean_date = audit["created_at"][:16].replace(":", "-").replace("T", "_")
    filename = f"Auditoria_Fulfillment_Tienda_{audit['store_id']}_{clean_date}.txt"
    filepath = os.path.join(archive_dir, filename)
    
    # Generate content
    lines = []
    lines.append("================================================================")
    lines.append("         WALMART - ASSET PROTECTION INVESTIGATIONS")
    lines.append("       TOURING FULFILLMENT OPD - REPORTE DE AUDITORIA")
    lines.append("================================================================")
    lines.append(f"Tienda: #{audit['store_id']}")
    if audit.get("week_number"):
        lines.append(f"Semana Fiscal: {audit['week_number']}")
    lines.append(f"Auditor/Investigador: {audit['auditor_name']}")
    if audit.get("discussed_with"):
        lines.append(f"Discutido con: {audit['discussed_with']}")
    lines.append(f"Fecha/Hora: {audit['formatted_date']}")
    lines.append(f"Score de Cumplimiento: {audit['score']}%")
    
    score_lbl = "Sobresaliente" if audit['score'] >= 90 else ("Necesita Mejora" if audit['score'] >= 80 else "Insatisfactorio / Critico")
    lines.append(f"Evaluacion General: {score_lbl}")
    lines.append("================================================================")
    
    if audit['notes']:
      lines.append("\nCOMENTARIOS GENERALES Y PLAN DE ACCION:")
      lines.append(audit['notes'])
      lines.append("----------------------------------------------------------------")
      
    # Group responses
    grouped = {}
    for r in audit['responses']:
        if r['category'] not in grouped:
            grouped[r['category']] = []
        grouped[r['category']].append(r)
        
    lines.append("\nDETALLES DE PUNTOS EVALUADOS:")
    for category, items in grouped.items():
        lines.append(f"\n>>> CATEGORIA: {category.upper()}")
        for item in items:
            status_lbl = "CUMPLE" if item['status'] == 'yes' else ("NO CUMPLE" if item['status'] == 'no' else "N/A")
            lines.append(f"  [-] {item['question']}")
            lines.append(f"      Estado: {status_lbl}")
            if item['status'] == 'no' and item['comment']:
                lines.append(f"      Hallazgo/Comentario: {item['comment']}")
            elif item['comment']:
                lines.append(f"      Nota: {item['comment']}")
                
    lines.append("\n================================================================")
    lines.append("Este reporte se ha guardado de forma automatica en los archivos del sistema.")
    lines.append("Desarrollado por Hector & Toby")
    lines.append("================================================================")
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
        
    return filepath
    conn.close()
