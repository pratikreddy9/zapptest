import streamlit as st
import pandas as pd
from pymongo import MongoClient
import requests

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
        .tile {
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 15px;
            margin: 10px;
            background-color: #f9f9f9;
            box-shadow: 0px 2px 5px rgba(0, 0, 0, 0.1);
        }
        .tile:hover {
            box-shadow: 0px 4px 10px rgba(0, 0, 0, 0.2);
        }
        .tile-heading {
            font-size: 18px;
            font-weight: bold;
            margin-bottom: 10px;
            color: #333;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

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

# Function to calculate keyword match percentage
def find_keyword_matches(jd_keywords, num_candidates=10):
    results = []
    resumes = resume_collection.find().limit(num_candidates)

    for resume in resumes:
        resume_keywords = resume.get("keywords", [])
        if not resume_keywords:
            continue

        # Calculate keyword matches
        matching_keywords = set(jd_keywords).intersection(set(resume_keywords))
        match_count = len(matching_keywords)
        total_keywords = len(jd_keywords)
        if total_keywords == 0:
            continue
        match_percentage = round((match_count / total_keywords) * 100, 2)

        results.append({
            "Resume ID": resume.get("resumeId"),
            "Name": resume.get("name", "N/A"),
            "Match Percentage (Keywords)": match_percentage,
            "Matching Keywords": list(matching_keywords)
        })

    # Return sorted results by match percentage
    return sorted(results, key=lambda x: x["Match Percentage (Keywords)"], reverse=True)

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

    edu_qual = [
        f"{eq.get('degree', 'N/A')} in {eq.get('field', 'N/A')} ({eq.get('graduationYear', 'N/A')})"
        for eq in resume.get("educationalQualifications", [])
    ]

    job_exp = [
        f"{je.get('title', 'N/A')} at {je.get('company', 'N/A')} ({je.get('duration', 'N/A')} years)"
        for je in resume.get("jobExperiences", [])
    ]

    skills = [skill.get("skillName", "N/A") for skill in resume.get("skills", [])]
    keywords = resume.get("keywords", [])

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("<div class='tile'><div class='tile-heading'>Educational Qualifications</div>", unsafe_allow_html=True)
        if edu_qual:
            for edu in edu_qual:
                st.write(f"- {edu}")
        else:
            st.write("No educational qualifications available.")
        st.markdown("</div>", unsafe_allow_html=True)

    with col2:
        st.markdown("<div class='tile'><div class='tile-heading'>Job Experiences</div>", unsafe_allow_html=True)
        if job_exp:
            for job in job_exp:
                st.write(f"- {job}")
        else:
            st.write("No job experiences available.")
        st.markdown("</div>", unsafe_allow_html=True)

    with col1:
        st.markdown("<div class='tile'><div class='tile-heading'>Skills</div>", unsafe_allow_html=True)
        if skills:
            st.write(", ".join(skills))
        else:
            st.write("No skills available.")
        st.markdown("</div>", unsafe_allow_html=True)

    with col2:
        st.markdown("<div class='tile'><div class='tile-heading'>Keywords</div>", unsafe_allow_html=True)
        if keywords:
            st.write(", ".join(keywords))
        else:
            st.write("No keywords available.")
        st.markdown("</div>", unsafe_allow_html=True)

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

    jd_input_area()
    display_match_results()

def jd_input_area():
    st.markdown("<div class='section-heading'>Add a Job Description</div>", unsafe_allow_html=True)
    jd_id_input = st.text_input("Enter Job ID", placeholder="e.g., 1234abcd-5678-efgh-9101-ijklmnopqrs")
    jd_input = st.text_area("Paste a Job Description (JD) in natural language:")

    if st.button("Store Job Description"):
        if not jd_id_input.strip():
            st.error("Please provide a valid Job ID.")
            return
        if not jd_input.strip():
            st.error("Please provide a valid Job Description.")
            return

        payload = {
            "jobId": jd_id_input.strip(),
            "jobDescription": jd_input.strip()
        }

        try:
            response = requests.post(lambda_url, json=payload)
            if response.status_code == 200:
                st.success(f"Job Description stored successfully! Job ID: {jd_id_input}")
            else:
                st.error(f"Lambda error: {response.json()}")
        except Exception as e:
            st.error(f"Error: {e}")

def display_match_results():
    st.markdown("<div class='section-heading'>Select Job Description for Matching</div>", unsafe_allow_html=True)
    jds = list(jd_collection.find())
    jd_mapping = {jd.get("jobDescription", "N/A"): jd.get("jobId", "N/A") for jd in jds}
    selected_jd_description = st.selectbox("Select a Job Description:", list(jd_mapping.keys()))

    if selected_jd_description:
        selected_jd_id = jd_mapping[selected_jd_description]
        selected_jd = next(jd for jd in jds if jd.get("jobId") == selected_jd_id)
        jd_keywords = selected_jd.get("keywords", [])
        jd_embedding = selected_jd.get("embedding")

        st.write(f"**Job Description ID:** {selected_jd_id}")
        st.write(f"**Job Description:** {selected_jd_description}")

        # Keyword Matching
        st.subheader("Top Matches (Keywords)")
        keyword_matches = find_keyword_matches(jd_keywords)
        if keyword_matches:
            keyword_match_df = pd.DataFrame(keyword_matches).astype(str)
            st.dataframe(keyword_match_df, use_container_width=True, height=300)
        else:
            st.info("No matching resumes found for keywords.")

        # Vector Matching
        if jd_embedding:
            st.subheader("Top Matches (Vector Similarity)")
            vector_matches = find_top_matches(jd_embedding)
            if vector_matches:
                vector_match_df = pd.DataFrame(vector_matches).astype(str)
                st.dataframe(vector_match_df, use_container_width=True, height=300)
            else:
                st.info("No matching resumes found for vector similarity.")
        else:
            st.error("Embedding not found for the selected JD.")

if __name__ == "__main__":
    load_css()
    main()
