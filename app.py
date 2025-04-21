import requests
import time
import matplotlib.pyplot as plt
import streamlit as st
import threading
import queue
import pandas as pd
import seaborn as sns
import io

# Dictionary mapping HTTP status codes to descriptive names
STATUS_CODE_NAMES = {
    100: "Continue",
    200: "OK",
    201: "Created",
    301: "Moved Permanently",
    302: "Found",
    400: "Bad Request",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not Found",
    429: "Too Many Requests",
    500: "Internal Server Error",
    502: "Bad Gateway",
    503: "Service Unavailable",
    None: "Request Failed"
}

def get_url_response(url):
    try:# Save plot as PNG if save_path is provided
        start_time = time.time()
        response = requests.get(url, timeout=5)
        response_time = time.time() - start_time
        return response.text, response_time, response.status_code
    except requests.exceptions.RequestException:
        return None, 0, None

def monitor_urls(urls, ping_frequency, duration, use_duration, result_queue, stop_event):
    data = {url: {"times": [], "codes": [], "names": [], "numbers": [], "elapsed": 0} for url in urls}
    start_time = time.time()
    
    while not stop_event.is_set():
        for url in urls:
            if stop_event.is_set() or (use_duration and data[url]["elapsed"] >= duration):
                continue
                
            _, resp_time, status_code = get_url_response(url)
            data[url]["times"].append(resp_time)
            data[url]["codes"].append(status_code if status_code else 0)
            data[url]["names"].append(STATUS_CODE_NAMES.get(status_code, "Unknown"))
            data[url]["numbers"].append(len(data[url]["times"]))
            data[url]["elapsed"] = time.time() - start_time
            
            # Send updated data to queue
            result_queue.put(data.copy())
        
        # Store latest data in session state
        st.session_state.last_data = data.copy()
        
        # Sleep for ping frequency
        time.sleep(ping_frequency)
        
        # Stop if all URLs have reached duration (if used)
        if use_duration and all(data[url]["elapsed"] >= duration for url in urls):
            stop_event.set()

def plot_url_data(data, url, placeholder):
    sns.set_style("whitegrid")
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 2), dpi=500)
    
    # Response time plot
    ax1.plot(data["numbers"], data["times"], 'o-', color='#008080', linewidth=2, markersize=6, label='Response Time')
    ax1.set_title(f'Response Time: {url}\nElapsed: {data["elapsed"]:.1f}s', fontsize=12, pad=10)
    ax1.set_xlabel('Request Number', fontsize=10)
    ax1.set_ylabel('Response Time (s)', fontsize=10)
    ax1.grid(True, linestyle='--', alpha=0.7)
    ax1.legend(fontsize=9)
    ax1.set_facecolor('#F5F6F5')
    
    # Annotate latest response time
    if data["times"]:
        x, y = data["numbers"][-1], data["times"][-1]
        ax1.annotate(f'{y:.2f}s', (x, y), xytext=(5, 5), textcoords='offset points', fontsize=9, color='#008080')
    
    # Status code plot
    ax2.plot(data["numbers"], data["codes"], 's-', color='#FF6F61', linewidth=2, markersize=6, 
             label=f'Status: {data["names"][-1] if data["names"] else "Unknown"}')
    ax2.set_title(f'Status Codes: {url}\nRemaining: {max(0, st.session_state.duration - data["elapsed"] if st.session_state.use_duration else float("inf")):.1f}s', 
                  fontsize=12, pad=10)
    ax2.set_xlabel('Request Number', fontsize=10)
    ax2.set_ylabel('Status Code', fontsize=10)
    ax2.grid(True, linestyle='--', alpha=0.7)
    ax2.legend(fontsize=9)
    ax2.set_facecolor('#F5F6F5')
    
    # Annotate latest status code
    if data["codes"]:
        x, y = data["numbers"][-1], data["codes"][-1]
        ax2.annotate(f'{data["names"][-1]}', (x, y), xytext=(5, 5), textcoords='offset points', fontsize=9, color='#FF6F61')
    
    # Adjust layout
    plt.tight_layout()

    buffer = io.BytesIO()
    fig.savefig(buffer, format='png', bbox_inches='tight')
    buffer.seek(0)

    # Save plot as PNG if save_path is provided
    # if save_path:
    #     fig.savefig(save_path, format='png', bbox_inches='tight')
    
    # Update plot in Streamlit
    placeholder.pyplot(fig)
    plt.close(fig)
    return buffer


def data_to_csv(data, url):
    if not data or url not in data or not data[url]["times"]:
        return None
    
    df = pd.DataFrame({
        'Request Number': data[url]["numbers"],
        'Response Time (s)': data[url]["times"],
        'Status Code': data[url]["codes"],
        'Status Name': data[url]["names"],
        'Elapsed Time (s)': [data[url]["elapsed"]] * len(data[url]["numbers"])
    })
    return df.to_csv(index=False).encode('utf-8')



