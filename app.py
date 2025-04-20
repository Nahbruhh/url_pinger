import streamlit as st
import threading
import time
import requests
from datetime import datetime

# Shared state
if "urls" not in st.session_state:
    st.session_state.urls = {}

if "running" not in st.session_state:
    st.session_state.running = False

# Function to ping a single URL
def ping_url(name, url, interval, status_dict):
    while st.session_state.running:
        try:
            res = requests.get(url)
            status_dict[name]["status"] = res.status_code
            status_dict[name]["last_ping"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            status_dict[name]["error"] = ""
        except Exception as e:
            status_dict[name]["status"] = "Error"
            status_dict[name]["last_ping"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            status_dict[name]["error"] = str(e)
        time.sleep(interval)

# UI
st.title("🌐 Multi-URL Pinger & Monitor")

with st.sidebar:
    st.header("➕ Add a URL")
    url_name = st.text_input("Name")
    url_input = st.text_input("URL (include http/https)")
    interval = st.number_input("Ping interval (seconds)", value=60, min_value=10)

    if st.button("Add URL"):
        if url_name and url_input:
            st.session_state.urls[url_name] = {
                "url": url_input,
                "interval": interval,
                "status": "Not started",
                "last_ping": "Never",
                "error": ""
            }
            st.success(f"Added {url_name}")

    if st.button("🚀 Start Pinging", disabled=st.session_state.running):
        st.session_state.running = True
        for name, info in st.session_state.urls.items():
            thread = threading.Thread(target=ping_url, args=(name, info["url"], info["interval"], st.session_state.urls), daemon=True)
            thread.start()

    if st.button("🛑 Stop Pinging", disabled=not st.session_state.running):
        st.session_state.running = False
        st.success("Pinging stopped")

st.header("📊 URL Status Monitor")

if not st.session_state.urls:
    st.info("No URLs added yet.")
else:
    for name, info in st.session_state.urls.items():
        col1, col2, col3, col4 = st.columns([2, 4, 2, 4])
        col1.markdown(f"**{name}**")
        col2.write(info["url"])
        col3.write(f"⏱️ {info['interval']}s")
        if info["error"]:
            col4.error(f"❌ {info['error']}")
        else:
            col4.success(f"✅ {info['status']} @ {info['last_ping']}")

