import streamlit as st
import pandas as pd
from pymongo import MongoClient
import re
from rapidfuzz import fuzz
import os
import numpy as np
from scipy.spatial.distance import cosine

# Disable Streamlit's file watcher to avoid inotify limit issues
os.environ["STREAMLIT_SERVER_FILE_WATCHER_TYPE"] = "none"

# MongoDB connection details
host = "notify.pesuacademy.com"
port = 27017
username = "admin"
password = "Ayotta@123"
auth_db = "admin"
db_name = "resumes_database"

client = MongoClient(
    host=host,
    port=port,
    username=username,
    password=password,
    authSource=auth_db
)
db = client[db_name]
resume_collection = db["resumes"]
jd_collection = db["job_description"]

# Set Streamlit page configuration for a wider layout
st.set_page_config(layout="wide")

# Load custom CSS for consistent styling
def load_css():
    st.markdown(
        """
        <style>
        .metrics-container {
            border: 2px solid #4CAF50;
            padding: 10px;
            margin-bottom: 20px;
            border-radius: 10px;
            background-color: #f9f9f9;
        }
        .section-heading {
            border-left: 5px solid #4CAF50;
            padding-left: 10px;
            margin-top: 20px;
            margin-bottom: 10px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

def preprocess_keyword(keyword):
    return ' '.join(sorted(re.sub(r'[^\w\s]', '', keyword.casefold().strip()).split()))

def fuzzy_match(keyword, target_keywords, threshold=80):
    return any(fuzz.ratio(keyword, tk) >= threshold for tk in target_keywords)

def find_keyword_matches(jd_keywords):
    """
    Match resumes to job descriptions using keywords.
    """
    total_resumes = resume_collection.count_documents({"resumeId": {"$exists": True}})
    results = []
    seen_keys = set()
    resumes = resume_collection.find({"resumeId": {"$exists": True}}).limit(total_resumes)  # Fetch all valid documents

    jd_keywords_normalized = [preprocess_keyword(keyword) for keyword in jd_keywords]

    for resume in resumes:
        key = f"{resume.get('email')}_{resume.get('contactNo')}"
        if key in seen_keys:
            continue
        seen_keys.add(key)

        resume_keywords = resume.get("keywords") or []
        resume_keywords_normalized = [preprocess_keyword(keyword) for keyword in resume_keywords]

        matching_keywords = [
            keyword for keyword in jd_keywords_normalized
            if any(preprocess_keyword(keyword) == rk or fuzzy_match(keyword, [rk]) for rk in resume_keywords_normalized)
        ]

        match_count = len(matching_keywords)
        total_keywords = len(jd_keywords_normalized)
        if total_keywords == 0:
            continue

        match_percentage = round((match_count / total_keywords) * 100, 2)

        results.append({
            "Resume ID": resume.get("resumeId"),
            "Name": resume.get("name", "N/A"),
            "Match Percentage (Keywords)": match_percentage,
            "Matching Keywords": matching_keywords,
        })

    return sorted(results, key=lambda x: x["Match Percentage (Keywords)"], reverse=True)

def find_top_matches(jd_embedding):
    """
    Find top matches using vector similarity.
    """
    total_resumes = resume_collection.count_documents({"resumeId": {"$exists": True}})
    results = []
    seen_keys = set()
    resumes = resume_collection.find({"resumeId": {"$exists": True}}).limit(total_resumes)

    for resume in resumes:
        key = f"{resume.get('email')}_{resume.get('contactNo')}"
        if key in seen_keys:
            continue
        seen_keys.add(key)

        resume_embedding = resume.get("embedding")
        if not resume_embedding:
            continue

        similarity_score = 1 - cosine(jd_embedding, resume_embedding)
        match_percentage = round(similarity_score * 100, 2)

        results.append({
            "Resume ID": resume.get("resumeId"),
            "Name": resume.get("name", "N/A"),
            "Match Percentage (Vector)": match_percentage,
        })

    return sorted(results, key=lambda x: x["Match Percentage (Vector)"], reverse=True)

def main():
    load_css()

    st.markdown("<div class='metrics-container'>", unsafe_allow_html=True)
    total_resumes = resume_collection.count_documents({"resumeId": {"$exists": True}})
    total_jds = jd_collection.count_documents({"jobId": {"$exists": True}})
    col1, col2 = st.columns(2)

    with col1:
        st.metric(label="Total Resumes", value=total_resumes)
    with col2:
        st.metric(label="Total Job Descriptions", value=total_jds)

    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='section-heading'>Select Job Description for Matching</div>", unsafe_allow_html=True)
    jds = list(jd_collection.find({"jobId": {"$exists": True}}))
    jd_mapping = {jd.get("jobDescription", "N/A"): jd.get("jobId", "N/A") for jd in jds}
    selected_jd_description = st.selectbox("Select a Job Description:", list(jd_mapping.keys()))

    if selected_jd_description:
        selected_jd_id = jd_mapping.get(selected_jd_description)
        if not selected_jd_id:
            st.error(f"Job Description ID not found for the selected description: {selected_jd_description}")
            return

        try:
            selected_jd = next(jd for jd in jds if jd.get("jobId") == selected_jd_id)
        except StopIteration:
            st.error(f"Job Description with ID {selected_jd_id} not found in the database.")
            return

        jd_keywords = selected_jd.get("structured_query", {}).get("keywords", [])
        jd_embedding = selected_jd.get("embedding")

        st.write(f"**Job Description ID:** {selected_jd_id}")
        st.write(f"**Job Description:** {selected_jd_description}")

        st.subheader("Top Matches (Keywords)")
        keyword_matches = find_keyword_matches(jd_keywords)
        if keyword_matches:
            keyword_match_df = pd.DataFrame(keyword_matches).astype(str)
            st.dataframe(keyword_match_df, use_container_width=True, height=300)
        else:
            st.info("No matching resumes found.")

        if jd_embedding:
            st.subheader("Top Matches (Vector Similarity)")
            vector_matches = find_top_matches(jd_embedding)
            if vector_matches:
                vector_match_df = pd.DataFrame(vector_matches).astype(str)
                st.dataframe(vector_match_df, use_container_width=True, height=300)
            else:
                st.info("No matching resumes found.")
        else:
            st.error("Embedding not found for the selected JD.")

if __name__ == "__main__":
    main()
