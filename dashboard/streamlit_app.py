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

import random  # make sure this is imported near the top

from agents.needs_agent import process_user_preferences, get_current_needs
from agents.opportunity_agent import generate_offer, get_current_offers, list_all_merchants_products
from agents.users_agent import list_users
from provider_manager import list_providers
from agents.supplier_agent import get_current_products
from provider_manager import register_provider

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

# call this once for each merchant ID you want active:
for m in [
    "merchant_travel",
    "merchant_electronics",
    "merchant_financial",
    "merchant_clothing",
    "merchant_home",
    "merchant_books",
    "merchant_food",
    "merchant_health",
    "merchant_automotive",
]:
    register_provider(m)

# ───────────────────────────────────────────────────────────────────────────────
# Redis Pub/Sub Listener (background thread)
# ───────────────────────────────────────────────────────────────────────────────
def redis_listener(queue):
    pubsub = r.pubsub(ignore_subscribe_messages=True)
    pubsub.subscribe(
        "needs_stream", "needs_removed_stream",
        "offers_stream", "offers_removed_stream",
        "match_traces_stream", "providers_stream",
        "needs_unsatisfied_stream", "products_stream"
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

st.sidebar.metric("Needs requested", r.get("metrics:needs_requested") or 0)
st.sidebar.metric("Needs satisfied", r.get("metrics:needs_met") or 0)

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

st.sidebar.markdown("---")  # visual separator

# Generate Manual Offer
if st.sidebar.button("Generate Offer", key="btn_generate_offer"):
    offer = generate_offer("merchant_1", "aggregated_offers")
    if offer is not None:
        st.sidebar.success(f"Offer created: {offer['offer_id']}")
    else:
        st.sidebar.warning("No offer created: merchant has no stocked inventory")

st.sidebar.markdown("---")  # visual separator

if st.sidebar.button("Reset All Data", key="btn_reset_data"):
    # Flush every key in Redis
    r.flushdb()
    # Clear the local event history
    st.session_state["events"] = []
    st.sidebar.success("All Redis data and event history have been reset.")

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


st.sidebar.subheader("Active Products")
products = get_current_products()
if products:
    # Show all current product entries
    df_products = pd.DataFrame(products)
    st.sidebar.table(df_products)
else:
    st.sidebar.write("No active products")

# ───────────────────────────────────────────────────────────────────────────────
# Sidebar: Merchant Product Offerings (Product Names Only)
# ───────────────────────────────────────────────────────────────────────────────
st.sidebar.subheader("Merchant Product Offerings")
# Get the unique product_ids each merchant is offering
products_by_merchant = list_all_merchants_products()
if products_by_merchant:
    # Build a lookup of product_id to product name
    all_products = get_current_products()
    name_map = {p['product_id']: p['attributes'].get('name','') for p in all_products}

    rows = []
    for merchant, pids in products_by_merchant.items():
        # Map each id to its name, skip empty
        names = [name_map.get(pid, pid) for pid in pids]
        rows.append({
            "Merchant ID": merchant,
            "Products": ", ".join(str(n) for n in names if n)
        })
    df_mp = pd.DataFrame(rows)
    st.sidebar.table(df_mp)
else:
    st.sidebar.write("No merchant products available")

# ───────────────────────────────────────────────────────────────────────────────
# Main Panel: Active Needs & Unsatisfied Alert
# ───────────────────────────────────────────────────────────────────────────────
st.header("Active Needs & Unsatisfied Alert")

# Fetch and timestamp
active_needs = get_current_needs()
now_ts = time.time()
UNSAT_TTL = 10  # seconds threshold

# Identify unsatisfied needs
unsatisfied = []
for need in active_needs:
    created_ts = datetime.fromisoformat(need["timestamp"]).timestamp()
    age = now_ts - created_ts
    # check if any match_trace shows it was accepted
    accepted = any(
        ev["channel"] == "match_traces_stream" and
        ev["data"].get("need_id") == need["need_id"] and
        ev["data"].get("negotiation", {}).get("status") == "accepted"
        for ev in st.session_state["events"]
    )
    if age > UNSAT_TTL and not accepted:
        unsatisfied.append({"need_id": need["need_id"], "user_id": need["user_id"], "age_s": round(age,1)})

if active_needs:
    st.subheader(f"Total Active Needs: {len(active_needs)}")

    # Build display table
    rows = []
    for n in active_needs:

        tags_list = n.get("preferences", {}).get("tags", [])
        tags = ", ".join(tags_list) if tags_list else "–"
        
        rows.append({
            "Need ID":      n.get("need_id",""),
            "User":         n.get("user_id",""),
            "Product ID":   n.get("product_id",""),
            "Product Name": n.get("product_name",""),
            "Tags":         tags,
            "Max Price":    n.get("preferences",{}).get("price_max",""),
            "Timestamp":    n.get("timestamp","")
        })
    df_needs = pd.DataFrame(rows)
    st.table(df_needs)

    if unsatisfied:
        st.error(f"{len(unsatisfied)} need(s) unsatisfied for >{UNSAT_TTL}s")
        df_unsat = pd.DataFrame(unsatisfied).rename(columns={
            "need_id":"Need ID","user_id":"User","age_s":"Age (s)"
        })
        st.table(df_unsat)
else:
    st.write("No active needs currently.")

 # ───────────────────────────────────────────────────────────────────────────────
# Main Panel: Active Offers with Merchant & Product Details
# ───────────────────────────────────────────────────────────────────────────────
st.header("Active Offers")
offers = get_current_offers()
if offers:
    rows = []
    for o in offers:
        # Nested product attributes dict (may be incomplete)
        prod = o.get("product") or {}
        # Attempt to read name and price directly
        pname = prod.get("name")
        price = prod.get("price")
        tags = prod.get("tags")
        # Fallback: lookup the full product record by ID if missing
        if not pname or price is None:
            raw = r.get(f"product:{o.get('product_id','')}")
            if raw:
                pobj = json.loads(raw)
                attrs = pobj.get("attributes", {})
                if not pname:
                    pname = attrs.get("name")
                if price is None:
                    price = attrs.get("price")
        rows.append({
            "Offer ID":     o.get("offer_id", ""),
            "Merchant":     o.get("provided_by", ""),
            "Product ID":   o.get("product_id", ""),
            "Product Name": pname or "",  # guaranteed string
            "Price":        price if price is not None else "",  # guaranteed string/number
            "Tags":         tags or "",
            "Strategy":     o.get("strategy", ""),
            "Timestamp":    o.get("timestamp", "")
        })
    df_offers = pd.DataFrame(rows)
    st.table(df_offers)
else:
    st.write("No active offers currently.")
            
# ───────────────────────────────────────────────────────────────────────────────
# Main Panel: Merchant Product Offerings
# ───────────────────────────────────────────────────────────────────────────────
st.header("Merchant Product Offerings")
merchant_offers = get_current_offers()
if merchant_offers:
    merchant_map = {}
    for offer in merchant_offers:
        m = offer.get("provided_by", "")
        # Primary: product_id; fallback to product name
        pid = offer.get("product_id") or ""
        # Extract product name if available
        prod_attrs = offer.get("product", {}) or {}
        pname = prod_attrs.get("name", "")
        # Combine for display
        if pid and pname:
            display_val = f"{pid} ({pname})"
        elif pid:
            display_val = pid
        else:
            display_val = pname
        merchant_map.setdefault(m, []).append(display_val)
    df_merchants = pd.DataFrame([
        {"Merchant ID": m, "Products": ", ".join(ids)}
        for m, ids in merchant_map.items()
    ])
    st.table(df_merchants)
else:
    st.write("No merchant offers available.")

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
    elif ch == "products_stream":
        # Handle new product events
        prod = data
        rows.append({
            "Time": ts,
            "Channel": ch,
            "Product ID": prod.get("product_id"),
            "Supplier": prod.get("supplier_id"),
            "Attributes": json.dumps(prod.get("attributes", {}))
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