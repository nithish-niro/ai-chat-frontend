@echo off
echo Starting Lab Intelligence Chatbot Frontend...
set PATH=%PATH%;%APPDATA%\Python\Python313\Scripts
python -m streamlit run frontend/app.py
