import os
import sqlite3
from datetime import datetime
from typing import List, Dict, Any

DB_PATH = os.path.join(os.path.dirname(__file__), "audits.db")
ARCHIVE_DIR = os.path.join(os.path.dirname(__file__), "audits_archive")

def init_db():
    """Initializes sqlite database with availability audit tables."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Availability audits main table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS availability_audits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        store_id TEXT NOT NULL,
        auditor_name TEXT NOT NULL,
        week_number TEXT NOT NULL,
        created_at TEXT NOT NULL,
        discussed_with TEXT DEFAULT '',
        total_understated_value REAL DEFAULT 0.0,
        notes TEXT,
        process_vagones_status TEXT DEFAULT '',
        process_vagones_comments TEXT DEFAULT '',
        process_pinpoint_status TEXT DEFAULT '',
        process_pinpoint_comments TEXT DEFAULT '',
        process_bines_status TEXT DEFAULT '',
        process_bines_comments TEXT DEFAULT '',
        process_topes_comments TEXT DEFAULT '',
        process_bines_loc TEXT DEFAULT '',
        process_topes_loc TEXT DEFAULT '',
        process_wacos_comments TEXT DEFAULT '',
        process_wacos_loc TEXT DEFAULT ''
    )
    """)
    
    # Add new columns dynamically if they don't exist
    for col, col_type in [
        ("process_topes_comments", "TEXT DEFAULT ''"), 
        ("process_bines_loc", "TEXT DEFAULT ''"), 
        ("process_topes_loc", "TEXT DEFAULT ''"),
        ("process_wacos_comments", "TEXT DEFAULT ''"),
        ("process_wacos_loc", "TEXT DEFAULT ''")
    ]:
        try:
            cursor.execute(f"ALTER TABLE availability_audits ADD COLUMN {col} {col_type}")
        except sqlite3.OperationalError:
            pass
    
    # Modular items checked during the audit
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS availability_modular_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        audit_id INTEGER NOT NULL,
        department TEXT NOT NULL,
        modular_verified TEXT NOT NULL,
        modular_sequence TEXT NOT NULL, -- 'SI' or 'NO'
        verification_date TEXT NOT NULL,
        outs_verified TEXT NOT NULL,
        comments TEXT DEFAULT '',
        understated_pi_found TEXT NOT NULL, -- 'SI' or 'NO'
        items_found INTEGER DEFAULT 0,
        items_corrected INTEGER DEFAULT 0,
        understated_value REAL DEFAULT 0.0,
        outs_oh_found TEXT DEFAULT 'NO',
        FOREIGN KEY (audit_id) REFERENCES availability_audits (id) ON DELETE CASCADE
    )
    """)
    
    try:
        cursor.execute("ALTER TABLE availability_modular_items ADD COLUMN outs_oh_found TEXT DEFAULT 'NO'")
    except sqlite3.OperationalError:
        pass
    
    # Item-level details for "Outs con On Hand (OH)" or "PI Understated Items"
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS availability_item_details (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        modular_item_id INTEGER NOT NULL,
        item_type TEXT NOT NULL, -- 'OH' or 'PI'
        upc TEXT NOT NULL,
        qty INTEGER DEFAULT 0,
        oh_qty INTEGER DEFAULT 0,
        physical_qty INTEGER DEFAULT 0,
        price REAL DEFAULT 0.0,
        FOREIGN KEY (modular_item_id) REFERENCES availability_modular_items (id) ON DELETE CASCADE
    )
    """)
    
    for col, col_type in [("qty", "INTEGER DEFAULT 0"), ("oh_qty", "INTEGER DEFAULT 0"), ("physical_qty", "INTEGER DEFAULT 0"), ("price", "REAL DEFAULT 0.0")]:
        try:
            cursor.execute(f"ALTER TABLE availability_item_details ADD COLUMN {col} {col_type}")
        except sqlite3.OperationalError:
            pass
            
    conn.commit()
    conn.close()

