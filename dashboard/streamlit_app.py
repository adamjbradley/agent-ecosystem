# dashboard/streamlit_app.py
import os
import json
import threading
import time
from queue import Queue
from datetime import datetime

import streamlit as st
import redis
import pandas as pd

from agents.needs_agent import process_user_preferences, get_current_needs
from agents.opportunity_agent import generate_offer, get_current_offers
from provider_manager import list_providers

# ───────────────────────────────────────────────────────────────────────────────
# Streamlit & Redis Setup
# ───────────────────────────────────────────────────────────────────────────────
st.set_page_config(layout="wide")
st.title("Autonomous Agent Ecosystem Dashboard")

# Redis connection
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)

# ───────────────────────────────────────────────────────────────────────────────
# Session State Initialization
# ───────────────────────────────────────────────────────────────────────────────
# Persistent event queue across reruns
if "event_queue" not in st.session_state:
    st.session_state["event_queue"] = Queue()
event_queue = st.session_state["event_queue"]

# Persistent event history
if "events" not in st.session_state:
    st.session_state["events"] = []

# ───────────────────────────────────────────────────────────────────────────────
# Redis Pub/Sub Listener (background thread)
# ───────────────────────────────────────────────────────────────────────────────
def redis_listener(queue):
    pubsub = r.pubsub(ignore_subscribe_messages=True)
    pubsub.subscribe(
        "needs_stream", "needs_removed_stream",
        "offers_stream", "offers_removed_stream",
        "match_traces_stream", "providers_stream"
    )
    for msg in pubsub.listen():
        if msg.get("type") != "message":
            continue
        try:
            payload = json.loads(msg["data"])
        except json.JSONDecodeError:
            payload = msg["data"]
        queue.put({
            "timestamp": time.time(),
            "channel": msg["channel"],
            "data": payload
        })

if "listener_thread" not in st.session_state:
    threading.Thread(target=redis_listener, args=(event_queue,), daemon=True).start()
    st.session_state["listener_thread"] = True

# ───────────────────────────────────────────────────────────────────────────────
# Sidebar Controls
# ───────────────────────────────────────────────────────────────────────────────
st.sidebar.header("Controls")

# -- User needs
user_id = st.sidebar.text_input("User ID", "user_001", key="user_id_input")
if st.sidebar.button("Submit Random Need", key="btn_submit_need"):
    import random
    tags = random.sample(["eco-friendly", "quiet", "budget", "fast-delivery"], k=2)
    max_price = random.choice([300, 400, 500, 600])
    need = process_user_preferences(user_id, {"tags": tags, "price_max": max_price})
    st.sidebar.success(f"Need created: {need['need_id']}")

# -- Create an unsatisfiable need (no provider will match)
if st.sidebar.button("Submit Unsatisfiable Need", key="btn_submit_hard_need"):
    # Very low max price and a tag no provider offers
    need = process_user_preferences(
        user_id,
        {"tags": ["unobtainium"], "price_max": 1},
        ttl=86400
    )
    st.sidebar.warning(f"Unsatisfiable need created: {need['need_id']}")

# -- Generate manual offer
if st.sidebar.button("Generate Offer", key="btn_generate_offer"):
    offer = generate_offer("merchant_1", "aggregated_offers")
    st.sidebar.success(f"Offer created: {offer['offer_id']}")

# -- Providers section
st.sidebar.subheader("Active Providers")
if st.sidebar.button("Refresh Providers", key="btn_refresh_providers"):
    pass  # triggers rerun
providers = list_providers()
if providers:
    st.sidebar.table({"Provider ID": providers})
else:
    st.sidebar.write("No active providers")

# -- Manual refresh for events
if st.sidebar.button("Refresh Events", key="btn_refresh"):
    pass  # triggers rerun

# ─── Main Panel: Active Needs & Unsatisfied Alert ───────────────────────────
import time
from datetime import datetime

st.header("Active Needs & Unsatisfied Alert")
active_needs = get_current_needs()
now_ts = time.time()
UNSAT_TTL = 10  # seconds threshold for unsatisfied needs

unsatisfied = []
for need in active_needs:
    created_ts = datetime.fromisoformat(need["timestamp"]).timestamp()
    age = now_ts - created_ts
    accepted = any(
        ev["channel"] == "match_traces_stream" and
        ev["data"].get("need_id") == need["need_id"] and
        ev["data"].get("negotiation", {}).get("status") == "accepted"
        for ev in st.session_state["events"]
    )
    if age > UNSAT_TTL and not accepted:
        unsatisfied.append({**need, "age_s": round(age, 1)})

if active_needs:
    st.subheader(f"Total Active Needs: {len(active_needs)}")
    st.table(active_needs)
    if unsatisfied:
        st.error(f"{len(unsatisfied)} need(s) unsatisfied for >{UNSAT_TTL}s")
        st.table(unsatisfied)
else:
    st.write("No active needs currently.")

# ───────────────────────────────────────────────────────────────────────────────
# Main Panel: Active Offers
# ───────────────────────────────────────────────────────────────────────────────
st.header("Active Offers")
active_offers = get_current_offers()
if active_offers:
    st.table(active_offers)
else:
    st.write("No active offers currently.")

# ───────────────────────────────────────────────────────────────────────────────
# Main Panel: Live Event Log with Negotiation & Provider Details
# ───────────────────────────────────────────────────────────────────────────────
st.header("Live Event Log (Most Recent)")

# Drain the queue into session state
while not event_queue.empty():
    entry = event_queue.get_nowait()
    st.session_state["events"].append(entry)

# Prepare rows for display
rows = []
for e in sorted(st.session_state["events"], key=lambda x: x["timestamp"], reverse=True)[:20]:
    ts = datetime.fromtimestamp(e["timestamp"]).strftime("%H:%M:%S")
    ch = e["channel"]
    if ch == "match_traces_stream":
        d = e["data"]
        rows.append({
            "Time": ts,
            "Channel": ch,
            "Need ID": d.get("need_id"),
            "Offer ID": d.get("offer_id"),
            "Score": d.get("score"),
            "Status": d.get("negotiation", {}).get("status"),
            "Offered Price": d.get("negotiation", {}).get("offered_price"),
            "Max Price": d.get("negotiation", {}).get("max_user_price"),
            "Removed": d.get("need_removed")
        })
    elif ch == "providers_stream":
        d = e["data"]
        rows.append({
            "Time": ts,
            "Channel": ch,
            "Need ID": "",
            "Offer ID": "",
            "Score": "",
            "Status": d.get("action"),
            "Offered Price": "",
            "Max Price": "",
            "Removed": "",
            "Provider": d.get("provider_id")
        })
    else:
        rows.append({
            "Time": ts,
            "Channel": ch,
            "Need ID": "",
            "Offer ID": "",
            "Score": "",
            "Status": "",
            "Offered Price": "",
            "Max Price": "",
            "Removed": "",
            "Provider": ""
        })

# Display as table
if rows:
    df = pd.DataFrame(rows)
    # Coerce numeric columns for Arrow compatibility
    df['Score'] = pd.to_numeric(df['Score'], errors='coerce')
    df['Offered Price'] = pd.to_numeric(df['Offered Price'], errors='coerce')
    df['Max Price'] = pd.to_numeric(df['Max Price'], errors='coerce')
    # Coerce Removed column to boolean, treating empty/missing as False
    df['Removed'] = df['Removed'].replace('', False).fillna(False).astype(bool)
    st.table(df)
else:
    st.write("No events yet.")