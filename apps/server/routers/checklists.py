from __future__ import annotations

import os
import shutil
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import (
    ChecklistConclusion,
    ChecklistEvidence,
    ChecklistRun,
    ChecklistRunItem,
    ChecklistStage,
    ChecklistTemplate,
    ChecklistTemplateChange,
    ChecklistTemplateItem,
    TicketItem,
    WorkflowLog,
    WorkflowState,
)

router = APIRouter(prefix="/api/checklists", tags=["checklists"])
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


class TemplateIn(BaseModel):
    name: str
    stage: ChecklistStage
    description: Optional[str] = None
    is_active: bool = True


class TemplateItemIn(BaseModel):
    label: str
    required: bool = False
    sort_order: int = 0
    input_type: str = "boolean"


class MappingIn(BaseModel):
    stage: str
    template_id: Optional[int] = None
    actor: str
    reason: str


class RunIn(BaseModel):
    ticket_item_id: int
    stage: ChecklistStage


class RunItemsIn(BaseModel):
    items: list[dict]


class FinalizeIn(BaseModel):
    inspector: Optional[str] = None
    note: Optional[str] = None
    conclusion: str


class RunEvidenceCaptionIn(BaseModel):
    caption: Optional[str] = None


@router.get("/templates")
def list_templates(db: Session = Depends(get_db)):
    rows = db.query(ChecklistTemplate).all()
    return [{"id": t.id, "name": t.name, "stage": t.stage, "description": t.description, "is_active": t.is_active} for t in rows]


@router.post("/templates")
def create_template(payload: TemplateIn, db: Session = Depends(get_db)):
    t = ChecklistTemplate(name=payload.name, stage=payload.stage, description=payload.description, is_active=payload.is_active)
    db.add(t)
    db.commit()
    db.refresh(t)
    return {"id": t.id}


@router.get("/templates/{template_id}")
def get_template(template_id: int, db: Session = Depends(get_db)):
    t = db.get(ChecklistTemplate, template_id)
    if not t:
        raise HTTPException(404, "Template not found")
    items = db.query(ChecklistTemplateItem).filter(ChecklistTemplateItem.template_id == template_id).order_by(ChecklistTemplateItem.sort_order, ChecklistTemplateItem.id).all()
    return {"id": t.id, "name": t.name, "stage": t.stage, "description": t.description, "is_active": t.is_active, "items": [{"id": i.id, "label": i.label, "required": i.required, "sort_order": i.sort_order, "input_type": i.input_type} for i in items]}


@router.put("/templates/{template_id}")
def update_template(template_id: int, payload: TemplateIn, db: Session = Depends(get_db)):
    t = db.get(ChecklistTemplate, template_id)
    if not t:
        raise HTTPException(404, "Template not found")
    t.name = payload.name
    t.stage = payload.stage
    t.description = payload.description
    t.is_active = payload.is_active
    db.commit()
    return {"ok": True}


@router.post("/templates/{template_id}/items")
def add_template_item(template_id: int, payload: TemplateItemIn, db: Session = Depends(get_db)):
    if not db.get(ChecklistTemplate, template_id):
        raise HTTPException(404, "Template not found")
    it = ChecklistTemplateItem(template_id=template_id, label=payload.label, required=payload.required, sort_order=payload.sort_order, input_type=payload.input_type)
    db.add(it)
    db.commit()
    db.refresh(it)
    return {"id": it.id}


@router.delete("/templates/{template_id}/items/{item_id}")
def delete_template_item(template_id: int, item_id: int, db: Session = Depends(get_db)):
    it = db.query(ChecklistTemplateItem).filter(ChecklistTemplateItem.id == item_id, ChecklistTemplateItem.template_id == template_id).first()
    if not it:
        raise HTTPException(404, "Template item not found")
    db.delete(it)
    db.commit()
    return {"ok": True}


@router.get("/mapping/{ticket_item_id}")
def get_mapping(ticket_item_id: int, db: Session = Depends(get_db)):
    item = db.get(TicketItem, ticket_item_id)
    if not item:
        raise HTTPException(404, "Ticket item not found")
    changes = db.query(ChecklistTemplateChange).filter(ChecklistTemplateChange.ticket_item_id == ticket_item_id).order_by(ChecklistTemplateChange.changed_at.desc()).all()
    return {
        "ticket_item_id": item.id,
        "a2_template_id": item.a2_template_id,
        "c1_template_id": item.c1_template_id,
        "a2_template_locked": item.a2_template_locked,
        "c1_template_locked": item.c1_template_locked,
        "history": [{"id": c.id, "stage": c.stage, "from_template_id": c.from_template_id, "to_template_id": c.to_template_id, "changed_by": c.changed_by, "reason": c.reason, "changed_at": c.changed_at.isoformat()} for c in changes],
    }


