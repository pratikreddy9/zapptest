import streamlit as st
import pandas as pd
from pymongo import MongoClient
import os

# Disable Streamlit's file watcher to avoid inotify limit issues
os.environ["STREAMLIT_SERVER_FILE_WATCHER_TYPE"] = "none"

# MongoDB connection details
mongo_uri = st.secrets["mongo"]["uri"]
client = MongoClient(mongo_uri)

# Accessing the database and collections
db = client["resumes_database"]
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

def find_top_matches_all_resumes(jd_embedding, num_candidates=50):
    """Find top closest matches using vector similarity."""
    results = []
    seen_keys = set()

    # Fetch all resumes from the collection
    all_resumes = resume_collection.find()

    for resume in all_resumes:
        # Create a unique key based on email and phone
        key = f"{resume.get('email')}_{resume.get('contactNo')}"

        # Skip duplicates based on key
        if key in seen_keys:
            continue
        seen_keys.add(key)

        # Get resume embedding
        resume_embedding = resume.get("embedding")
        if not resume_embedding:
            continue

        # Calculate cosine similarity
        dot_product = sum(a * b for a, b in zip(jd_embedding, resume_embedding))
        magnitude_jd = sum(a * a for a in jd_embedding) ** 0.5
        magnitude_resume = sum(b * b for b in resume_embedding) ** 0.5
        if magnitude_jd == 0 or magnitude_resume == 0:
            continue
        similarity_score = dot_product / (magnitude_jd * magnitude_resume)

        # Add fields for results
        skills = ", ".join(resume.get("keywords") or [])
        job_experiences = [
            f"{job.get('title', 'N/A')} at {job.get('companyName', 'N/A')}" 
            for job in resume.get("jobExperiences") or []
        ]
        educational_qualifications = [
            f"{edu.get('degree', 'N/A')} in {edu.get('field', 'N/A')}" 
            for edu in resume.get("educationalQualifications") or []
        ]

        results.append({
            "Resume ID": resume.get("resumeId"),
            "Name": resume.get("name", "N/A"),
            "Match Percentage (Vector)": round(similarity_score * 100, 2),
            "Skills": skills,
            "Job Experiences": "; ".join(job_experiences),
            "Educational Qualifications": "; ".join(educational_qualifications),
        })

    # Sort results by similarity and return top N
    return sorted(results, key=lambda x: x["Match Percentage (Vector)"], reverse=True)[:num_candidates]

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

    st.markdown("<div class='section-heading'>Select Job Description for Matching</div>", unsafe_allow_html=True)
    jds = list(jd_collection.find())
    jd_mapping = {jd.get("jobDescription", "N/A"): jd.get("jobId", "N/A") for jd in jds}
    selected_jd_description = st.selectbox("Select a Job Description:", list(jd_mapping.keys()))

    if selected_jd_description:
        selected_jd_id = jd_mapping[selected_jd_description]
        selected_jd = next(jd for jd in jds if jd.get("jobId") == selected_jd_id)
        jd_embedding = selected_jd.get("embedding")

        st.write(f"**Job Description ID:** {selected_jd_id}")
        st.write(f"**Job Description:** {selected_jd_description}")

        if jd_embedding:
            st.subheader("Top 50 Closest Resumes")
            top_matches = find_top_matches_all_resumes(jd_embedding, num_candidates=50)
            if top_matches:
                top_matches_df = pd.DataFrame(top_matches).astype(str)
                st.dataframe(top_matches_df, use_container_width=True, height=400)
            else:
                st.info("No matching resumes found.")
        else:
            st.error("Embedding not found for the selected JD.")

if __name__ == "__main__":
    main()
