"""OPD Orders PWA - Backend FastAPI
Visualizacion en tiempo real de ordenes pendientes por tienda OPD.
Configura config.py para cambiar entre datos mock y API real de Walmart.
"""

from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from paths import STATIC_DIR, TEMPLATES_DIR

import config
import orders_service
import audit_service
import cctv_service
import availability_service
import pdf_service
import os
from fastapi.responses import FileResponse


# ---------------------------------------------------------------------------
# Helpers de presentacion
# ---------------------------------------------------------------------------

def _wait_minutes(order: dict) -> int:
    return int((datetime.now() - order["created_at"]).total_seconds() / 60)


def _urgency(order: dict) -> str:
    mins = (datetime.now() - order["created_at"]).total_seconds() / 60
    if mins >= 20:
        return "critico"
    if mins >= 10:
        return "urgente"
    return "normal"


def _enrich(order: dict) -> dict:
    return {**order, "wait_mins": _wait_minutes(order), "urgency": _urgency(order)}


# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    orders_service.seed_demo_stores()
    audit_service.init_db()
    cctv_service.init_db()
    availability_service.init_db()
    yield


app = FastAPI(title="OPD Orders PWA", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=os.fspath(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=os.fspath(TEMPLATES_DIR))


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def main_page(request: Request):
    """Muestra la pagina de inicio del portal AP."""
    return templates.TemplateResponse(request, "main_page.html")


@app.get("/orders-dashboard", response_class=HTMLResponse)
async def index(request: Request):
    """Muestra el monitor de ordenes de OPD en vivo."""
    return templates.TemplateResponse(request, "index.html")


@app.get("/validate-store", response_class=JSONResponse)
async def validate_store(store: str = Query(..., min_length=1, max_length=10)):
    """Valida el numero de tienda."""
    store = store.strip()
    valid = store.isdigit() and 1 <= int(store) <= 9999
    return {"valid": valid, "store": store.zfill(4) if valid else None}


@app.get("/orders", response_class=HTMLResponse)
async def orders_partial(
    request: Request,
    store: str = Query(default="0000", min_length=1, max_length=10),
):
    """Retorna el partial HTML con las ordenes de la tienda."""
    store = store.strip().zfill(4)

    raw_orders = await orders_service.get_orders(store)
    enriched   = [_enrich(o) for o in raw_orders]

    active = sorted(
        [o for o in enriched if o["status"] != "Listo"],
        key=lambda o: o["created_at"],
    )
    ready = sorted(
        [o for o in enriched if o["status"] == "Listo"],
        key=lambda o: o["updated_at"],
        reverse=True,
    )
    urgent_count = sum(1 for o in active if o["urgency"] == "critico")
    order_ids    = ",".join(o["id"] for o in enriched)

    return templates.TemplateResponse(request, "partials/orders.html", {
        "active":       active,
        "ready":        ready,
        "urgent_count": urgent_count,
        "total":        len(raw_orders),
        "order_ids":    order_ids,
        "store":        store,
        "mock_mode":    config.USE_MOCK_DATA,
        "updated_at":   datetime.now().strftime("%H:%M:%S"),
    })


# ---------------------------------------------------------------------------
# Audit Routes
# ---------------------------------------------------------------------------

@app.get("/audits", response_class=HTMLResponse)
async def audits_list(request: Request):
    """Muestra la lista de todas las auditorias de Touring."""
    audits = audit_service.get_all_audits()
    return templates.TemplateResponse(request, "audits/list.html", {"audits": audits})


@app.get("/audits/new", response_class=HTMLResponse)
async def audits_new_form(request: Request):
    """Muestra el formulario para realizar un nuevo Touring."""
    schema = audit_service.get_questions_schema()
    return templates.TemplateResponse(request, "audits/form.html", {"schema": schema})


@app.post("/audits/new")
async def audits_save(request: Request):
    """Procesa el guardado de una nueva auditoria."""
    form_data = await request.form()
    store_id = str(form_data.get("store_id", "")).strip()
    auditor_name = str(form_data.get("auditor_name", "")).strip()
    notes = str(form_data.get("notes", "")).strip()
    week_number = str(form_data.get("week_number", "")).strip()
    discussed_with = str(form_data.get("discussed_with", "")).strip()
    
    responses = []
    for key in form_data.keys():
        if key.startswith("status_"):
            try:
                idx = int(key.split("_")[1])
                category = str(form_data.get(f"cat_{idx}"))
                question = str(form_data.get(f"question_{idx}"))
                status = str(form_data.get(f"status_{idx}"))
                comment = str(form_data.get(f"comment_{idx}", "")).strip()
                
                responses.append({
                    "category": category,
                    "question": question,
                    "status": status,
                    "comment": comment
                })
            except (ValueError, TypeError):
                pass
                
    audit_id = audit_service.save_audit(store_id, auditor_name, responses, notes, week_number=week_number, discussed_with=discussed_with)
    # Guardar automaticamente un reporte de texto legible y un PDF oficial en la carpeta audits_archive
    audit_service.export_audit_to_file(audit_id)
    
    # Pre-generar el PDF oficial
    audit = audit_service.get_audit_details(audit_id)
    pdf_service.generate_audit_pdf(audit)
    
    return RedirectResponse(url=f"/audits/{audit_id}", status_code=303)


@app.get("/audits/{audit_id}", response_class=HTMLResponse)
async def audits_detail(request: Request, audit_id: int):
    """Muestra los detalles de una auditoria especifica."""
    audit = audit_service.get_audit_details(audit_id)
    if not audit:
        return RedirectResponse(url="/audits", status_code=303)
    return templates.TemplateResponse(request, "audits/detail.html", {"audit": audit})


@app.get("/audits/{audit_id}/pdf")
async def download_audit_pdf(audit_id: int):
    """Genera y sirve el PDF oficial de la auditoria para descarga directa."""
    audit = audit_service.get_audit_details(audit_id)
    if not audit:
        return RedirectResponse(url="/audits", status_code=303)
        
    pdf_path = pdf_service.generate_audit_pdf(audit)
    filename = os.path.basename(pdf_path)
    return FileResponse(path=pdf_path, filename=filename, media_type="application/pdf")


@app.post("/audits/{audit_id}/delete")
async def audits_delete(audit_id: int):
    """Elimina una auditoria de la base de datos."""
    audit_service.delete_audit(audit_id)
    return RedirectResponse(url="/audits", status_code=303)


# ---------------------------------------------------------------------------
# CCTV Investigation Routes
# ---------------------------------------------------------------------------

@app.get("/cctv", response_class=HTMLResponse)
async def cctv_list(request: Request):
    """Muestra la lista de todas las investigaciones CCTV."""
    investigations = cctv_service.get_all_investigations()
    return templates.TemplateResponse(request, "cctv/list.html", {"investigations": investigations})


@app.get("/cctv/new", response_class=HTMLResponse)
async def cctv_new_form(request: Request, with_photos: bool = Query(False)):
    """Muestra el formulario para registrar una nueva investigacion CCTV."""
    return templates.TemplateResponse(request, "cctv/form.html", {"with_photos": with_photos})


@app.post("/cctv/new")
async def cctv_save(request: Request):
    """Procesa el guardado de una nueva investigacion CCTV."""
    form_data = await request.form()
    with_photos = form_data.get("with_photos") == "true"
    store_id = str(form_data.get("store_id", "")).strip()
    subject_name = str(form_data.get("subject_name", "")).strip()
    video_date = str(form_data.get("video_date", "")).strip()
    investigation_date = str(form_data.get("investigation_date", "")).strip()
    api = str(form_data.get("api", "")).strip()
    apasm = str(form_data.get("apasm", "")).strip()
    notes = str(form_data.get("notes", "")).strip()
    
    indices = form_data.getlist("event_indices")
    events = []
    
    for idx_str in indices:
        try:
            idx = int(idx_str)
            camera = str(form_data.get(f"camera_{idx}", "")).strip()
            time_stamp = str(form_data.get(f"time_stamp_{idx}", "")).strip()
            description = str(form_data.get(f"description_{idx}", "")).strip()
            
            photo_path = None
            if with_photos:
                photo_file = form_data.get(f"photo_{idx}")
                if photo_file and hasattr(photo_file, "filename") and photo_file.filename:
                    # Guardar archivo de foto
                    ext = os.path.splitext(photo_file.filename)[1]
                    unique_filename = f"cctv_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{idx}{ext}"
                    filepath = os.path.join(cctv_service.UPLOAD_DIR, unique_filename)
                    
                    content = await photo_file.read()
                    with open(filepath, "wb") as f:
                        f.write(content)
                        
                    photo_path = f"/static/uploads/cctv_photos/{unique_filename}"
                    
            events.append({
                "camera": camera,
                "time_stamp": time_stamp,
                "description": description,
                "photo_path": photo_path
            })
        except Exception:
            pass
            
    investigation_id = cctv_service.save_investigation(
        store_id=store_id,
        investigation_date=investigation_date,
        video_date=video_date,
        apasm=apasm,
        api=api,
        subject_name=subject_name,
        with_photos=with_photos,
        notes=notes,
        events=events
    )
    
    # Pre-generar el PDF oficial
    inv_details = cctv_service.get_investigation_details(investigation_id)
    cctv_service.generate_cctv_pdf(inv_details)
    
    return RedirectResponse(url=f"/cctv/{investigation_id}", status_code=303)


@app.get("/cctv/{investigation_id}", response_class=HTMLResponse)
async def cctv_detail(request: Request, investigation_id: int):
    """Muestra los detalles de una investigacion CCTV especifica."""
    inv = cctv_service.get_investigation_details(investigation_id)
    if not inv:
        return RedirectResponse(url="/cctv", status_code=303)
    return templates.TemplateResponse(request, "cctv/detail.html", {"inv": inv})


@app.get("/cctv/{investigation_id}/pdf")
async def download_cctv_pdf(investigation_id: int):
    """Genera y sirve el PDF oficial de la investigacion para descarga directa."""
    inv = cctv_service.get_investigation_details(investigation_id)
    if not inv:
        return RedirectResponse(url="/cctv", status_code=303)
        
    pdf_path = cctv_service.generate_cctv_pdf(inv)
    filename = os.path.basename(pdf_path)
    return FileResponse(path=pdf_path, filename=filename, media_type="application/pdf")


@app.post("/cctv/{investigation_id}/delete")
async def cctv_delete(investigation_id: int):
    """Elimina una investigacion CCTV de la base de datos."""
    cctv_service.delete_investigation(investigation_id)
    return RedirectResponse(url="/cctv", status_code=303)


# ---------------------------------------------------------------------------
# Availability Audit Routes
# ---------------------------------------------------------------------------

@app.get("/availability", response_class=HTMLResponse)
async def availability_list(request: Request):
    """Muestra la lista de todas las auditorías de Disponibilidad (Availability)."""
    audits = availability_service.get_all_audits()
    return templates.TemplateResponse(request, "availability/list.html", {"audits": audits})


@app.get("/availability/new", response_class=HTMLResponse)
async def availability_new_form(request: Request):
    """Muestra el formulario para realizar una nueva auditoría de disponibilidad."""
    return templates.TemplateResponse(request, "availability/form.html")


@app.post("/availability/new")
async def availability_save(request: Request):
    """Procesa el guardado de una nueva auditoría de disponibilidad."""
    form_data = await request.form()
    store_id = str(form_data.get("store_id", "")).strip()
    auditor_name = str(form_data.get("auditor_name", "Hector")).strip() or "Hector"
    week_number = str(form_data.get("week_number", "")).strip()
    discussed_with = str(form_data.get("discussed_with", "")).strip()
    notes = str(form_data.get("notes", "")).strip()
    
    import json
    
    process_vagones_status = str(form_data.get("process_vagones", "SI")).strip()
    process_vagones_comments = str(form_data.get("process_vagones_comments", "")).strip()
    process_pinpoint_status = str(form_data.get("process_pinpoint", "SI")).strip()
    process_pinpoint_comments = str(form_data.get("process_pinpoint_comments", "")).strip()
    process_bines_status = str(form_data.get("process_bines", "NO")).strip()
    
    # 1. Parse dynamic list of Bines
    bines_locs = form_data.getlist("process_bines_loc")
    bines_coms = form_data.getlist("process_bines_comments")
    bines_list = []
    for j in range(len(bines_locs)):
        l_val = str(bines_locs[j]).strip()
        c_val = str(bines_coms[j]).strip()
        if l_val or c_val:
            bines_list.append({"loc": l_val, "comments": c_val})
    process_bines_comments = json.dumps(bines_list)
    process_bines_loc = ""
    
    # 2. Parse dynamic list of Topes
    topes_locs = form_data.getlist("process_topes_loc")
    topes_coms = form_data.getlist("process_topes_comments")
    topes_list = []
    for j in range(len(topes_locs)):
        l_val = str(topes_locs[j]).strip()
        c_val = str(topes_coms[j]).strip()
        if l_val or c_val:
            topes_list.append({"loc": l_val, "comments": c_val})
    process_topes_comments = json.dumps(topes_list)
    process_topes_loc = ""
    
    # 3. Parse dynamic list of WACOS
    wacos_locs = form_data.getlist("process_wacos_loc")
    wacos_coms = form_data.getlist("process_wacos_comments")
    wacos_list = []
    for j in range(len(wacos_locs)):
        l_val = str(wacos_locs[j]).strip()
        c_val = str(wacos_coms[j]).strip()
        if l_val or c_val:
            wacos_list.append({"loc": l_val, "comments": c_val})
    process_wacos_comments = json.dumps(wacos_list)
    process_wacos_loc = ""
    
    # Detect all active modular card indices dynamically
    card_indices = []
    for key in form_data.keys():
        if key.startswith("dept_"):
            try:
                idx = int(key.split("_")[1])
                card_indices.append(idx)
            except ValueError:
                pass
    card_indices.sort()
    
    modular_items = []
    for i in card_indices:
        dept = str(form_data.get(f"dept_{i}", "")).strip()
        mod = str(form_data.get(f"mod_{i}", "")).strip()
        seq = str(form_data.get(f"seq_{i}", "SI")).strip()
        date = str(form_data.get(f"date_{i}", "")).strip()
        outs = str(form_data.get(f"outs_{i}", "")).strip()
        pi_found = str(form_data.get(f"pi_found_{i}", "NO")).strip()
        outs_oh_found = str(form_data.get(f"outs_oh_found_{i}", "NO")).strip()
        
        items_found = 0
        items_corrected = 0
        understated_value = 0.0
        
        if pi_found == "SI":
            try:
                items_found = int(form_data.get(f"pi_items_{i}", 0) or 0)
            except ValueError:
                pass
            try:
                items_corrected = int(form_data.get(f"pi_corr_{i}", 0) or 0)
            except ValueError:
                pass
            try:
                understated_value = float(form_data.get(f"pi_val_{i}", 0.0) or 0.0)
            except ValueError:
                pass
                
        comments = str(form_data.get(f"comments_{i}", "")).strip()
        
        # Parse product details (Outs with OH & PI Understated)
        details = []
        
        # 1. Parse "Outs with OH" items
        upcs_oh = form_data.getlist(f"item_upc_oh_{i}")
        qtys_oh = form_data.getlist(f"item_qty_oh_{i}")
        for u_idx in range(len(upcs_oh)):
            u = str(upcs_oh[u_idx]).strip()
            if u:
                try:
                    q = int(qtys_oh[u_idx] or 0)
                except (ValueError, IndexError):
                    q = 0
                details.append({
                    "upc": u,
                    "qty": q,
                    "item_type": "OH"
                })
                
        # 2. Parse "PI Understated" items
        upcs_pi = form_data.getlist(f"item_upc_pi_{i}")
        ohs_pi = form_data.getlist(f"item_oh_pi_{i}")
        phys_pi = form_data.getlist(f"item_physical_pi_{i}")
        prices_pi = form_data.getlist(f"item_price_pi_{i}")
        for u_idx in range(len(upcs_pi)):
            u = str(upcs_pi[u_idx]).strip()
            if u:
                try:
                    oh_q = int(ohs_pi[u_idx] or 0)
                except (ValueError, IndexError):
                    oh_q = 0
                try:
                    phys_q = int(phys_pi[u_idx] or 0)
                except (ValueError, IndexError):
                    phys_q = 0
                try:
                    pr_val = float(prices_pi[u_idx] or 0.0)
                except (ValueError, IndexError):
                    pr_val = 0.0
                details.append({
                    "upc": u,
                    "oh_qty": oh_q,
                    "physical_qty": phys_q,
                    "price": pr_val,
                    "item_type": "PI"
                })
        
        if dept:
            modular_items.append({
                "department": dept,
                "modular_verified": mod,
                "modular_sequence": seq,
                "verification_date": date,
                "outs_verified": outs,
                "understated_pi_found": pi_found,
                "items_found": items_found,
                "items_corrected": items_corrected,
                "understated_value": understated_value,
                "outs_oh_found": outs_oh_found,
                "comments": comments,
                "details": details
            })
            
    audit_id = availability_service.save_audit(
        store_id=store_id,
        auditor_name=auditor_name,
        week_number=week_number,
        discussed_with=discussed_with,
        notes=notes,
        process_vagones_status=process_vagones_status,
        process_vagones_comments=process_vagones_comments,
        process_pinpoint_status=process_pinpoint_status,
        process_pinpoint_comments=process_pinpoint_comments,
        process_bines_status=process_bines_status,
        process_bines_comments=process_bines_comments,
        process_topes_comments=process_topes_comments,
        process_bines_loc=process_bines_loc,
        process_topes_loc=process_topes_loc,
        process_wacos_comments=process_wacos_comments,
        process_wacos_loc=process_wacos_loc,
        modular_items=modular_items
    )
    
    # Export automatically to TXT report in audits_archive
    availability_service.export_audit_to_file(audit_id)
    
    # Pre-generate the official PDF
    audit = availability_service.get_audit_details(audit_id)
    pdf_service.generate_availability_pdf(audit)
    
    return RedirectResponse(url=f"/availability/{audit_id}", status_code=303)


@app.get("/availability/barcode/{upc}")
def availability_barcode(upc: str):
    """Genera un barcode SVG escaneable para el UPC dado."""
    import barcode
    from barcode.writer import SVGWriter
    import io

    # Code128 soporta cualquier longitud de UPC sin padding.
    # module_width >= 0.8mm es el minimo GS1 para impresion escaneable.
    code = barcode.get("code128", upc, writer=SVGWriter())
    buffer = io.BytesIO()
    code.write(buffer, options={
        "module_width": 0.8,
        "module_height": 20.0,
        "font_size": 11,
        "text_distance": 4.0,
        "quiet_zone": 6.5,
        "write_text": True,
    })
    svg_bytes = buffer.getvalue()
    return Response(content=svg_bytes, media_type="image/svg+xml")


@app.get("/availability/{audit_id}/edit", response_class=HTMLResponse)
async def availability_edit_form(request: Request, audit_id: int):
    """Muestra el formulario de edición pre-cargado con los datos de la auditoría."""
    import json
    audit = availability_service.get_audit_details(audit_id)
    if not audit:
        return RedirectResponse(url="/availability", status_code=303)
    # Deserialize JSON fields for bines/topes/wacos to pass back to the form
    for field in ("process_bines_comments", "process_topes_comments", "process_wacos_comments"):
        try:
            audit[field] = json.loads(audit.get(field, "[]") or "[]")
        except Exception:
            audit[field] = []
    return templates.TemplateResponse(request, "availability/form.html", {"audit": audit})


@app.post("/availability/{audit_id}/edit")
async def availability_edit_save(request: Request, audit_id: int):
    """Guarda los cambios de una auditoría existente."""
    import json
    form_data = await request.form()
    store_id       = str(form_data.get("store_id", "")).strip()
    auditor_name   = str(form_data.get("auditor_name", "Hector")).strip() or "Hector"
    week_number    = str(form_data.get("week_number", "")).strip()
    discussed_with = str(form_data.get("discussed_with", "")).strip()
    notes          = str(form_data.get("notes", "")).strip()

    process_vagones_status   = str(form_data.get("process_vagones", "SI")).strip()
    process_vagones_comments = str(form_data.get("process_vagones_comments", "")).strip()
    process_pinpoint_status  = str(form_data.get("process_pinpoint", "SI")).strip()
    process_pinpoint_comments= str(form_data.get("process_pinpoint_comments", "")).strip()
    process_bines_status     = str(form_data.get("process_bines", "NO")).strip()

    bines_list = [{"loc": str(l).strip(), "comments": str(c).strip()}
                  for l, c in zip(form_data.getlist("process_bines_loc"),
                                  form_data.getlist("process_bines_comments"))
                  if str(l).strip() or str(c).strip()]
    topes_list = [{"loc": str(l).strip(), "comments": str(c).strip()}
                  for l, c in zip(form_data.getlist("process_topes_loc"),
                                  form_data.getlist("process_topes_comments"))
                  if str(l).strip() or str(c).strip()]
    wacos_list = [{"loc": str(l).strip(), "comments": str(c).strip()}
                  for l, c in zip(form_data.getlist("process_wacos_loc"),
                                  form_data.getlist("process_wacos_comments"))
                  if str(l).strip() or str(c).strip()]

    card_indices = sorted({
        int(k.split("_")[1]) for k in form_data.keys()
        if k.startswith("dept_") and k.split("_")[1].isdigit()
    })

    modular_items = []
    for i in card_indices:
        pi_found     = str(form_data.get(f"pi_found_{i}", "NO")).strip()
        outs_oh_found= str(form_data.get(f"outs_oh_found_{i}", "NO")).strip()
        try:
            items_found = int(form_data.get(f"pi_items_{i}", 0) or 0)
        except ValueError:
            items_found = 0
        try:
            items_corrected = int(form_data.get(f"pi_corr_{i}", 0) or 0)
        except ValueError:
            items_corrected = 0
        try:
            understated_value = float(form_data.get(f"pi_val_{i}", 0.0) or 0.0)
        except ValueError:
            understated_value = 0.0

        details = []
        for upc, qty in zip(form_data.getlist(f"item_upc_oh_{i}"),
                            form_data.getlist(f"item_qty_oh_{i}")):
            if str(upc).strip():
                details.append({"item_type": "OH", "upc": str(upc).strip(),
                                 "qty": int(qty or 0), "oh_qty": 0,
                                 "physical_qty": 0, "price": 0.0})
        for upc, oh, phys, price in zip(
                form_data.getlist(f"item_upc_pi_{i}"),
                form_data.getlist(f"item_oh_pi_{i}"),
                form_data.getlist(f"item_physical_pi_{i}"),
                form_data.getlist(f"item_price_pi_{i}")):
            if str(upc).strip():
                details.append({"item_type": "PI", "upc": str(upc).strip(),
                                 "qty": 0,
                                 "oh_qty": int(oh or 0),
                                 "physical_qty": int(phys or 0),
                                 "price": float(price or 0.0)})

        modular_items.append({
            "department": str(form_data.get(f"dept_{i}", "")).strip(),
            "modular_verified": str(form_data.get(f"mod_{i}", "")).strip(),
            "modular_sequence": str(form_data.get(f"seq_{i}", "SI")).strip(),
            "verification_date": str(form_data.get(f"date_{i}", "")).strip(),
            "outs_verified": str(form_data.get(f"outs_{i}", "")).strip(),
            "comments": str(form_data.get(f"comments_{i}", "")).strip(),
            "understated_pi_found": pi_found,
            "outs_oh_found": outs_oh_found,
            "items_found": items_found,
            "items_corrected": items_corrected,
            "understated_value": understated_value,
            "details": details,
        })

    availability_service.update_audit(
        audit_id=audit_id,
        store_id=store_id, auditor_name=auditor_name,
        week_number=week_number, discussed_with=discussed_with, notes=notes,
        process_vagones_status=process_vagones_status,
        process_vagones_comments=process_vagones_comments,
        process_pinpoint_status=process_pinpoint_status,
        process_pinpoint_comments=process_pinpoint_comments,
        process_bines_status=process_bines_status,
        process_bines_comments=json.dumps(bines_list),
        process_topes_comments=json.dumps(topes_list),
        process_bines_loc="", process_topes_loc="",
        process_wacos_comments=json.dumps(wacos_list),
        process_wacos_loc="",
        modular_items=modular_items,
    )
    availability_service.export_audit_to_file(audit_id)
    return RedirectResponse(url=f"/availability/{audit_id}", status_code=303)


@app.get("/availability/{audit_id}", response_class=HTMLResponse)
async def availability_detail(request: Request, audit_id: int):
    """Muestra los detalles de una auditoría de disponibilidad específica."""
    audit = availability_service.get_audit_details(audit_id)
    if not audit:
        return RedirectResponse(url="/availability", status_code=303)
        
    # Deserialize bines and topes findings safely
    import json
    try:
        audit["bines_findings"] = json.loads(audit["process_bines_comments"])
    except Exception:
        audit["bines_findings"] = [{"loc": audit.get("process_bines_loc", ""), "comments": audit.get("process_bines_comments", "")}]
        
    try:
        audit["topes_findings"] = json.loads(audit["process_topes_comments"])
    except Exception:
        audit["topes_findings"] = [{"loc": audit.get("process_topes_loc", ""), "comments": audit.get("process_topes_comments", "")}]
        
    try:
        audit["wacos_findings"] = json.loads(audit["process_wacos_comments"])
    except Exception:
        audit["wacos_findings"] = [{"loc": audit.get("process_wacos_loc", ""), "comments": audit.get("process_wacos_comments", "")}]
        
    return templates.TemplateResponse(request, "availability/detail.html", {"audit": audit})


@app.get("/availability/{audit_id}/pdf")
async def download_availability_pdf(audit_id: int):
    """Genera y sirve el PDF oficial de la auditoría de disponibilidad para descarga directa."""
    audit = availability_service.get_audit_details(audit_id)
    if not audit:
        return RedirectResponse(url="/availability", status_code=303)
        
    pdf_path = pdf_service.generate_availability_pdf(audit)
    filename = os.path.basename(pdf_path)
    return FileResponse(path=pdf_path, filename=filename, media_type="application/pdf")


@app.post("/availability/{audit_id}/delete")
async def availability_delete(audit_id: int):
    """Elimina una auditoría de disponibilidad de la base de datos."""
    availability_service.delete_audit(audit_id)
    return RedirectResponse(url="/availability", status_code=303)


@app.get("/debug-db")
async def debug_db():
    import sqlite3
    conn = sqlite3.connect(cctv_service.DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    try:
        cursor.execute("SELECT * FROM cctv_investigations")
        rows = cursor.fetchall()
    except Exception as e:
        rows = str(e)
    return {
        "db_path": cctv_service.DB_PATH,
        "exists": os.path.exists(cctv_service.DB_PATH),
        "tables": tables,
        "rows": rows
    }

