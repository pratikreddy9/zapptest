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

# Function to preprocess and normalize text
def preprocess_text(text):
    """Normalize text by lowercasing, stripping, and removing special characters."""
    return re.sub(r'[^a-zA-Z0-9\s]', '', text.strip().lower())

# Function to combine keywords and skills into a unified list
def combine_keywords_and_skills(keywords, skills):
    """Combine keywords and skills into a single list after preprocessing."""
    combined = keywords + [skill.get("skillName", "") for skill in skills if skill.get("skillName")]
    return [preprocess_text(item) for item in combined if item]

# Function to find matches between two lists
def find_matches(jd_terms, resume_terms):
    """Find exact and fuzzy matches between job description and resume terms."""
    matches = []
    for term in jd_terms:
        if term in resume_terms or any(fuzz.ratio(term, rt) >= 80 for rt in resume_terms):
            matches.append(term)
    return matches

# Function to calculate match percentages and details
def calculate_match_percentage(jd_terms, num_candidates=10):
    """Match resumes to job descriptions using combined keywords and skills."""
    results = []
    resumes = resume_collection.find().limit(num_candidates)

    for resume in resumes:
        # Combine resume keywords and skills
        resume_keywords = resume.get("keywords", [])
        resume_skills = resume.get("skills", [])
        resume_combined = combine_keywords_and_skills(resume_keywords, resume_skills)

        # Find matches
        matching_terms = find_matches(jd_terms, resume_combined)
        match_count = len(matching_terms)
        total_terms = len(jd_terms)
        match_percentage = round((match_count / total_terms) * 100, 2) if total_terms > 0 else 0

        results.append({
            "Resume ID": resume.get("resumeId"),
            "Name": resume.get("name", "N/A"),
            "Match Percentage": match_percentage,
            "Matching Terms": matching_terms
        })

    # Return sorted results by match percentage
    return sorted(results, key=lambda x: x["Match Percentage"], reverse=True)

# Function to calculate match percentages using cosine similarity
def find_top_matches(jd_embedding, num_candidates=10):
    results = []
    resumes = resume_collection.find().limit(num_candidates)

    for resume in resumes:
        resume_embedding = resume.get("embedding")
        if not resume_embedding:
            continue

        # Cosine similarity calculation
        dot_product = sum(a * b for a, b in zip(jd_embedding, resume_embedding))
        magnitude_jd = sum(a * a for a in jd_embedding) ** 0.5
        magnitude_resume = sum(b * b for b in resume_embedding) ** 0.5
        if magnitude_jd == 0 or magnitude_resume == 0:
            continue
        similarity_score = dot_product / (magnitude_jd * magnitude_resume)

        # Convert similarity score to match percentage
        match_percentage = round(similarity_score * 100, 2)

        results.append({
            "Resume ID": resume.get("resumeId"),
            "Name": resume.get("name", "N/A"),
            "Match Percentage (Vector)": match_percentage
        })

    # Return sorted results by match percentage in descending order
    return sorted(results, key=lambda x: x["Match Percentage (Vector)"], reverse=True)

# Function to display detailed resume information
def display_resume_details(resume_id):
    resume = resume_collection.find_one({"resumeId": resume_id})
    if not resume:
        st.warning("Resume details not found!")
        return

    st.markdown("<div class='section-heading'>Personal Information</div>", unsafe_allow_html=True)
    st.write(f"**Name:** {resume.get('name', 'N/A')}")
    st.write(f"**Email:** {resume.get('email', 'N/A')}")
    st.write(f"**Contact No:** {resume.get('contactNo', 'N/A')}")
    st.write(f"**Address:** {resume.get('address', 'N/A')}")
    st.markdown("---")

# Main application logic
def main():
    st.markdown("<div class='metrics-container'>", unsafe_allow_html=True)

    total_resumes = resume_collection.count_documents({})
    total_jds = jd_collection.count_documents({})
    col1, col2 = st.columns(2)

    with col1:
        st.metric(label="Total Resumes", value=total_resumes)
    with col2:
        st.metric(label="Total Job Descriptions", value=total_jds)

    st.markdown("</div>", unsafe_allow_html=True)

    # Search by Resume ID
    st.markdown("<div class='section-heading'>Search Candidate by Resume ID</div>", unsafe_allow_html=True)
    search_id = st.text_input("Enter Resume ID:")
    if st.button("Search"):
        if search_id.strip():
            display_resume_details(search_id)
        else:
            st.warning("Please enter a valid Resume ID.")

    st.markdown("<div class='section-heading'>Select Job Description for Matching</div>", unsafe_allow_html=True)
    jds = list(jd_collection.find())
    jd_mapping = {jd.get("jobDescription", "N/A"): jd.get("jobId", "N/A") for jd in jds}
    selected_jd_description = st.selectbox("Select a Job Description:", list(jd_mapping.keys()))

    if selected_jd_description:
        selected_jd_id = jd_mapping[selected_jd_description]
        selected_jd = next(jd for jd in jds if jd.get("jobId") == selected_jd_id)

        # Combine JD keywords and skills into a unified list
        jd_keywords = selected_jd.get("structured_query", {}).get("keywords", [])
        jd_skills = selected_jd.get("skills", [])
        jd_combined = combine_keywords_and_skills(jd_keywords, jd_skills)

        jd_embedding = selected_jd.get("embedding")

        st.write(f"**Job Description ID:** {selected_jd_id}")
        st.write(f"**Job Description:** {selected_jd_description}")

        # Combined Matching
        st.subheader("Top Matches (Combined Keywords and Skills)")
        matches = calculate_match_percentage(jd_combined)
        if matches:
            match_df = pd.DataFrame(matches).astype(str)
            st.dataframe(match_df, use_container_width=True, height=300)
        else:
            st.info("No matching resumes found.")

        # Vector Matching
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
    load_css()
    main()