def save_audit(
    store_id: str,
    auditor_name: str,
    week_number: str,
    discussed_with: str,
    notes: str,
    process_vagones_status: str,
    process_vagones_comments: str,
    process_pinpoint_status: str,
    process_pinpoint_comments: str,
    process_bines_status: str,
    process_bines_comments: str,
    process_topes_comments: str,
    process_bines_loc: str,
    process_topes_loc: str,
    process_wacos_comments: str, # Added field requested by Hector
    process_wacos_loc: str, # Added field requested by Hector
    modular_items: List[Dict[str, Any]]
) -> int:
    """Saves a complete Availability Audit, calculates total understated value and returns audit_id."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    created_at = datetime.now().isoformat()
    
    total_value = 0.0
    for item in modular_items:
        item_total_pi = 0.0
        for detail in item.get("details", []):
            if detail.get("item_type") == "PI":
                oh = float(detail.get("oh_qty", 0) or 0)
                phys = float(detail.get("physical_qty", 0) or 0)
                pr = float(detail.get("price", 0.0) or 0.0)
                diff = max(0.0, phys - oh)
                item_total_pi += diff * pr
                
        if item_total_pi > 0.0:
            item["understated_value"] = item_total_pi
        
        try:
            val = float(item.get("understated_value", 0.0) or 0.0)
            total_value += val
        except (ValueError, TypeError):
            pass
            
    cursor.execute("""
    INSERT INTO availability_audits (
        store_id, auditor_name, week_number, created_at, discussed_with, 
        total_understated_value, notes, 
        process_vagones_status, process_vagones_comments,
        process_pinpoint_status, process_pinpoint_comments,
        process_bines_status, process_bines_comments, process_topes_comments,
        process_bines_loc, process_topes_loc, process_wacos_comments, process_wacos_loc
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        store_id, auditor_name, week_number, created_at, discussed_with,
        total_value, notes,
        process_vagones_status, process_vagones_comments,
        process_pinpoint_status, process_pinpoint_comments,
        process_bines_status, process_bines_comments, process_topes_comments,
        process_bines_loc, process_topes_loc, process_wacos_comments, process_wacos_loc
    ))
    
    audit_id = cursor.lastrowid
    
    for item in modular_items:
        pi_items_count = 0
        pi_corrected_count = 0
        for d in item.get("details", []):
            if d.get("item_type") == "PI":
                pi_items_count += int(d.get("physical_qty", 0) or 0)
                pi_corrected_count += int(d.get("physical_qty", 0) or 0)
                
        if pi_items_count > 0:
            item["items_found"] = pi_items_count
            item["items_corrected"] = pi_corrected_count

        try:
            val = float(item.get("understated_value", 0.0) or 0.0)
        except (ValueError, TypeError):
            val = 0.0
            
        try:
            found = int(item.get("items_found", 0) or 0)
        except (ValueError, TypeError):
            found = 0
            
        try:
            corrected = int(item.get("items_corrected", 0) or 0)
        except (ValueError, TypeError):
            corrected = 0
            
        cursor.execute("""
        INSERT INTO availability_modular_items (
            audit_id, department, modular_verified, modular_sequence, 
            verification_date, outs_verified, comments, 
            understated_pi_found, items_found, items_corrected, understated_value,
            outs_oh_found
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            audit_id,
            str(item.get("department", "")).strip(),
            str(item.get("modular_verified", "")).strip(),
            str(item.get("modular_sequence", "SI")).strip(),
            str(item.get("verification_date", "")).strip(),
            str(item.get("outs_verified", "")).strip(),
            str(item.get("comments", "")).strip(),
            str(item.get("understated_pi_found", "NO")).strip(),
            found,
            corrected,
            val,
            str(item.get("outs_oh_found", "NO")).strip()
        ))
        
        modular_item_id = cursor.lastrowid
        
        for detail in item.get("details", []):
            try:
                qty_val = int(detail.get("qty", 0) or 0)
            except (ValueError, TypeError):
                qty_val = 0
                
            try:
                oh_qty_val = int(detail.get("oh_qty", 0) or 0)
            except (ValueError, TypeError):
                oh_qty_val = 0
                
            try:
                physical_qty_val = int(detail.get("physical_qty", 0) or 0)
            except (ValueError, TypeError):
                physical_qty_val = 0
                
            try:
                price_val = float(detail.get("price", 0.0) or 0.0)
            except (ValueError, TypeError):
                price_val = 0.0
                
            cursor.execute("""
            INSERT INTO availability_item_details (modular_item_id, item_type, upc, qty, oh_qty, physical_qty, price)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                modular_item_id,
                str(detail.get("item_type", "OH")).strip(),
                str(detail.get("upc", "")).strip(),
                qty_val,
                oh_qty_val,
                physical_qty_val,
                price_val
            ))
        
    conn.commit()
    conn.close()
    return audit_id

