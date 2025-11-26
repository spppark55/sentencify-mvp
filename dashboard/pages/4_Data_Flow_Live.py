import pymongo
import os
from enum import StrEnum
from textwrap import dedent
import streamlit as st
import time
import json
import random

# Import correct collection names from queries.mongo
from queries.mongo import COLL_A, COLL_B, COLL_C

st.set_page_config(page_title="Live Data Flow", page_icon="🌊", layout="wide")

# --- Event Emitter & State Management (Provided Pattern) ---

class EventEmitter:
    def __init__(self):
        self._events = {}

    def on(self, event_name, listener):
        if event_name not in self._events:
            self._events[event_name] = []
        self._events[event_name].append(listener)

    def emit(self, event_name, *args, **kwargs):
        if event_name in self._events:
            for listener in self._events[event_name]:
                listener(*args, **kwargs)

emitter = EventEmitter()

class StageKind(StrEnum):
    CONTEXT = "context"      # E. Context Block
    SCORING = "scoring"      # A. Recommend Options
    INTERACTION = "interaction" # B->C. Run & Select
    PROFILE = "profile"      # G. Profile Update
    COMPLETED = "completed"

class StatusKind(StrEnum):
    NORMAL = "normal"
    Processing = "processing"
    FAILED = "failed"

STAGE_DISPLAY = {
    StageKind.CONTEXT: "1. Context Capture",
    StageKind.SCORING: "2. Engine Scoring",
    StageKind.INTERACTION: "3. User Interaction",
    StageKind.PROFILE: "4. Profile Learning",
}

class PipelineState:
    _stage: StageKind
    _status: StatusKind
    _description: str
    _data: dict
    _log_history: list

    def __init__(self):
        self._stage = StageKind.CONTEXT
        self._status = StatusKind.NORMAL
        self._description = "Ready to monitor..."
        self._data = {}
        self._log_history = []

    def set_stage(self, stage: StageKind, description: str, data: dict = None):
        self._stage = stage
        self._description = description
        if data:
            self._data = data
            # Append to history for scrollable logs
            timestamp = time.strftime("%H:%M:%S")
            self._log_history.append({
                "time": timestamp,
                "stage": stage,
                "desc": description,
                "data": data
            })
        return True

    def show_message(self):
        # Clear previous layout if needed, but Streamlit containers handle updates well
        # layout: Left (Steps) | Right (Visuals + Logs)
        
        # Use the main container defined in session state
        main = st.session_state["main_container"]
        
        with main:
            # Ensure we are working in a clean state for this frame if we were using empty(),
            # but here we are inside a container that might have content.
            # We'll use columns directly.
            
            col_left, col_right = st.columns([1, 2], gap="large")
            
            with col_left:
                st.markdown("### 🛤️ Pipeline")
                st.markdown(
                    self._build_stage_boxes(self._stage), 
                    unsafe_allow_html=True
                )
            
            with col_right:
                st.markdown("### 👁️ Live Insight")
                with st.container(border=True):
                    self._render_visuals(self._stage, self._data)
                
                st.markdown("### 📜 System Logs")
                # Scrollable container for logs
                with st.container(height=400, border=True):
                    if not self._log_history:
                        st.info("Waiting for events...")
                    else:
                        # Show newest first
                        for log in reversed(self._log_history):
                            with st.expander(f"[{log['time']}] {log['desc']} ({log['stage']})", expanded=False):
                                st.json(log['data'])

    def _render_visuals(self, stage, data):
        if stage == StageKind.CONTEXT:
            st.info("Waiting for input or processing new text...")
            if data.get('text'):
                st.code(f"Input: {data.get('text')}")
            else:
                st.caption("System is idle or initializing context.")
            
        elif stage == StageKind.SCORING:
            c1, c2 = st.columns(2)
            with c1:
                st.metric("Engine Mode", "Hybrid (Vector+Rule)")
                reco_opts = data.get("reco_options", [])
                best = reco_opts[0].get("category", "N/A") if reco_opts else "N/A"
                st.metric("Top Recommendation", best)
            
            with c2:
                scores = data.get("P_vec", {})
                if scores:
                    st.caption("Vector Scores (P_vec)")
                    st.bar_chart(scores, horizontal=True, color="#3b82f6", height=150)
            
        elif stage == StageKind.INTERACTION:
            action_type = data.get("action_type", "Unknown")
            if action_type == "run":
                st.success(f"🚀 User ran paraphrase! (Intensity: {data.get('target_intensity')})")
            elif action_type == "select":
                if data.get("was_accepted"):
                    st.balloons()
                    st.success("✅ User accepted the result!")
                else:
                    st.error("❌ User rejected/closed.")
            
        elif stage == StageKind.PROFILE:
            st.progress(data.get("profile_score", 0.5), text="Updating User Embedding...")
            st.caption("Reinforcement learning from user feedback applied.")

    def _build_stage_boxes(self, current_stage: StageKind) -> str:
        boxes = []
        for idx, (stage, label) in enumerate(STAGE_DISPLAY.items(), start=1):
            is_active = stage == current_stage
            if is_active:
                bg_color = "#dcfce7"
                border_color = "#22c55e"
                text_color = "#065f46"
                indicator_color = "#16a34a"
                status_text = "Processing..."
                scale = "transform: scale(1.02);"
                shadow = "box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);"
            else:
                bg_color = "#f8fafc"
                border_color = "#e2e8f0"
                text_color = "#64748b"
                indicator_color = "#cbd5f5"
                status_text = "Waiting"
                scale = ""
                shadow = "box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);"

            boxes.append(
                dedent(
                    f"""
                    <div class="stage-box" style="
                        width: 100%;
                        border-radius: 12px;
                        padding: 16px;
                        border: 2px solid {border_color};
                        background: {bg_color};
                        margin-bottom: 12px;
                        transition: all 0.3s ease;
                        {scale}
                        {shadow}
                    ">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <div style="font-size:0.85rem;color:#94a3b8;">STEP {idx}</div>
                            <div style="
                                width:8px; height:8px; border-radius:50%;
                                background:{indicator_color};
                                box-shadow:0 0 5px {indicator_color};
                            "></div>
                        </div>
                        <div style="font-size:1.0rem;font-weight:600;color:{text_color}; margin-top:4px;">
                            {label}
                        </div>
                        <div style="font-size:0.75rem;color:#475569;margin-top:4px;">{status_text}</div>
                    </div>
                    """
                )
            )

        return dedent(
            f"""
            <div style="display:flex; flex-direction:column; width:100%;">
                {" ".join(boxes)}
            </div>
            """
        )