def main():
    st.title("🌐URL Monitor")
    
    # Input for URLs and timing
    st.sidebar.subheader("⚙️Configure Monitoring")
    urls_input = st.sidebar.text_area("📡Enter URLs (one per line):", "http://localhost:8501\nhttps://simxlab.work\nhttps://cog-calculator.streamlit.app/\nhttps://fea-nonlinear-prediction.streamlit.app/",height=200)
    ping_frequency = st.sidebar.number_input("⏱️Ping Frequency (seconds between pings)", min_value=0.1, max_value=60.0, value=2.0, step=0.1)
    use_duration = st.sidebar.checkbox("Specify Monitoring Duration", value=False)
    duration = st.sidebar.number_input("Monitoring Duration per URL (seconds)", min_value=1, max_value=3600, value=60, step=1, disabled=not use_duration)
    
    # Parse URLs and store in session state
    urls = [url.strip() for url in urls_input.split("\n") if url.strip()]
    st.session_state.urls = urls
    st.session_state.duration = duration
    st.session_state.use_duration = use_duration
    
    # Session state for monitoring control and last data
    if "monitoring" not in st.session_state:
        st.session_state.monitoring = False
        st.session_state.stop_event = threading.Event()
        st.session_state.result_queue = queue.Queue()
        st.session_state.last_data = {}
    
    # Start/Stop buttons
    col1, col2 = st.columns(2)
    with col1:
        if st.button("▶️Start Monitoring") and not st.session_state.monitoring:
            if urls:
                st.session_state.monitoring = True
                st.session_state.stop_event.clear()
                thread = threading.Thread(
                    target=monitor_urls,
                    args=(
                        urls,
                        ping_frequency,
                        duration,
                        use_duration,
                        st.session_state.result_queue,
                        st.session_state.stop_event
                    )
                )
                thread.daemon = True
                thread.start()
            else:
                st.error("Please enter at least one URL.")

    # Stop Monitoring
    with col2:
        if st.button("⏹️Stop Monitoring"):
            if st.session_state.monitoring:
                st.session_state.stop_event.set()
                st.session_state.monitoring = False  # Let main loop exit
    
    # Prepare placeholders
    if urls:
        st.subheader("📊 Monitoring Results")
        placeholders = {url: st.empty() for url in urls}

        # Live monitoring loop
        if st.session_state.monitoring:
            while st.session_state.monitoring:
                try:
                    data = st.session_state.result_queue.get(timeout=0.2)
                    if data:
                        st.session_state.last_data = data  # Save last result
                        for url in urls:
                            if url in data:
                                plot_url_data(data[url], url, placeholders[url])
                except queue.Empty:
                    pass
                time.sleep(0.1)

        # After stopping, still show last plots
        elif st.session_state.last_data:
            for url in urls:
                if url in st.session_state.last_data:
                    plot_url_data(st.session_state.last_data[url], url, placeholders[url])

            # Download buttons
            
            with st.expander("📥Download Options", expanded=True):
                st.markdown("You can download the monitoring data as CSV or PNG plot.")
                col1, col2 = st.columns(2)
                for url in urls:
                    if url in st.session_state.last_data:
                        buffer = plot_url_data(st.session_state.last_data[url], url,placeholders[url])
                        csv_data = data_to_csv(st.session_state.last_data, url)
                        # Download buttons for CSV and PNG
                        with col1:
                            if csv_data:
                                st.download_button(
                                    label=f" Download CSV - {url}",
                                    data=csv_data,
                                    file_name=f"{url.replace('http://', '').replace('https://', '').replace('/', '_')}_data.csv",
                                    mime="text/csv",
                                    key=f"{url}-csv"
                                )
                        with col2:

                            if buffer:
                                st.download_button(
                                    label=f" Download Plot - {url}",
                                    data=buffer,
                                    file_name=f"{url.replace('http://', '').replace('https://', '').replace('/', '_')}_plot.png",
                                    mime="image/png",
                                    key=f"{url}-png"
                                )
    else:
        st.info("Enter at least one URL to begin monitoring.")


st.set_page_config(
    page_title="URL Monitor",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="expanded",
)

with st.expander("ℹ️ About this App"):
    st.markdown("""
    **🌐 URL Monitor** is a simple tool that helps you track the availability and response time of multiple URLs in real-time.

    **Author**: Copyright (c) Nguyen Manh Tuan [GitHub](https://github.com/Nahbruhh) | [LinkedIn](https://www.linkedin.com/in/manh-tuan-nguyen19/) 

    ### Features:
    > - Enter one or more URLs and ping them at regular intervals
    > - Visualize response time over time for each URL
    > - Set a custom ping frequency and optional monitoring duration
    > - Download monitoring data as **CSV** or **PNG plot**
    > - Stop monitoring anytime and keep your results

    ### Use Cases:
    > - Keep your deployed web apps (e.g. Streamlit, Heroku, Onrender) alive and prevent idle timeout
    > - Monitor development servers and endpoints during testing
    > - Track public or private website uptime and response behavior
    > - Use logs for performance analysis or debugging

    > Built with ❤️ using Streamlit.
    """, unsafe_allow_html=True)




if __name__ == "__main__":
    main()