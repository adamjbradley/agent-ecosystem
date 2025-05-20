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
from agents.users_agent import list_users
from provider_manager import list_providers

import random  # make sure this is imported near the top

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
if "event_queue" not in st.session_state:
    st.session_state["event_queue"] = Queue()
event_queue = st.session_state["event_queue"]

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
        "match_traces_stream", "providers_stream",
        "needs_unsatisfied_stream"
    )
    for msg in pubsub.listen():
        if msg.get("type") != "message":
            continue
        try:
            payload = json.loads(msg["data"])
        except json.JSONDecodeError:
            payload = msg["data"]
        channel = msg["channel"]
        if isinstance(channel, bytes):
            channel = channel.decode()
        queue.put({
            "timestamp": time.time(),
            "channel": channel,
            "data": payload
        })

if "listener_thread" not in st.session_state:
    threading.Thread(target=redis_listener, args=(event_queue,), daemon=True).start()
    st.session_state["listener_thread"] = True

# ───────────────────────────────────────────────────────────────────────────────
# Sidebar Controls
# ───────────────────────────────────────────────────────────────────────────────
user_id = st.sidebar.text_input("User ID", "user_001", key="user_id_input")

 #-- Submit Random Need
if st.sidebar.button("Submit Random Need", key="btn_submit_need"):
    existing_users = list_users()
    # If no user_id entered, pick one at random
    target_user = user_id.strip() or (random.choice(existing_users) if existing_users else "")
    if not target_user or target_user not in existing_users:
        st.sidebar.error(f"Cannot create need: user '{target_user or user_id}' is not registered.")
    else:
        tags = random.sample(["eco-friendly", "quiet", "budget", "fast-delivery"], k=2)
        max_price = random.choice([300, 400, 500, 600])
        need = process_user_preferences(target_user, {"tags": tags, "price_max": max_price})
        st.sidebar.success(f"Need created for {target_user}: {need['need_id']}")

# -- Submit Unsatisfiable Need
if st.sidebar.button("Submit Unsatisfiable Need", key="btn_submit_hard_need"):
    existing_users = list_users()
    target_user = user_id.strip() or (random.choice(existing_users) if existing_users else "")
    if not target_user or target_user not in existing_users:
        st.sidebar.error(f"Cannot create need: user '{target_user or user_id}' is not registered.")
    else:
        need = process_user_preferences(
            target_user,
            {"tags": ["unobtainium"], "price_max": 1},
            ttl=86400  # 1 day TTL
        )
        st.sidebar.warning(f"Unsatisfiable need created for {target_user}: {need['need_id']}")
 
# Generate Manual Offer
if st.sidebar.button("Generate Offer", key="btn_generate_offer"):
    offer = generate_offer("merchant_1", "aggregated_offers")
    st.sidebar.success(f"Offer created: {offer['offer_id']}")

# Active Providers
st.sidebar.subheader("Active Providers")
if st.sidebar.button("Refresh Providers", key="btn_refresh_providers"):
    pass
providers = list_providers()
if providers:
    st.sidebar.table({"Provider ID": providers})
else:
    st.sidebar.write("No active providers")

# Registered Users
st.sidebar.subheader("Registered Users")
if st.sidebar.button("Refresh Users", key="btn_refresh_users"):
    pass
users = list_users()
if users:
    st.sidebar.table({"User ID": users})
else:
    st.sidebar.write("No users yet")

# Manual Refresh for Events
if st.sidebar.button("Refresh Events", key="btn_refresh"):
    pass

# ───────────────────────────────────────────────────────────────────────────────
# Main Panel: Active Needs & Unsatisfied Alert
# ───────────────────────────────────────────────────────────────────────────────
import time as _time
from datetime import datetime as _dt

st.header("Active Needs & Unsatisfied Alert")
active_needs = get_current_needs()
now_ts = _time.time()
UNSAT_TTL = 10  # seconds

unsatisfied = []
for need in active_needs:
    created_ts = _dt.fromisoformat(need["timestamp"]).timestamp()
    age = now_ts - created_ts
    accepted = any(
        ev["channel"] == "match_traces_stream"
        and ev["data"].get("need_id") == need["need_id"]
        and ev["data"].get("negotiation", {}).get("status") == "accepted"
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
# Main Panel: Live Event Log (Most Recent)
# ───────────────────────────────────────────────────────────────────────────────
st.header("Live Event Log (Most Recent)")

# Drain queue
while not event_queue.empty():
    st.session_state["events"].append(event_queue.get_nowait())

# Build rows for display
rows = []
for e in sorted(st.session_state["events"], key=lambda x: x["timestamp"], reverse=True)[:20]:
    ts = datetime.fromtimestamp(e["timestamp"]).strftime("%H:%M:%S")
    ch = e["channel"]
    data = e.get("data", {})

    if ch == "needs_stream":
        rows.append({
            "Time": ts,
            "Channel": ch,
            "Need ID": data.get("need_id"),
            "User ID": data.get("user_id"),
            "Preferences": json.dumps(data.get("preferences", {})),
            "Offer ID": "",
            "Status": "",
            "Provider": ""
        })
    elif ch == "offers_stream":
        rows.append({
            "Time": ts,
            "Channel": ch,
            "Need ID": "",
            "Offer ID": data.get("offer_id"),
            "Provided By": data.get("provided_by"),
            "Product": json.dumps(data.get("product", {})),
            "Status": "",
            "Provider": ""
        })
    elif ch == "match_traces_stream":
        d = data
        rows.append({
            "Time": ts,
            "Channel": ch,
            "Need ID": d.get("need_id"),
            "Offer ID": d.get("offer_id"),
            "Score": d.get("score"),
            "Status": d.get("negotiation", {}).get("status"),
            "Offered Price": d.get("negotiation", {}).get("offered_price"),
            "Max Price": d.get("negotiation", {}).get("max_user_price"),
            "Removed": d.get("need_removed"),
            "Provider": ""
        })
    elif ch == "providers_stream":
        d = data
        rows.append({
            "Time": ts,
            "Channel": ch,
            "Need ID": "",
            "Offer ID": "",
            "Score": "",
            "Status": d.get("action"),
            "Removed": "",
            "Provider": d.get("provider_id")
        })
    elif ch == "needs_unsatisfied_stream":
        d = data
        rows.append({
            "Time": ts,
            "Channel": ch,
            "Need ID": d.get("need_id"),
            "Age (s)": round(d.get("age_s", 0), 1),
            "Notes": "Unsatisfied threshold exceeded"
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

# Convert to DataFrame & coerce types

df = pd.DataFrame(rows)
for col in ['Score', 'Offered Price', 'Max Price']:
    if col not in df.columns:
        df[col] = None
    df[col] = pd.to_numeric(df[col], errors='coerce')

if 'Removed' not in df.columns:
    df['Removed'] = False

df['Removed'] = df['Removed'].replace('', False).fillna(False).astype(bool)

st.table(df)