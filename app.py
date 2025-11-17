"""
Lab Intelligence Chatbot - Streamlit Frontend
Natural language interface for querying lab database
"""

import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import json
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv is optional for frontend

# Page configuration
st.set_page_config(
    page_title="Lab Intelligence Chatbot",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="expanded"
)

# API configuration
default_api_url = os.getenv("API_BASE_URL", "https://niro-chat-backend.onrender.com")
API_BASE_URL = st.sidebar.text_input(
    "API Base URL",
    value=default_api_url,
    help="Backend API URL"
)

# Timeout configuration
API_TIMEOUT = st.sidebar.slider(
    "API Timeout (seconds)",
    min_value=10,
    max_value=300,
    value=int(os.getenv("API_TIMEOUT", "60")),
    help="Maximum time to wait for API response"
)

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "query_history" not in st.session_state:
    st.session_state.query_history = []


def call_api(question: str) -> dict:
    """Call the backend API"""
    try:
        response = requests.post(
            f"{API_BASE_URL}/ask",
            json={"question": question},
            timeout=API_TIMEOUT
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        st.error(f"⏱️ API Timeout: Request took longer than {API_TIMEOUT} seconds. Try increasing the timeout in the sidebar.")
        return None
    except requests.exceptions.RequestException as e:
        st.error(f"API Error: {str(e)}")
        return None


def check_api_health() -> bool:
    """Check if API is healthy"""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        return response.status_code == 200
    except:
        return False


# Main UI
st.title("🧪 Lab Intelligence Chatbot")
st.markdown("Ask questions about lab data in natural language and get instant insights!")

# Sidebar
with st.sidebar:
    st.header("⚙️ Configuration")
    
    # Health check
    if check_api_health():
        st.success("✅ API Connected")
    else:
        st.error("❌ API Not Available")
        st.info(f"Please ensure the backend is running at {API_BASE_URL}")
    
    st.divider()
    
    st.header("📊 Quick Queries")
    quick_queries = [
        "Show all abnormal tests for Lab 12 yesterday",
        "How many reports were generated this month?",
        "List abnormal parameters for male patients last week",
        "Compare abnormal test count by lab center",
        "Show test results trend over the last 30 days"
    ]
    
    for query in quick_queries:
        if st.button(query, key=f"quick_{query[:20]}", use_container_width=True):
            st.session_state.current_question = query
            st.rerun()
    
    st.divider()
    
    if st.button("🗑️ Clear Chat History"):
        st.session_state.messages = []
        st.session_state.query_history = []
        st.rerun()

# Display chat history
chat_container = st.container()
with chat_container:
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            
            # Show SQL query if available
            if message.get("sql_query"):
                with st.expander("📝 View SQL Query"):
                    st.code(message["sql_query"], language="sql")
            
            # Show data table if available
            if message.get("data") and len(message["data"]) > 0:
                df = pd.DataFrame(message["data"])
                
                # Display summary
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Rows Returned", len(df))
                with col2:
                    st.metric("Columns", len(df.columns))
                with col3:
                    if message.get("execution_time_ms"):
                        st.metric("Execution Time", f"{message['execution_time_ms']:.0f}ms")
                
                # Display table
                st.dataframe(df, use_container_width=True, height=400)
                
                # Auto-generate visualizations for time-series data
                if "bill_date" in df.columns or "date" in [col.lower() for col in df.columns]:
                    date_col = "bill_date" if "bill_date" in df.columns else [col for col in df.columns if "date" in col.lower()][0]
                    try:
                        df[date_col] = pd.to_datetime(df[date_col])
                        
                        # Count by date
                        if len(df) > 1:
                            date_counts = df.groupby(df[date_col].dt.date).size().reset_index(name="count")
                            fig = px.line(date_counts, x=date_col, y="count", 
                                        title="Trend Over Time", markers=True)
                            st.plotly_chart(fig, use_container_width=True)
                    except:
                        pass
                
                # Generate bar chart for categorical data
                categorical_cols = [col for col in df.columns 
                                  if df[col].dtype == 'object' and len(df[col].unique()) < 20]
                if categorical_cols and len(df) > 0:
                    with st.expander("📊 Visualizations"):
                        for cat_col in categorical_cols[:2]:  # Limit to 2 charts
                            try:
                                counts = df[cat_col].value_counts().head(10)
                                fig = px.bar(x=counts.index, y=counts.values,
                                           title=f"Distribution: {cat_col}",
                                           labels={"x": cat_col, "y": "Count"})
                                st.plotly_chart(fig, use_container_width=True)
                            except:
                                pass

# Chat input
if "current_question" in st.session_state:
    question = st.session_state.current_question
    del st.session_state.current_question
else:
    question = st.chat_input("Ask a question about lab data...")

if question:
    # Add user message to history
    st.session_state.messages.append({"role": "user", "content": question})
    
    # Display user message
    with st.chat_message("user"):
        st.markdown(question)
    
    # Show assistant thinking
    with st.chat_message("assistant"):
        with st.spinner("Analyzing your question and querying the database..."):
            result = call_api(question)
        
        if result:
            if result.get("success"):
                # Display answer
                st.markdown(result.get("answer", "Query executed successfully."))
                
                # Store in session
                message_data = {
                    "role": "assistant",
                    "content": result.get("answer", ""),
                    "sql_query": result.get("sql_query", ""),
                    "data": result.get("data", []),
                    "execution_time_ms": result.get("execution_time_ms", 0),
                    "row_count": result.get("row_count", 0)
                }
                st.session_state.messages.append(message_data)
                st.session_state.query_history.append({
                    "question": question,
                    "sql": result.get("sql_query", ""),
                    "timestamp": datetime.now().isoformat()
                })
                
                # Display SQL
                with st.expander("📝 View SQL Query"):
                    st.code(result.get("sql_query", ""), language="sql")
                
                # Display data
                data = result.get("data", [])
                if len(data) > 0:
                    df = pd.DataFrame(data)
                    
                    # Metrics
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Rows Returned", len(df))
                    with col2:
                        st.metric("Columns", len(df.columns))
                    with col3:
                        st.metric("Execution Time", f"{result.get('execution_time_ms', 0):.0f}ms")
                    
                    # Data table
                    st.dataframe(df, use_container_width=True, height=400)
                    
                    # Download button
                    csv = df.to_csv(index=False)
                    st.download_button(
                        label="📥 Download as CSV",
                        data=csv,
                        file_name=f"lab_query_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv"
                    )
                    
                    # Auto-visualizations
                    if "bill_date" in df.columns:
                        try:
                            df_date = df.copy()
                            df_date["bill_date"] = pd.to_datetime(df_date["bill_date"])
                            date_counts = df_date.groupby(df_date["bill_date"].dt.date).size().reset_index(name="count")
                            
                            if len(date_counts) > 1:
                                fig = px.line(date_counts, x="bill_date", y="count",
                                            title="📈 Trend Over Time", markers=True)
                                st.plotly_chart(fig, use_container_width=True)
                        except Exception as e:
                            pass
                else:
                    st.info("No data returned from query.")
            else:
                st.error(f"Query failed: {result.get('error', 'Unknown error')}")
        else:
            st.error("Failed to connect to API. Please check your configuration.")
    
    st.rerun()

# Footer
st.divider()
st.markdown(
    """
    <div style='text-align: center; color: gray;'>
        <small>Lab Intelligence Chatbot v1.0 | Built with FastAPI + Streamlit + OpenAI</small>
    </div>
    """,
    unsafe_allow_html=True
)

