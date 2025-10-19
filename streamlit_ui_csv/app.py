import os
import time
import datetime
import json
import uuid
import boto3
import requests
import streamlit as st
from botocore.exceptions import ClientError
from dotenv import load_dotenv

# Load environment variables ONCE
load_dotenv()

# =========================
# Configuration
# =========================
CUSTOM_TEMP_DIR = "/mnt/c/workspaces/mcpserver/temp/"
S3_BUCKET = "050593425983my-mcp-bucket"
S3_PREFIX = "temp"
MAX_HISTORY = 25
MAX_RENDER_CHARS = 8000

# =========================
# Page Configuration
# =========================
st.set_page_config(
    page_title="MCP CSV Intelligence",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =========================
# Cached Resources
# =========================
@st.cache_resource
def get_s3_client():
    """Get S3 client - cached once"""
    os.makedirs(CUSTOM_TEMP_DIR, exist_ok=True)
    return boto3.client('s3')

# =========================
# Session State Init
# =========================
if "messages" not in st.session_state:
    st.session_state.messages = []
if "csv_uploaded" not in st.session_state:
    st.session_state.csv_uploaded = False
if "logs" not in st.session_state:
    st.session_state.logs = []
if "file_info" not in st.session_state:
    st.session_state.file_info = {}
if "token_cache" not in st.session_state:
    st.session_state.token_cache = {}

# =========================
# Logging
# =========================
def add_log(message: str):
    """Add log entry"""
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    st.session_state.logs.append(f"[{timestamp}] {message}")

# =========================
# Token Management (In-Memory Cache)
# =========================
def get_or_refresh_token(task_type: str) -> str:
    """Get token from session cache or fetch new one"""

    # Check in-memory cache first
    cache_key = f"{task_type}_token"
    if cache_key in st.session_state.token_cache:
        token_data = st.session_state.token_cache[cache_key]
        if time.time() - token_data['timestamp'] < 3300:  # 55 minutes
            return token_data['token']

    # Get fresh token
    env_map = {
        "csv": ('CSV_DISCOVERY_URL', 'CSV_CLIENT_ID', 'CSV_CLIENT_SECRET'),
        "dashboard": ('DASHBOARD_DISCOVERY_URL', 'DASHBOARD_CLIENT_ID', 'DASHBOARD_CLIENT_SECRET')
    }

    env_keys = env_map[task_type]
    discovery_url = os.getenv(env_keys[0])
    client_id = os.getenv(env_keys[1])
    client_secret = os.getenv(env_keys[2])

    # Get token endpoint
    response = requests.get(discovery_url, timeout=10)
    token_endpoint = response.json().get('token_endpoint')

    # Get token
    response = requests.post(
        token_endpoint,
        data={
            'grant_type': 'client_credentials',
            'client_id': client_id,
            'client_secret': client_secret,
        },
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        timeout=10
    )

    token = response.json().get('access_token')

    # Cache in session state
    st.session_state.token_cache[cache_key] = {
        'token': token,
        'timestamp': time.time()
    }

    return token

# =========================
# S3 Operations
# =========================
def upload_to_s3(local_path: str, file_name: str) -> str:
    """Upload file to S3"""
    s3_client = get_s3_client()
    s3_key = f"{S3_PREFIX}/{file_name}"

    try:
        s3_client.upload_file(local_path, S3_BUCKET, s3_key)
        add_log(f"✅ Uploaded: {s3_key}")
        return s3_key
    except ClientError as e:
        add_log(f"❌ Upload failed: {e}")
        return None

def delete_from_s3(s3_key: str) -> bool:
    """Delete file from S3"""
    s3_client = get_s3_client()
    try:
        s3_client.delete_object(Bucket=S3_BUCKET, Key=s3_key)
        add_log("✅ Deleted from S3")
        return True
    except ClientError as e:
        add_log(f"❌ Delete failed: {e}")
        return False

# =========================
# Agent Invocation
# =========================
def invoke_csv_agent(bearer_token: str, question: str):
    """Invoke CSV agent"""
    agent_arn = os.getenv('CSV_AGENT_ARN')
    region = os.getenv('CSV_REGION', 'us-east-1')

    if not agent_arn:
        return "❌ CSV_AGENT_ARN not set"

    encoded_arn = agent_arn.replace(':', '%3A').replace('/', '%2F')
    url = f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT"

    headers = {
        "Authorization": f"Bearer {bearer_token}",
        "Content-Type": "application/json",
        "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": str(uuid.uuid4()),
        "Accept": "text/event-stream"
    }

    try:
        response = requests.post(url, headers=headers, json={"prompt": question}, timeout=120)
        response.raise_for_status()

       # Try parsing JSON
        try:
            data = response.json()
        except json.JSONDecodeError:
            print("⚠️ Response is not valid JSON, returning raw text.")
            return response.text.strip()

        # Normalize different response shapes
        if isinstance(data, dict):
            if "result" in data:
                result = data["result"]
            elif "output" in data:
                result = data["output"]
            elif "response" in data:
                result = data["response"]
            else:
                result = json.dumps(data, indent=2)
        else:
            result = str(data)

        print("✅ Response received successfully!\n")
        print(result.strip())
        return result.strip()

        return "No response from agent"

    except Exception as e:
        return f"❌ Error: {e}"

def invoke_dashboard_agent(bearer_token: str, question: str):
    """Invoke dashboard agent"""
    agent_arn = os.getenv('DASHBOARD_AGENT_ARN')
    region = os.getenv('DASHBOARD_REGION', 'us-east-1')

    if not agent_arn:
        return None

    encoded_arn = agent_arn.replace(':', '%3A').replace('/', '%2F')
    url = f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT"

    headers = {
        "Authorization": f"Bearer {bearer_token}",
        "Content-Type": "application/json",
        "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": str(uuid.uuid4()),
        "Accept": "text/event-stream"
    }

    try:
        response = requests.post(url, headers=headers, json={"prompt": question}, timeout=180)
        response.raise_for_status()

        html_content = response.text.strip()
        if html_content:
            html_file = os.path.join(CUSTOM_TEMP_DIR, "s1.html")
            with open(html_file, "w", encoding="utf-8") as f:
                f.write(html_content)
            return html_content

        return None
    except Exception as e:
        add_log(f"❌ Dashboard error: {e}")
        return None

# =========================
# Main App
# =========================
st.title("🧠 MCP CSV Intelligence Platform")
st.caption("Advanced CSV Analysis & Dashboard Generation")

# =========================
# Sidebar
# =========================
with st.sidebar:
    st.header("📋 Control Panel")

    st.subheader("📁 File Upload")

    # Only show uploader if no file uploaded
    if not st.session_state.csv_uploaded:
        uploaded_file = st.file_uploader("Choose a CSV file", type=["csv"], key="csv_uploader")

        if uploaded_file is not None:
            # Save file locally
            temp_path = os.path.join(CUSTOM_TEMP_DIR, f"uploaded_{uploaded_file.name}")
            with open(temp_path, "wb") as f:
                f.write(uploaded_file.getbuffer())

            # Upload to S3
            s3_key = upload_to_s3(temp_path, uploaded_file.name)

            if s3_key:
                # Store in session state
                st.session_state.file_info = {
                    'name': uploaded_file.name,
                    'path': temp_path,
                    's3_key': s3_key,
                    'size_kb': len(uploaded_file.getbuffer()) / 1024,
                    'upload_time': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                st.session_state.csv_uploaded = True
                st.session_state.messages = []
                st.rerun()
    else:
        # Show file info
        st.success("✅ File uploaded!")
        with st.expander("📄 File Details", expanded=False):
            info = st.session_state.file_info
            st.write(f"**Name:** {info['name']}")
            st.write(f"**Size:** {info['size_kb']:.2f} KB")
            st.write(f"**S3:** `{info['s3_key']}`")
            st.write(f"**Time:** {info['upload_time']}")

        # Remove file button
        if st.button("🗑️ Remove File", use_container_width=True):
            # Delete from S3
            delete_from_s3(st.session_state.file_info['s3_key'])

            # Delete local file
            if os.path.exists(st.session_state.file_info['path']):
                os.remove(st.session_state.file_info['path'])

            # Clear state
            st.session_state.csv_uploaded = False
            st.session_state.messages = []
            st.session_state.file_info = {}
            st.rerun()

    st.divider()

    # Status
    st.subheader("📊 Status")
    if st.session_state.csv_uploaded:
        st.success("🟢 Ready for Analysis")
    else:
        st.warning("🟡 Waiting for File")

    st.divider()

    # Clear logs
    if st.button("🧹 Clear Logs", use_container_width=True):
        st.session_state.logs = []
        st.rerun()

# =========================
# Main Content
# =========================
if not st.session_state.csv_uploaded:
    st.info("👋 **Welcome!** Upload a CSV file in the sidebar to get started.")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("### 💬 Chat")
        st.write("Ask questions about your data using natural language")
    with col2:
        st.markdown("### 📊 Dashboard")
        st.write("Generate interactive visualizations automatically")
    with col3:
        st.markdown("### 🔍 Insights")
        st.write("Explore patterns and trends in your data")

    st.stop()

# Create tabs
tab1, tab2, tab3 = st.tabs(["💬 Chat Assistant", "📊 Dashboard Generator", "📋 Activity Logs"])

# =========================
# Chat Tab
# =========================
with tab1:
    st.subheader("💬 Chat with Your Data")

    # Display chat history
    for msg in st.session_state.messages:
        with st.chat_message(msg['role']):
            st.markdown(msg['content'])

    # Chat input
    user_input = st.chat_input("Ask me anything about your data...")

    if user_input:
        # Add user message
        st.session_state.messages.append({"role": "user", "content": user_input})

        # Show user message
        with st.chat_message("user"):
            st.markdown(user_input)

        # Get AI response
        with st.chat_message("assistant"):
            with st.spinner("🤔 Analyzing..."):
                try:
                    token = get_or_refresh_token("csv")
                    response = invoke_csv_agent(token, user_input)
                    st.markdown(response)
                    st.session_state.messages.append({"role": "assistant", "content": response})
                    add_log("✅ CSV query completed")
                except Exception as e:
                    error_msg = f"❌ Error: {e}"
                    st.error(error_msg)
                    st.session_state.messages.append({"role": "assistant", "content": error_msg})
                    add_log(f"❌ CSV query failed: {e}")

        # Trim history
        if len(st.session_state.messages) > MAX_HISTORY:
            st.session_state.messages = st.session_state.messages[-MAX_HISTORY:]

# =========================
# Dashboard Tab
# =========================
with tab2:
    st.subheader("📊 Generate Interactive Dashboard")

    dashboard_query = st.text_input(
        "Describe the dashboard you want to create:",
        placeholder="e.g., Create a sales dashboard with revenue trends by region"
    )

    if st.button("🚀 Generate Dashboard", type="primary"):
        if dashboard_query:
            with st.spinner("✨ Creating your dashboard..."):
                try:
                    token = get_or_refresh_token("dashboard")
                    html_content = invoke_dashboard_agent(token, dashboard_query)
                    print(html_content)

                    if html_content:
                        data = json.loads(html_content) if isinstance(html_content, str) else html_content
                        html_code = data.get("result", "")
                        st.divider()
                        st.success("✅ Dashboard generated successfully!")
                        st.components.v1.html(html_code, height=700, scrolling=True)
                        add_log("✅ Dashboard generated")
                    else:
                        st.error("❌ Failed to generate dashboard")
                        add_log("❌ Dashboard generation failed")
                except Exception as e:
                    st.error(f"❌ Error: {e}")
                    add_log(f"❌ Dashboard error: {e}")
        else:
            st.warning("⚠️ Please enter a dashboard description")

# =========================
# Logs Tab
# =========================
with tab3:
    st.subheader("📋 Activity Logs")

    if st.session_state.logs:
        for log in reversed(st.session_state.logs[-50:]):
            st.text(log)
    else:
        st.info("No activity logs yet. Start using the application to see logs here.")

# =========================
# Footer
# =========================
st.divider()
st.caption("Built with Streamlit • Powered by AWS Bedrock • Secure & Fast")