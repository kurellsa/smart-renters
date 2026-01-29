import streamlit as st
import requests
import pandas as pd
import json
import os

st.set_page_config(page_title="SmartPartners Rental Recon", layout="wide")

st.title("🏠 SmartPartners Reconciliation Dashboard")

# --- STEP 1: UPLOAD SECTION ---
with st.sidebar:
    st.header("Upload Documents")
    pdf1 = st.file_uploader("Upload PDF Statement 1", type=["pdf"])
    pdf2 = st.file_uploader("Upload PDF Statement 2", type=["pdf"])
    bank_json = st.file_uploader("Upload Baselane JSON", type=["json"])
    
    run_btn = st.button("🚀 Run Reconciliation", type="primary")

# --- STEP 2: RECONCILIATION LOGIC ---
if run_btn:
    if not (pdf1 and pdf2 and bank_json):
        st.error("Please upload all three files first!")
    else:
        with st.spinner("Processing with LLM and comparing data..."):
            # Prepare files for the FastAPI backend
            files = {
                "pdf1": (pdf1.name, pdf1.getvalue(), "application/pdf"),
                "pdf2": (pdf2.name, pdf2.getvalue(), "application/pdf"),
                "sheet_json": (bank_json.name, bank_json.getvalue(), "application/json"),
            }
            
            # Since Streamlit and FastAPI run in the same Space, 
            # we point to the local FastAPI port (usually 7860)
            try:
                response = requests.post("http://localhost:7860/reconcile", files=files)
                
                if response.status_code == 200:
                    data = response.json()
                    results = data.get("reconciliation_result", [])
                    
                    st.success("Reconciliation Complete!")
                    
                    # Display as a nice Table
                    df = pd.DataFrame(results)
                    st.table(df)
                    
                    # Highlighting discrepancies
                    if "Discrepancy" in df['status'].values:
                        st.warning("⚠️ Discrepancies found! Check the table above.")
                else:
                    st.error(f"Error: {response.text}")
            except Exception as e:
                st.error(f"Connection failed: {e}")

# --- STEP 3: HISTORY SECTION (From Neon) ---
st.divider()
st.subheader("Last 10 Processed Properties (from Neon DB)")
if st.button("🔄 Refresh History"):
    history_resp = requests.get("http://localhost:7860/history")
    if history_resp.status_code == 200:
        st.json(history_resp.json())