def get_all_audits() -> List[Dict[str, Any]]:
    """Retrieves all saved availability audits."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
    SELECT id, store_id, auditor_name, week_number, created_at, discussed_with, total_understated_value 
    FROM availability_audits 
    ORDER BY created_at DESC
    """)
    rows = cursor.fetchall()
    
    audits = []
    for r in rows:
        dt = datetime.fromisoformat(r["created_at"])
        formatted_date = dt.strftime("%b %d, %Y - %I:%M %p")
        audits.append({
            "id": r["id"],
            "store_id": r["store_id"],
            "auditor_name": r["auditor_name"],
            "week_number": r["week_number"],
            "created_at": r["created_at"],
            "formatted_date": formatted_date,
            "discussed_with": r["discussed_with"],
            "total_understated_value": round(r["total_understated_value"], 2)
        })
        
    conn.close()
    return audits

def get_audit_details(audit_id: int) -> Dict[str, Any]:
    """Retrieves detailed information for a single availability audit."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM availability_audits WHERE id = ?", (audit_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None
        
    dt = datetime.fromisoformat(row["created_at"])
    formatted_date = dt.strftime("%b %d, %Y - %I:%M %p")
    
    # Safely extract dynamic columns for backward compatibility
    row_keys = row.keys()
    topes_comments = row["process_topes_comments"] if "process_topes_comments" in row_keys else ""
    bines_loc = row["process_bines_loc"] if "process_bines_loc" in row_keys else ""
    topes_loc = row["process_topes_loc"] if "process_topes_loc" in row_keys else ""
    wacos_comments = row["process_wacos_comments"] if "process_wacos_comments" in row_keys else ""
    wacos_loc = row["process_wacos_loc"] if "process_wacos_loc" in row_keys else ""
    
    audit_data = {
        "id": row["id"],
        "store_id": row["store_id"],
        "auditor_name": row["auditor_name"],
        "week_number": row["week_number"],
        "created_at": row["created_at"],
        "formatted_date": formatted_date,
        "discussed_with": row["discussed_with"],
        "total_understated_value": round(row["total_understated_value"], 2),
        "notes": row["notes"],
        "process_vagones_status": row["process_vagones_status"],
        "process_vagones_comments": row["process_vagones_comments"],
        "process_pinpoint_status": row["process_pinpoint_status"],
        "process_pinpoint_comments": row["process_pinpoint_comments"],
        "process_bines_status": row["process_bines_status"],
        "process_bines_comments": row["process_bines_comments"],
        "process_topes_comments": topes_comments,
        "process_bines_loc": bines_loc,
        "process_topes_loc": topes_loc,
        "process_wacos_comments": wacos_comments,
        "process_wacos_loc": wacos_loc,
        "modular_items": []
    }
    
    cursor.execute("SELECT * FROM availability_modular_items WHERE audit_id = ?", (audit_id,))
    item_rows = cursor.fetchall()
    for item in item_rows:
        cursor.execute("SELECT * FROM availability_item_details WHERE modular_item_id = ?", (item["id"],))
        detail_rows = cursor.fetchall()
        details_list = []
        for d in detail_rows:
            details_list.append({
                "id": d["id"],
                "item_type": d["item_type"],
                "upc": d["upc"],
                "qty": d["qty"],
                "oh_qty": d["oh_qty"] if "oh_qty" in d.keys() else 0,
                "physical_qty": d["physical_qty"] if "physical_qty" in d.keys() else 0,
                "price": d["price"] if "price" in d.keys() else 0.0
            })
            
        audit_data["modular_items"].append({
            "id": item["id"],
            "department": item["department"],
            "modular_verified": item["modular_verified"],
            "modular_sequence": item["modular_sequence"],
            "verification_date": item["verification_date"],
            "outs_verified": item["outs_verified"],
            "comments": item["comments"],
            "understated_pi_found": item["understated_pi_found"],
            "items_found": item["items_found"],
            "items_corrected": item["items_corrected"],
            "understated_value": round(item["understated_value"], 2),
            "outs_oh_found": item["outs_oh_found"] if "outs_oh_found" in item.keys() else "NO",
            "details": details_list
        })
        
    conn.close()
    return audit_data

def update_audit(
    audit_id: int,
    store_id: str,
    auditor_name: str,
    week_number: str,
    discussed_with: str,
    notes: str,
    process_vagones_status: str,
    process_vagones_comments: str,
    process_pinpoint_status: str,
    process_pinpoint_comments: str,
    process_bines_status: str,
    process_bines_comments: str,
    process_topes_comments: str,
    process_bines_loc: str,
    process_topes_loc: str,
    process_wacos_comments: str,
    process_wacos_loc: str,
    modular_items: List[Dict[str, Any]]
) -> None:
    """Updates header + replaces all modular items of an existing availability audit."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    total_value = 0.0
    for item in modular_items:
        item_total_pi = 0.0
        for detail in item.get("details", []):
            if detail.get("item_type") == "PI":
                oh   = float(detail.get("oh_qty", 0) or 0)
                phys = float(detail.get("physical_qty", 0) or 0)
                pr   = float(detail.get("price", 0.0) or 0.0)
                item_total_pi += max(0.0, phys - oh) * pr
        if item_total_pi > 0.0:
            item["understated_value"] = item_total_pi
        try:
            total_value += float(item.get("understated_value", 0.0) or 0.0)
        except (ValueError, TypeError):
            pass

    cursor.execute("""
    UPDATE availability_audits SET
        store_id=?, auditor_name=?, week_number=?, discussed_with=?,
        total_understated_value=?, notes=?,
        process_vagones_status=?, process_vagones_comments=?,
        process_pinpoint_status=?, process_pinpoint_comments=?,
        process_bines_status=?, process_bines_comments=?, process_topes_comments=?,
        process_bines_loc=?, process_topes_loc=?,
        process_wacos_comments=?, process_wacos_loc=?
    WHERE id=?
    """, (
        store_id, auditor_name, week_number, discussed_with,
        total_value, notes,
        process_vagones_status, process_vagones_comments,
        process_pinpoint_status, process_pinpoint_comments,
        process_bines_status, process_bines_comments, process_topes_comments,
        process_bines_loc, process_topes_loc,
        process_wacos_comments, process_wacos_loc,
        audit_id
    ))

    # Wipe old modular items & their details, then reinsert fresh
    cursor.execute("SELECT id FROM availability_modular_items WHERE audit_id=?", (audit_id,))
    old_ids = [r[0] for r in cursor.fetchall()]
    for oid in old_ids:
        cursor.execute("DELETE FROM availability_item_details WHERE modular_item_id=?", (oid,))
    cursor.execute("DELETE FROM availability_modular_items WHERE audit_id=?", (audit_id,))

    for item in modular_items:
        try:
            val = float(item.get("understated_value", 0.0) or 0.0)
        except (ValueError, TypeError):
            val = 0.0
        try:
            found = int(item.get("items_found", 0) or 0)
        except (ValueError, TypeError):
            found = 0
        try:
            corrected = int(item.get("items_corrected", 0) or 0)
        except (ValueError, TypeError):
            corrected = 0

        cursor.execute("""
        INSERT INTO availability_modular_items (
            audit_id, department, modular_verified, modular_sequence,
            verification_date, outs_verified, comments,
            understated_pi_found, items_found, items_corrected, understated_value, outs_oh_found
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            audit_id,
            str(item.get("department", "")).strip(),
            str(item.get("modular_verified", "")).strip(),
            str(item.get("modular_sequence", "SI")).strip(),
            str(item.get("verification_date", "")).strip(),
            str(item.get("outs_verified", "")).strip(),
            str(item.get("comments", "")).strip(),
            str(item.get("understated_pi_found", "NO")).strip(),
            found, corrected, val,
            str(item.get("outs_oh_found", "NO")).strip()
        ))

        modular_item_id = cursor.lastrowid
        for detail in item.get("details", []):
            try:
                qty_val = int(detail.get("qty", 0) or 0)
            except (ValueError, TypeError):
                qty_val = 0
            try:
                oh_qty_val = int(detail.get("oh_qty", 0) or 0)
            except (ValueError, TypeError):
                oh_qty_val = 0
            try:
                physical_qty_val = int(detail.get("physical_qty", 0) or 0)
            except (ValueError, TypeError):
                physical_qty_val = 0
            try:
                price_val = float(detail.get("price", 0.0) or 0.0)
            except (ValueError, TypeError):
                price_val = 0.0

            cursor.execute("""
            INSERT INTO availability_item_details
                (modular_item_id, item_type, upc, qty, oh_qty, physical_qty, price)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                modular_item_id,
                str(detail.get("item_type", "OH")).strip(),
                str(detail.get("upc", "")).strip(),
                qty_val, oh_qty_val, physical_qty_val, price_val
            ))

    conn.commit()
    conn.close()


