import streamlit as st
import pandas as pd
from pymongo import MongoClient
import requests
import re
from rapidfuzz import fuzz
import os

# Disable Streamlit's file watcher to avoid inotify limit issues
os.environ["STREAMLIT_SERVER_FILE_WATCHER_TYPE"] = "none"

# MongoDB connection details
mongo_uri = st.secrets["mongo"]["uri"]
client = MongoClient(mongo_uri)

# Accessing the database and collections
db = client["resumes_database"]
resume_collection = db["resumes"]  # Collection for resumes
jd_collection = db["job_description"]  # Collection for job descriptions

# Lambda function URL for processing job descriptions
lambda_url = "https://ljlj3twvuk.execute-api.ap-south-1.amazonaws.com/default/getJobDescriptionVector"

# Set Streamlit page configuration for a wider layout
st.set_page_config(layout="wide")

# Load custom CSS for consistent styling
def load_css():
    css = """
    <style>
    body {
        font-family: Arial, sans-serif;
    }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)

# Preprocess keywords
def preprocess_keyword(keyword):
    return ' '.join(sorted(keyword.split()))

# Perform fuzzy matching with a similarity threshold
def fuzzy_match(keyword, target_keywords, threshold=80):
    return any(fuzz.ratio(keyword, tk) >= threshold for tk in target_keywords)

# Find duplicate resumes
def find_duplicate_resumes():
    duplicates = []
    seen = {}
    for resume in resume_collection.find():
        resume_data = tuple(resume.items())
        if resume_data in seen:
            duplicates.append(resume)
        else:
            seen[resume_data] = True
    total_duplicates = len(duplicates)
    return total_duplicates

# Find keyword matches
def find_keyword_matches(jd_keywords, num_candidates=100):
    results = []
    for resume in resume_collection.find():
        resume_keywords = resume.get("keywords", [])
        match_count = sum(1 for jk in jd_keywords if jk in resume_keywords)
        match_percentage = (match_count / len(jd_keywords)) * 100 if jd_keywords else 0
        results.append({
            "Resume ID": resume.get("resumeId"),
            "Match Percentage (Keywords)": match_percentage
        })
    return sorted(results, key=lambda x: x["Match Percentage (Keywords)"], reverse=True)[:num_candidates]

# Find top matches based on vector similarity
def find_top_matches(jd_embedding, num_candidates=100):
    results = []
    for resume in resume_collection.find():
        resume_embedding = resume.get("embedding")
        if resume_embedding:
            similarity = sum(1 for a, b in zip(jd_embedding, resume_embedding) if a == b)
            match_percentage = (similarity / len(jd_embedding)) * 100 if jd_embedding else 0
            results.append({
                "Resume ID": resume.get("resumeId"),
                "Match Percentage (Vector)": match_percentage
            })
    return sorted(results, key=lambda x: x["Match Percentage (Vector)"], reverse=True)[:num_candidates]

# Display resume details in a table format
def display_resume_details(resume_id):
    """Display details of the selected resume in a table format."""
    resume = resume_collection.find_one({"resumeId": resume_id})
    if resume:
        st.markdown(f"### Details for Resume ID: {resume_id}")
        resume_df = pd.DataFrame(resume.items(), columns=["Key", "Value"])
        st.table(resume_df)
    else:
        st.error("Resume details not found.")

# Main function to run the Streamlit app
def main():
    st.title("Resume Matching System")
    st.sidebar.header("Navigation")

    # Load job descriptions
    jd_list = list(jd_collection.find({}))
    jd_options = [jd["title"] for jd in jd_list if "title" in jd]

    selected_jd_title = st.sidebar.selectbox("Select Job Description", jd_options)

    if selected_jd_title:
        jd = next((jd for jd in jd_list if jd["title"] == selected_jd_title), None)
        jd_keywords = jd.get("keywords", [])
        jd_embedding = jd.get("embedding")

        st.subheader(f"Job Description: {selected_jd_title}")
        st.write(jd_keywords)

        if jd_embedding:
            # Find top matches using embeddings
            vector_matches = find_top_matches(jd_embedding)

            # Display matches
            st.markdown("## Matched Resumes")
            for match in vector_matches:
                resume_id = match["Resume ID"]
                match_percentage = match["Match Percentage (Vector)"]
                st.markdown(f"### Resume ID: {resume_id} - Match: {match_percentage}%")

                # Display detailed resume info
                display_resume_details(resume_id)
                st.markdown("---")
        else:
            st.error("Embedding not found for the selected JD.")

if __name__ == "__main__":
    load_css()
    main()
