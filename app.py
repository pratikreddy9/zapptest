import streamlit as st
import pandas as pd
from pymongo import MongoClient
import requests

# MongoDB connection details
mongo_uri = st.secrets["mongo"]["uri"]
client = MongoClient(mongo_uri)

# Access database and collections
db = client["resumes_database"]
resume_collection = db["resumes"]
jd_collection = db["job_description"]

# Lambda function URL for JD processing
lambda_url = "https://ljlj3twvuk.execute-api.ap-south-1.amazonaws.com/default/getJobDescriptionVector"

# Set Streamlit page config for wider layout
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
        .styled-table {
            border-collapse: collapse;
            width: 100%;
            overflow-x: auto;
        }
        .styled-table th, .styled-table td {
            text-align: left;
            padding: 8px;
        }
        .styled-table th {
            background-color: #4CAF50;
            color: white;
        }
        .styled-table tr:nth-child(even) {
            background-color: #f2f2f2;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

# Function to find top matches using embeddings
def find_top_matches(jd_embedding, num_candidates=10):
    results = []
    resumes = resume_collection.find().limit(num_candidates)

    for resume in resumes:
        resume_embedding = resume.get("embedding")
        if not resume_embedding:
            continue

        similarity_score = sum(
            a * b for a, b in zip(jd_embedding, resume_embedding)
        ) / (sum(a * a for a in jd_embedding) ** 0.5 * sum(b * b for b in resume_embedding) ** 0.5)
        similarity_score = round(similarity_score * 10, 4)

        results.append({
            "Resume ID": resume.get("resumeId"),
            "Name": resume.get("name"),
            "Similarity Score": similarity_score
        })

    return sorted(results, key=lambda x: x["Similarity Score"], reverse=True)

# Function to display detailed resume data
def display_resume_details(resume_id):
    resume = resume_collection.find_one({"resumeId": resume_id})
    if resume:
        filtered_data = {
            "Resume ID": resume.get("resumeId"),
            "Name": resume.get("name"),
            "Email": resume.get("email"),
            "Contact No": resume.get("contactNo"),
            "Address": resume.get("address"),
            "Educational Qualifications": resume.get("educationalQualifications"),
            "Job Experiences": resume.get("jobExperiences"),
            "Keywords": resume.get("keywords"),
            "Skills": resume.get("skills"),
        }
        st.json(filtered_data)
    else:
        st.warning("Resume not found!")

# New Feature: Natural Language JD Search
def natural_language_jd_search():
    st.markdown("<div class='section-heading'>Natural Language JD Search</div>", unsafe_allow_html=True)
    num_candidates = st.number_input(
        "Enter the Number of Resumes to Fetch for JD Search",
        min_value=1,
        max_value=100,
        value=10,
        step=1
    )
    jd_input = st.text_area("Paste a Job Description (JD) in natural language:")
    if st.button("Find Similar Resumes"):
        if not jd_input.strip():
            st.error("Please provide a valid Job Description.")
            return
        try:
            # Post JD to Lambda function
            response = requests.post(lambda_url, json={"jobDescription": jd_input})
            if response.status_code == 200:
                lambda_response = response.json()
                jd_id = lambda_response.get("jobDescriptionId")
                jd_embedding = jd_collection.find_one({"jobDescriptionId": jd_id}).get("embedding")

                # Find matching resumes
                st.info("Finding matching resumes...")
                matches = find_top_matches(jd_embedding, num_candidates=num_candidates)

                # Display results
                if matches:
                    st.subheader("Top Matching Resumes")
                    match_df = pd.DataFrame(matches)
                    st.dataframe(match_df, use_container_width=True)
                    selected_name = st.selectbox("Select a Resume to View Details:", [m["Name"] for m in matches])
                    if selected_name:
                        selected_resume_id = next(m["Resume ID"] for m in matches if m["Name"] == selected_name)
                        display_resume_details(selected_resume_id)
                else:
                    st.info("No matching resumes found.")
            else:
                st.error(f"Lambda error: {response.json()}")
        except Exception as e:
            st.error(f"Error: {e}")

# Main app functionality
def main():
    # Display metrics at the top
    st.markdown("<div class='metrics-container'>", unsafe_allow_html=True)
    total_resumes = resume_collection.count_documents({})
    total_jds = jd_collection.count_documents({})
    col1, col2 = st.columns(2)
    with col1:
        st.metric(label="Total Resumes", value=total_resumes)
    with col2:
        st.metric(label="Total Job Descriptions", value=total_jds)
    st.markdown("</div>", unsafe_allow_html=True)

    # Natural Language JD Search
    natural_language_jd_search()

    # Original Selected JD Workflow
    st.markdown("<div class='section-heading'>Selected Job Description</div>", unsafe_allow_html=True)
    col1, col2 = st.columns([1, 2])
    with col1:
        num_resumes_to_fetch = st.number_input(
            "Enter the Number of Resumes to Fetch", min_value=1, max_value=total_resumes, value=10, step=1
        )
    with col2:
        jds = list(jd_collection.find())
        jd_options = {jd.get("jobDescriptionId", "N/A"): jd for jd in jds}
        selected_jd_id = st.selectbox("Select a Job Description:", list(jd_options.keys()))

    if jd_options and selected_jd_id:
        selected_jd = jd_options[selected_jd_id]
        st.write(f"**Job Description ID:** {selected_jd_id}")
        st.write(f"**Query:** {selected_jd.get('query', 'N/A')}")

        jd_embedding = selected_jd.get("embedding")
        if jd_embedding:
            matches = find_top_matches(jd_embedding, num_candidates=num_resumes_to_fetch)
            if matches:
                st.subheader("Top Matches")
                match_df = pd.DataFrame(matches[:num_resumes_to_fetch])
                st.dataframe(match_df, use_container_width=True, height=300)
                names_to_ids = {match["Name"]: match["Resume ID"] for match in matches[:num_resumes_to_fetch]}
                selected_name = st.selectbox("Select a Resume to View Details:", list(names_to_ids.keys()))
                if selected_name:
                    st.subheader("Resume Details")
                    display_resume_details(names_to_ids[selected_name])
            else:
                st.info("No matching resumes found.")
        else:
            st.error("Embedding not found for the selected JD.")

    # Commented Resumes Table
    # st.header("All Resumes")
    # resumes = resume_collection.find()
    # resumes_data = [{"Resume ID": resume.get("resumeId"), "Name": resume.get("name")} for resume in resumes]
    # resumes_df = pd.DataFrame(resumes_data)
    # st.dataframe(resumes_df, use_container_width=True, height=400)

    st.header("All Job Descriptions")
    jd_data = [{"JD ID": jd.get("jobDescriptionId"), "Query": jd.get("query", "N/A")} for jd in jds]
    jd_df = pd.DataFrame(jd_data)
    st.dataframe(jd_df, use_container_width=True, height=200)

if __name__ == "__main__":
    load_css()
    main()