def delete_audit(audit_id: int):
    """Deletes an availability audit and cascade deletes its items."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM availability_audits WHERE id = ?", (audit_id,))
    cursor.execute("DELETE FROM availability_modular_items WHERE audit_id = ?", (audit_id,))
    conn.commit()
    conn.close()

def export_audit_to_file(audit_id: int) -> str:
    """Exports audit details to a readable text report file on disk."""
    audit = get_audit_details(audit_id)
    if not audit:
        return ""
        
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    clean_date = audit["created_at"][:16].replace(":", "-").replace("T", "_")
    filename = f"Auditoria_Availability_Tienda_{audit['store_id']}_{clean_date}.txt"
    filepath = os.path.join(ARCHIVE_DIR, filename)
    
    lines = []
    lines.append("================================================================")
    lines.append("         WALMART - ASSET PROTECTION INVESTIGATIONS")
    lines.append("            AVAILABILITY AUDIT - MARKET 801")
    lines.append("================================================================")
    lines.append(f"Tienda: #{audit['store_id']}")
    lines.append(f"Semana Fiscal: {audit['week_number']}")
    lines.append(f"Auditor/Investigador: {audit['auditor_name']}")
    if audit.get("discussed_with"):
        lines.append(f"Discutido con: {audit['discussed_with']}")
    lines.append(f"Fecha/Hora: {audit['formatted_date']}")
    lines.append(f"Total PI Understated: ${audit['total_understated_value']:.2f}")
    lines.append("================================================================")
    
    if audit['notes']:
        lines.append("\nCOMENTARIOS GENERALES:")
        lines.append(audit['notes'])
        lines.append("----------------------------------------------------------------")
        
    lines.append("\nMODULARES VERIFICADOS:")
    for item in audit['modular_items']:
        lines.append(f"\n[-] Departamento: {item['department']} | Modular: {item['modular_verified']}")
        lines.append(f"    Secuencia Modular: {item['modular_sequence']} | Fecha: {item['verification_date']}")
        lines.append(f"    Outs Verificados: {item['outs_verified']}")
        lines.append(f"    ¿Outs con On Hand?: {item.get('outs_oh_found', 'NO')}")
        lines.append(f"    PI Understated Detectado: {item['understated_pi_found']}")
        if item['understated_pi_found'] == 'SI':
            lines.append(f"    Items Encontrados: {item['items_found']} | Corregidos: {item['items_corrected']} | Valor: ${item['understated_value']:.2f}")
            
        # Write sub-items (UPC / QTY / PI stats)
        if item.get("details"):
            lines.append("    PRODUCTOS IDENTIFICADOS:")
            for d in item["details"]:
                if d["item_type"] == "OH":
                    lines.append(f"      * [OUT CON OH] UPC: {d['upc']} | Qty: {d['qty']}")
                else:
                    diff = max(0, d['physical_qty'] - d['oh_qty'])
                    val_calc = diff * d['price']
                    lines.append(f"      * [PI UNDERSTATED] UPC: {d['upc']} | OH: {d['oh_qty']} | Fisico: {d['physical_qty']} | Precio: ${d['price']:.2f} | Dif: {diff} | Valor: ${val_calc:.2f}")
                
        if item['comments']:
            lines.append(f"    Comentarios: {item['comments']}")
            
    lines.append("\n================================================================")
    lines.append("VALIDACION DE PROCESOS (TRASTIENDA):")
    lines.append("================================================================")
    
    lines.append(f"1. ¿Todos los vagones fueron finalizados? (Semanal)")
    lines.append(f"   Estado: {audit['process_vagones_status']}")
    if audit['process_vagones_comments']:
        lines.append(f"   Comentarios: {audit['process_vagones_comments']}")
        
    lines.append(f"2. ¿Se están realizando los pinpoint diariamente? (10 Semanal)")
    lines.append(f"   Estado: {audit['process_pinpoint_status']}")
    if audit['process_pinpoint_comments']:
        lines.append(f"   Comentarios: {audit['process_pinpoint_comments']}")
        
    lines.append(f"3. ¿Bines cumplen con estándares establecidos? (15 Semanal)")
    lines.append(f"   Estado: {audit['process_bines_status']}")
    if audit['process_bines_comments'] or audit.get('process_bines_loc'):
        lines.append(f"   Bines -> Loc: {audit.get('process_bines_loc', '')} | Hallazgo: {audit['process_bines_comments']}")
    if audit.get('process_topes_comments') or audit.get('process_topes_loc'):
        lines.append(f"   Topes -> Loc: {audit.get('process_topes_loc', '')} | Hallazgo: {audit.get('process_topes_comments', '')}")
    if audit.get('process_wacos_comments') or audit.get('process_wacos_loc'):
        lines.append(f"   WACOS -> Loc: {audit.get('process_wacos_loc', '')} | Hallazgo: {audit.get('process_wacos_comments', '')}")
        
    lines.append("\n================================================================")
    lines.append("Este reporte se ha guardado de forma automática en los archivos del sistema.")
    lines.append("Desarrollado por Hector & Toby")
    lines.append("================================================================")
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
        
    return filepath