# --- UI Layout ---

st.title("🌊 Data Flow Live Monitor (Real-time)")
st.caption("Watch logs transform into insights as they flow through the pipeline.")

if "state" not in st.session_state:
    st.session_state["state"] = PipelineState()

# Use a single main container that we will redraw content into
st.session_state["main_container"] = st.empty()

def update_stage(stage, desc, data):
    st.session_state["state"].set_stage(stage, desc, data)
    st.session_state["state"].show_message()

emitter.on("update", update_stage)

# --- Real-time Monitoring Logic ---

def get_mongo_client():
    uri = os.getenv("MONGO_URI", "mongodb://mongo:27017")
    return pymongo.MongoClient(uri)

def monitor_live_traffic():
    client = get_mongo_client()
    db = client["sentencify"]
    
    log_a_col = db[COLL_A] # Use COLL_A for editor_recommend_options
    log_b_col = db[COLL_B] # Use COLL_B for editor_run_paraphrasing
    log_c_col = db[COLL_C] # Use COLL_C for editor_selected_paraphrasing
    
    last_processed_id = None
    
    st.toast("Connected to MongoDB. Monitoring started...", icon="🟢")
    
    placeholder = st.empty()
    stop_btn = placeholder.button("⏹️ Stop Monitoring", type="secondary")

    while True:
        # 1. Poll for latest Recommendation (Event A)
        # Sort by natural order (insertion order) descending
        latest_a = log_a_col.find_one(sort=[("$natural", -1)])
        
        if latest_a:
            current_id = latest_a.get("insert_id")
            
            if current_id != last_processed_id:
                # --- New Transaction Detected! ---
                last_processed_id = current_id
                
                # Stage 1: Context (Simulated extract from A)
                ctx_data = {
                    "doc_id": latest_a.get("doc_id"),
                    "user_id": latest_a.get("user_id"),
                    "text": "(Text data not in Log A, refer to Context Block E)"
                }
                emitter.emit("update", StageKind.CONTEXT, "New Input Detected", ctx_data)
                time.sleep(1.5)
                
                # Stage 2: Scoring
                # Convert ObjectIDs/Datetimes to string for JSON serialization
                a_dump = json.loads(json.dumps(latest_a, default=str))
                emitter.emit("update", StageKind.SCORING, "Scoring Completed", a_dump)
                time.sleep(1.5)
                
                # Stage 3: Wait for Interaction (B or C)
                # Poll for B/C related to this insert_id for a few seconds
                found_interaction = False
                for _ in range(5): # Try for 5 seconds
                    # Check Run (B)
                    b_event = log_b_col.find_one({"source_recommend_event_id": current_id})
                    if b_event:
                        b_dump = json.loads(json.dumps(b_event, default=str))
                        b_dump["action_type"] = "run"
                        emitter.emit("update", StageKind.INTERACTION, "User Run Paraphrase", b_dump)
                        found_interaction = True
                        time.sleep(1.0)
                        
                        # Check Select (C) after Run
                        c_event = log_c_col.find_one({"source_recommend_event_id": current_id})
                        if c_event:
                            c_dump = json.loads(json.dumps(c_event, default=str))
                            c_dump["action_type"] = "select"
                            emitter.emit("update", StageKind.INTERACTION, "User Selected Result", c_dump)
                            
                            # Stage 4: Profile Update (Simulated)
                            time.sleep(1.0)
                            emitter.emit("update", StageKind.PROFILE, "Profile Updated", {"profile_score": 0.8})
                        break
                    
                    # Check Select (C) directly (rare but possible)
                    c_event = log_c_col.find_one({"source_recommend_event_id": current_id})
                    if c_event:
                         c_dump = json.loads(json.dumps(c_event, default=str))
                         c_dump["action_type"] = "select"
                         emitter.emit("update", StageKind.INTERACTION, "User Selected Result", c_dump)
                         found_interaction = True
                         break
                    
                    time.sleep(1.0)
                
                if not found_interaction:
                    st.toast("User ignored recommendation (No interaction).", icon="⚠️")
                    
        time.sleep(1.0) # Polling interval

if st.button("▶️ Start Live Monitoring", type="primary"):
    monitor_live_traffic()
else:
    st.session_state["state"].show_message()
