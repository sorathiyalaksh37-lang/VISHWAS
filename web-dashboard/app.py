"""
VISHWAS Web Dashboard
Streamlit-based interface for call fraud detection analysis.
"""
import streamlit as st
import time
from datetime import datetime
from api_client import VishwasAPIClient
import os

# Page configuration
st.set_page_config(
    page_title="VISHWAS - Call Fraud Detection",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize API client
API_BASE_URL = os.getenv("VISHWAS_API_URL", "http://localhost:8000/api/v1")
api_client = VishwasAPIClient(API_BASE_URL)

# Sidebar
with st.sidebar:
    st.title("🛡️ VISHWAS")
    st.caption("AI-Powered Call Fraud Detection")
    
    # Backend health check
    health = api_client.health_check()
    if health:
        st.success(f"✅ Backend: {health.get('status', 'unknown').upper()}")
        st.caption(f"Version: {health.get('version', 'unknown')}")
    else:
        st.error("❌ Backend Unavailable")
        st.caption("Check if the backend server is running")
    
    st.divider()
    
    # Navigation
    page = st.radio(
        "Navigation",
        ["📊 Dashboard", "📤 Upload Recording", "📋 Analysis History", "ℹ️ About"],
        label_visibility="collapsed"
    )
    
    st.divider()
    
    # Phase 1 notice
    st.warning("⚠️ **Phase 1: Mock Analysis**\n\nCurrent analysis results are for demonstration only.")

# Helper functions
def format_datetime(dt_str):
    """Format ISO datetime string for display."""
    try:
        dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except:
        return dt_str


def get_risk_color(risk_level):
    """Get color for risk level."""
    colors = {
        "low": "green",
        "medium": "orange",
        "high": "red",
        "critical": "darkred"
    }
    return colors.get(risk_level.lower(), "gray")


def display_report(report):
    """Display analysis report."""
    if not report:
        st.error("Failed to load report")
        return
    
    if report.get("status") == "in_progress":
        st.info("⏳ Analysis in progress. Please wait...")
        return
    
    # Mock indicator
    if report.get("is_mock"):
        st.info("🔬 **Mock Analysis Mode** - This is demonstration data, not real fraud detection")
    
    # Risk level
    risk_level = report.get("risk_level", "unknown")
    risk_color = get_risk_color(risk_level)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Risk Level", risk_level.upper())
    with col2:
        st.metric("Language", report.get("language", "Unknown").upper())
    with col3:
        st.metric("Analysis Mode", report.get("analysis_mode", "unknown").upper())
    
    # Warnings
    warnings = report.get("warnings", [])
    if warnings:
        st.warning("**Warnings:**\n" + "\n".join(f"- {w}" for w in warnings))
    
    # Risk factors
    st.subheader("🎯 Risk Factors")
    reasons = report.get("reasons", [])
    if reasons:
        for reason in reasons:
            st.markdown(f"- {reason}")
    else:
        st.info("No specific risk factors identified")
    
    # Recommended actions
    st.subheader("✅ Recommended Actions")
    actions = report.get("recommended_actions", [])
    if actions:
        for action in actions:
            st.markdown(f"- {action}")
    
    # Agent findings
    st.subheader("🔍 Detection Findings")
    findings = report.get("agent_findings", [])
    if findings:
        for finding in findings:
            severity = finding.get("severity", "unknown")
            with st.expander(f"{finding.get('signal', 'Unknown')} - {severity.upper()}"):
                st.write(f"**Agent:** {finding.get('agent', 'unknown')}")
                st.write(f"**Severity:** {severity}")
                st.write(f"**Evidence:** {finding.get('evidence_text', '')}")
                if finding.get('start_time') is not None:
                    st.write(f"**Time:** {finding.get('start_time')}s - {finding.get('end_time')}s")
                st.caption(f"Source: {finding.get('source', 'unknown')}")
    else:
        st.info("No suspicious patterns detected")
    
    # Transcript
    transcript = report.get("transcript")
    if transcript:
        st.subheader("📝 Transcript")
        segments = transcript.get("segments", [])
        if segments:
            for i, segment in enumerate(segments, 1):
                st.text(f"[{segment.get('start', 0):.1f}s - {segment.get('end', 0):.1f}s] {segment.get('text', '')}")
        else:
            st.info("No transcript available")
    
    # Metadata
    with st.expander("📊 Metadata"):
        st.write(f"**Call ID:** {report.get('call_id', 'unknown')}")
        st.write(f"**Status:** {report.get('status', 'unknown')}")
        st.write(f"**Created:** {format_datetime(report.get('created_at', ''))}")
        if report.get('completed_at'):
            st.write(f"**Completed:** {format_datetime(report.get('completed_at'))}")


# Main content
if page == "📊 Dashboard":
    st.title("📊 Dashboard")
    st.caption("Overview of call fraud detection system")
    
    # Get statistics
    calls_data = api_client.list_calls(page=1, page_size=100)
    
    if calls_data:
        total = calls_data.get("pagination", {}).get("total", 0)
        calls = calls_data.get("calls", [])
        
        # Status breakdown
        status_counts = {}
        for call in calls:
            status = call.get("status", "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1
        
        # Display metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Analyses", total)
        with col2:
            st.metric("Completed", status_counts.get("completed", 0))
        with col3:
            st.metric("In Progress", status_counts.get("processing", 0) + status_counts.get("queued", 0))
        with col4:
            st.metric("Failed", status_counts.get("failed", 0))
        
        st.divider()
        
        # Recent calls
        st.subheader("Recent Analyses")
        if calls:
            for call in calls[:5]:
                with st.container():
                    col1, col2, col3 = st.columns([3, 2, 1])
                    with col1:
                        st.write(f"**{call.get('original_filename', 'Unknown')}**")
                        st.caption(f"ID: {call.get('call_id', 'unknown')[:8]}...")
                    with col2:
                        st.write(f"Status: `{call.get('status', 'unknown')}`")
                        st.caption(format_datetime(call.get('created_at', '')))
                    with col3:
                        if st.button("View", key=call.get('call_id')):
                            st.session_state.selected_call_id = call.get('call_id')
                            st.rerun()
                st.divider()
        else:
            st.info("No analyses yet. Upload a recording to get started!")
    else:
        st.error("Unable to fetch dashboard data. Check backend connection.")

elif page == "📤 Upload Recording":
    st.title("📤 Upload Recording")
    st.caption("Upload a call recording for fraud analysis")
    
    # File uploader
    uploaded_file = st.file_uploader(
        "Choose an audio file",
        type=["wav", "mp3", "m4a"],
        help="Supported formats: WAV, MP3, M4A (max 50MB)"
    )
    
    if uploaded_file:
        # Display file info
        st.info(f"**File:** {uploaded_file.name}\n\n**Size:** {uploaded_file.size / 1024:.2f} KB")
        
        if st.button("🚀 Upload and Analyze", type="primary"):
            with st.spinner("Uploading..."):
                result = api_client.upload_recording_bytes(
                    uploaded_file.getvalue(),
                    uploaded_file.name
                )
                
                if result:
                    st.success(f"✅ Upload successful!")
                    call_id = result.get("call_id")
                    
                    st.info(f"**Call ID:** {call_id}\n\n**Status:** {result.get('status')}")
                    
                    # Poll for completion
                    st.write("Waiting for analysis to complete...")
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    max_wait = 15  # seconds
                    waited = 0
                    interval = 0.5
                    
                    while waited < max_wait:
                        status_data = api_client.get_call_status(call_id)
                        if status_data:
                            current_status = status_data.get("status")
                            status_text.text(f"Status: {current_status}")
                            
                            if current_status == "completed":
                                progress_bar.progress(100)
                                st.success("✅ Analysis complete!")
                                
                                # Show report
                                report = api_client.get_report(call_id)
                                if report:
                                    st.divider()
                                    display_report(report)
                                break
                            elif current_status == "failed":
                                st.error(f"❌ Analysis failed: {status_data.get('error_message', 'Unknown error')}")
                                break
                        
                        time.sleep(interval)
                        waited += interval
                        progress_bar.progress(int((waited / max_wait) * 100))
                    
                    if waited >= max_wait:
                        st.warning("⏰ Analysis is taking longer than expected. Check the History page for results.")
                else:
                    st.error("❌ Upload failed. Check backend connection and file format.")

elif page == "📋 Analysis History":
    st.title("📋 Analysis History")
    st.caption("View all previous analyses")
    
    # Filters
    col1, col2 = st.columns([3, 1])
    with col1:
        status_filter = st.selectbox(
            "Filter by status",
            ["All", "completed", "processing", "queued", "failed"]
        )
    with col2:
        if st.button("🔄 Refresh"):
            st.rerun()
    
    # Get calls
    calls_data = api_client.list_calls(page=1, page_size=50)
    
    if calls_data:
        calls = calls_data.get("calls", [])
        
        # Apply filter
        if status_filter != "All":
            calls = [c for c in calls if c.get("status") == status_filter]
        
        st.write(f"**Total: {len(calls)} call(s)**")
        st.divider()
        
        # Display calls
        for call in calls:
            with st.container():
                col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
                with col1:
                    st.write(f"**{call.get('original_filename', 'Unknown')}**")
                    st.caption(f"ID: {call.get('call_id', 'unknown')}")
                with col2:
                    status = call.get('status', 'unknown')
                    st.write(f"Status: `{status}`")
                with col3:
                    st.caption(f"Created: {format_datetime(call.get('created_at', ''))}")
                with col4:
                    if call.get('status') == 'completed':
                        if st.button("📊 View Report", key=f"view_{call.get('call_id')}"):
                            st.session_state.selected_call_id = call.get('call_id')
                            # Show report below
                            report = api_client.get_report(call.get('call_id'))
                            if report:
                                st.divider()
                                display_report(report)
                st.divider()
        
        if not calls:
            st.info("No analyses match the current filter.")
    else:
        st.error("Unable to fetch history. Check backend connection.")

elif page == "ℹ️ About":
    st.title("ℹ️ About VISHWAS")
    
    st.markdown("""
    ## AI-Powered Call Fraud Detection Platform
    
    VISHWAS is an intelligent system designed to analyze authorized call recordings and help identify 
    potential fraud, suspicious requests, impersonation attempts, threats, urgency tactics, and attempts 
    to obtain sensitive information.
    
    ### Current Status: Phase 1
    
    Phase 1 establishes the complete project infrastructure with a working end-to-end workflow using 
    **mock analysis**. All analysis results are clearly labeled as mock data for demonstration purposes.
    
    ### Features
    
    - ✅ Audio file upload (WAV, MP3, M4A)
    - ✅ Automated analysis workflow
    - ✅ Risk assessment and recommendations
    - ✅ Transcript generation (mock)
    - ✅ Detection agent findings (mock)
    - ✅ Analysis history tracking
    
    ### Architecture
    
    ```
    Recording Upload → Perception → Evidence Extraction → Content & Knowledge → 
    Adversarial Reasoning → Deterministic Decision → Action → Clients
    ```
    
    **Phase 1** implements the infrastructure with clearly labeled mock analysis.
    
    **Future Phases** will implement:
    - Real multilingual speech-to-text transcription
    - Audio perception and feature extraction
    - Evidence detection agents
    - Knowledge graph integration
    - Advanced fraud detection models
    
    ### Security & Privacy
    
    ⚠️ **Important:** Call recordings may contain sensitive personal information.
    
    - Files are validated and stored securely
    - Server-generated filenames prevent path traversal
    - No execution of uploaded content
    - **Phase 1 Limitations:** No authentication, no encryption at rest, not production-ready
    
    ### Support
    
    For documentation and setup instructions, see the project README.
    """)
    
    st.divider()
    
    st.caption("Copyright © 2026 VISHWAS Team. All rights reserved.")

# Footer
st.divider()
st.caption(f"Connected to: {API_BASE_URL}")
