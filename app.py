import streamlit as st
import pandas as pd
from pymongo import MongoClient
import re
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

# Function to find exact matches between two lists
def find_exact_matches(jd_terms, resume_terms):
    """Find exact matches between job description and resume terms."""
    return list(set(jd_terms) & set(resume_terms))

# Function to calculate match percentages and details
def calculate_match_percentage(jd_combined, num_candidates=10):
    """Match resumes to job descriptions using combined keywords and skills."""
    results = []
    resumes = resume_collection.find().limit(num_candidates)

    for resume in resumes:
        # Combine resume keywords and skills
        resume_keywords = resume.get("keywords", [])
        resume_skills = resume.get("skills", [])
        resume_combined = combine_keywords_and_skills(resume_keywords, resume_skills)

        # Find exact matches
        matching_terms = find_exact_matches(jd_combined, resume_combined)
        match_count = len(matching_terms)
        total_terms = len(jd_combined)
        match_percentage = round((match_count / total_terms) * 100, 2) if total_terms > 0 else 0

        results.append({
            "Resume ID": resume.get("resumeId"),
            "Name": resume.get("name", "N/A"),
            "Match Percentage": match_percentage,
            "Matching Terms": ', '.join(matching_terms),
            "Combined Resume Keys": ', '.join(resume_combined),
        })

    # Return sorted results by match percentage
    return sorted(results, key=lambda x: x["Match Percentage"], reverse=True)

# Main application logic
def main():
    load_css()
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
            resume = resume_collection.find_one({"resumeId": search_id})
            if resume:
                st.write(resume)
            else:
                st.warning("Resume not found!")
        else:
            st.warning("Please enter a valid Resume ID.")

    # Select Job Description for Matching
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

        # Display Combined JD Keys
        st.write(f"**Combined JD Keys:** {', '.join(jd_combined)}")

        # Calculate Match Percentages
        st.subheader("Top Matches")
        matches = calculate_match_percentage(jd_combined)
        if matches:
            match_df = pd.DataFrame(matches)
            st.dataframe(match_df, use_container_width=True, height=300)
        else:
            st.info("No matching resumes found.")

if __name__ == "__main__":
    main()