@router.post("/mapping/{ticket_item_id}")
def set_mapping(ticket_item_id: int, payload: MappingIn, db: Session = Depends(get_db)):
    item = db.get(TicketItem, ticket_item_id)
    if not item:
        raise HTTPException(404, "Ticket item not found")
    if not payload.actor.strip() or not payload.reason.strip():
        raise HTTPException(400, "actor và reason là bắt buộc")
    is_a2 = payload.stage == "A2"
    locked = item.a2_template_locked if is_a2 else item.c1_template_locked
    if locked:
        raise HTTPException(400, "Template mapping đã lock")
    old = item.a2_template_id if is_a2 else item.c1_template_id
    if payload.template_id and not db.get(ChecklistTemplate, payload.template_id):
        raise HTTPException(404, "Template not found")
    if is_a2:
        item.a2_template_id = payload.template_id
    else:
        item.c1_template_id = payload.template_id
    db.add(ChecklistTemplateChange(ticket_item_id=ticket_item_id, stage=payload.stage, from_template_id=old, to_template_id=payload.template_id, changed_by=payload.actor, reason=payload.reason))
    db.commit()
    return {"ok": True}


@router.post("/runs")
def create_run(payload: RunIn, db: Session = Depends(get_db)):
    item = db.get(TicketItem, payload.ticket_item_id)
    if not item:
        raise HTTPException(404, "Ticket item not found")
    if payload.stage == ChecklistStage.A2_PRECHECK:
        if item.workflow_state != WorkflowState.A2:
            raise HTTPException(400, "Chỉ tạo run A2 khi item ở state A2")
        template_id = item.a2_template_id
    else:
        if item.workflow_state != WorkflowState.C1:
            raise HTTPException(400, "Chỉ tạo run C1 khi item ở state C1")
        template_id = item.c1_template_id
    if not template_id:
        raise HTTPException(400, "Chưa mapping template cho stage này")

    active = db.query(ChecklistRun).filter(
        ChecklistRun.ticket_item_id == item.id,
        ChecklistRun.stage == payload.stage,
        ChecklistRun.finalized_at == None,
    ).first()
    if active:
        return {"id": active.id, "reused": True}

    run = ChecklistRun(ticket_item_id=item.id, template_id=template_id, stage=payload.stage, conclusion=ChecklistConclusion.draft)
    db.add(run)
    db.flush()
    tpl_items = db.query(ChecklistTemplateItem).filter(ChecklistTemplateItem.template_id == template_id).all()
    if not tpl_items:
        raise HTTPException(400, "Template chưa có item checklist. Vui lòng thêm item trước khi tạo run")
    for ti in tpl_items:
        db.add(ChecklistRunItem(run_id=run.id, template_item_id=ti.id, checked=False))
    db.commit()
    return {"id": run.id}


@router.get("/runs/{run_id}")
def get_run(run_id: int, db: Session = Depends(get_db)):
    run = db.get(ChecklistRun, run_id)
    if not run:
        raise HTTPException(404, "Run not found")

    # Backfill cho run cũ từng được tạo khi template chưa có items
    existing_count = db.query(ChecklistRunItem).filter(ChecklistRunItem.run_id == run_id).count()
    if existing_count == 0:
        tpl_items = db.query(ChecklistTemplateItem).filter(
            ChecklistTemplateItem.template_id == run.template_id
        ).all()
        for ti in tpl_items:
            db.add(ChecklistRunItem(run_id=run.id, template_item_id=ti.id, checked=False))
        if tpl_items:
            db.commit()

    rows = db.query(ChecklistRunItem, ChecklistTemplateItem).join(
        ChecklistTemplateItem, ChecklistTemplateItem.id == ChecklistRunItem.template_item_id
    ).filter(ChecklistRunItem.run_id == run_id).order_by(ChecklistTemplateItem.sort_order, ChecklistTemplateItem.id).all()
    evidence = db.query(ChecklistEvidence).filter(ChecklistEvidence.run_id == run_id).order_by(ChecklistEvidence.created_at.desc()).all()
    return {
        "id": run.id,
        "ticket_item_id": run.ticket_item_id,
        "template_id": run.template_id,
        "stage": run.stage,
        "inspector": run.inspector,
        "note": run.note,
        "conclusion": run.conclusion,
        "finalized_at": run.finalized_at.isoformat() if run.finalized_at else None,
        "items": [{"run_item_id": r.id, "template_item_id": t.id, "label": t.label, "required": t.required, "input_type": t.input_type, "checked": r.checked, "value_text": r.value_text, "note": r.note} for r, t in rows],
        "evidence": [{"id": e.id, "file_url": e.file_url, "caption": e.caption, "created_at": e.created_at.isoformat()} for e in evidence],
    }


