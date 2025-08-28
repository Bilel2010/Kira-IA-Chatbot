# app/routers/publish_flow.py
from fastapi import APIRouter, Request
from pydantic import BaseModel
from app.flows import engine as flow_engine
from app.services.session_store import get_post_session, save_post_session, clear_post_session

router = APIRouter(prefix="/api/v1/publish/flow", tags=["publish-flow"])

class FlowIn(BaseModel):
    text: str

@router.post("/start")
def start_flow(request: Request):
    # RESET HARD : vide la session 'post'
    clear_post_session(request)
    flow = flow_engine.load_flow()
    sess = get_post_session(request)
    out = flow_engine.start_flow(flow, sess)  # current=entry, vars={}
    save_post_session(request, sess)
    return out

@router.post("/reply")
def reply_flow(payload: FlowIn, request: Request):
    flow = flow_engine.load_flow()
    sess = get_post_session(request)
    out = flow_engine.step(flow, sess, user_input=payload.text)
    save_post_session(request, sess)
    return out

@router.post("/reset")
def reset_flow(request: Request):
    clear_post_session(request)
    return {"ok": True, "message": "flow session cleared"}


