"""音色库与读音词典端点。"""
from __future__ import annotations

import shutil
import uuid

from fastapi import APIRouter, HTTPException, UploadFile
from pydantic import BaseModel
from sqlmodel import select

from .. import config
from ..db import session
from ..models import PronunciationEntry, VoiceRef

router = APIRouter(prefix="/api", tags=["voices"])


@router.get("/voice-refs")
def list_refs():
    with session() as s:
        return [v.model_dump() for v in s.exec(select(VoiceRef)).all()]


@router.post("/voice-refs")
async def upload_ref(file: UploadFile, name: str = "", kind: str = "narrator",
                     emotion_tag: str = ""):
    config.ensure_dirs()
    ext = (file.filename or "ref.wav").rsplit(".", 1)[-1]
    path = config.REFS_DIR / f"{uuid.uuid4().hex[:8]}.{ext}"
    with path.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    ref = VoiceRef(name=name or (file.filename or "ref"), kind=kind,
                   emotion_tag=emotion_tag, file_path=str(path))
    with session() as s:
        s.add(ref); s.commit(); s.refresh(ref)
        return {"id": ref.id}


@router.post("/voice-refs/{vid}/activate")
def activate_ref(vid: int):
    with session() as s:
        ref = s.get(VoiceRef, vid)
        if not ref:
            raise HTTPException(404, "音色不存在")
        for r in s.exec(select(VoiceRef).where(VoiceRef.kind == ref.kind)).all():
            r.is_active = r.id == vid
        s.commit()
        return {"ok": True}


@router.get("/pronunciation-dict")
def list_dict():
    with session() as s:
        return [e.model_dump() for e in s.exec(select(PronunciationEntry)).all()]


class DictIn(BaseModel):
    word: str
    pinyin: str


@router.post("/pronunciation-dict")
def upsert_dict(e: DictIn):
    with session() as s:
        row = s.get(PronunciationEntry, e.word)
        if row:
            row.pinyin = e.pinyin
        else:
            s.add(PronunciationEntry(word=e.word, pinyin=e.pinyin))
        s.commit()
        return {"ok": True}