@router.get("/runs")
def list_runs(ticket_item_id: int, db: Session = Depends(get_db)):
    runs = db.query(ChecklistRun).filter(ChecklistRun.ticket_item_id == ticket_item_id).order_by(ChecklistRun.created_at.desc()).all()
    return [{"id": r.id, "stage": r.stage, "conclusion": r.conclusion, "created_at": r.created_at.isoformat(), "finalized_at": r.finalized_at.isoformat() if r.finalized_at else None} for r in runs]


@router.patch("/runs/{run_id}/items")
def patch_run_items(run_id: int, payload: RunItemsIn, db: Session = Depends(get_db)):
    run = db.get(ChecklistRun, run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    if run.finalized_at:
        raise HTTPException(400, "Run đã finalize")
    for x in payload.items:
        rid = x.get("run_item_id")
        ri = db.query(ChecklistRunItem).filter(ChecklistRunItem.id == rid, ChecklistRunItem.run_id == run_id).first()
        if not ri:
            continue
        if "checked" in x:
            ri.checked = bool(x["checked"])
        if "value_text" in x:
            ri.value_text = x["value_text"]
        if "note" in x:
            ri.note = x["note"]
    db.commit()
    return {"ok": True}


@router.post("/runs/{run_id}/evidence")
async def add_evidence(run_id: int, file: UploadFile = File(...), caption: Optional[str] = None, db: Session = Depends(get_db)):
    run = db.get(ChecklistRun, run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    ext = file.filename.rsplit(".", 1)[-1] if file.filename and "." in file.filename else "jpg"
    filename = f"check_{run_id}_{int(datetime.utcnow().timestamp())}.{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)
    with open(filepath, "wb") as f:
        shutil.copyfileobj(file.file, f)
    ev = ChecklistEvidence(run_id=run_id, file_url=f"/uploads/{filename}", caption=caption)
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return {"id": ev.id, "file_url": ev.file_url}


@router.delete("/runs/{run_id}/evidence/{ev_id}")
def delete_evidence(run_id: int, ev_id: int, db: Session = Depends(get_db)):
    ev = db.query(ChecklistEvidence).filter(ChecklistEvidence.id == ev_id, ChecklistEvidence.run_id == run_id).first()
    if not ev:
        raise HTTPException(404, "Evidence not found")
    db.delete(ev)
    db.commit()
    return {"ok": True}


@router.post("/runs/{run_id}/finalize")
def finalize_run(run_id: int, payload: FinalizeIn, db: Session = Depends(get_db)):
    run = db.get(ChecklistRun, run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    if run.finalized_at:
        raise HTTPException(400, "Run đã finalize")
    item = db.get(TicketItem, run.ticket_item_id)
    conclusion = payload.conclusion.lower()
    if run.stage == ChecklistStage.A2_PRECHECK:
        if conclusion != "completed":
            raise HTTPException(400, "A2 chỉ chấp nhận conclusion=completed")
        run.conclusion = ChecklistConclusion.completed
        item.a2_template_locked = True
    else:
        evidence_count = db.query(ChecklistEvidence).filter(ChecklistEvidence.run_id == run.id).count()
        if evidence_count < 1:
            raise HTTPException(400, "C1 cần ít nhất 1 ảnh evidence")
        if conclusion not in ("pass", "fail"):
            raise HTTPException(400, "C1 chỉ chấp nhận pass|fail")
        run.conclusion = ChecklistConclusion.pass_ if conclusion == "pass" else ChecklistConclusion.fail
        item.c1_template_locked = True
        old = item.workflow_state
        item.workflow_state = WorkflowState.C2 if conclusion == "pass" else WorkflowState.C3
        db.add(WorkflowLog(ticket_item_id=item.id, from_state=old, to_state=item.workflow_state, note="Checklist C1 finalized", actor=payload.inspector))
    run.inspector = payload.inspector
    run.note = payload.note
    run.finalized_at = datetime.utcnow()
    db.commit()
    return {"ok": True, "conclusion": run.conclusion}
