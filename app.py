import streamlit as st
import pandas as pd
import numpy as np
from pymongo import MongoClient
import requests
import json

# MongoDB connection details
mongo_uri = st.secrets["mongo"]["uri"]
client = MongoClient(mongo_uri)

# Access database and collections
db = client["resumes_database"]
resume_collection = db["resumes"]
jd_collection = db["job_description"]

# Set Streamlit page config for wider layout
st.set_page_config(layout="wide")

# Custom CSS for visual enhancements
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

# Function to calculate cosine similarity
def calculate_cosine_similarity(vector1, vector2):
    vector1 = np.array(vector1)
    vector2 = np.array(vector2)
    dot_product = np.dot(vector1, vector2)
    norm_vector1 = np.linalg.norm(vector1)
    norm_vector2 = np.linalg.norm(vector2)
    if norm_vector1 == 0 or norm_vector2 == 0:
        return 0
    return dot_product / (norm_vector1 * norm_vector2)

# Function to find top matches
def find_top_matches(jd_embedding, num_candidates=10):
    results = []
    resumes = resume_collection.find().limit(num_candidates)

    for resume in resumes:
        resume_embedding = resume.get("embedding")
        if not resume_embedding:
            continue

        # Calculate cosine similarity
        similarity_score = calculate_cosine_similarity(jd_embedding, resume_embedding)

        # Normalize to a score out of 10
        similarity_score = round(similarity_score * 10, 4)

        results.append({
            "Resume ID": resume.get("resumeId"),
            "Name": resume.get("name"),
            "Similarity Score": similarity_score
        })

    # Sort results by similarity score (descending)
    results = sorted(results, key=lambda x: x["Similarity Score"], reverse=True)
    return results  # Return all matches

# Function to display detailed resume data (only 9 keys, excluding embedding)
def display_resume_details(resume_id):
    resume = resume_collection.find_one({"resumeId": resume_id})
    if resume:
        # Filter only required fields
        filtered_data = {
            "_id": str(resume.get("_id")),
            "resumeId": resume.get("resumeId"),
            "name": resume.get("name"),
            "email": resume.get("email"),
            "contactNo": resume.get("contactNo"),
            "address": resume.get("address"),
            "educationalQualifications": resume.get("educationalQualifications"),
            "jobExperiences": resume.get("jobExperiences"),
            "keywords": resume.get("keywords"),
            "skills": resume.get("skills"),
        }

        # Format educational qualifications and job experiences
        edu_qual = [
            f"{eq.get('degree', 'N/A')} in {eq.get('field', 'N/A')} ({eq.get('graduationYear', 'N/A')})"
            for eq in filtered_data.get("educationalQualifications", [])
        ]
        job_exp = [
            f"{je.get('title', 'N/A')} at {je.get('company', 'N/A')} ({je.get('duration', 'N/A')} years)"
            for je in filtered_data.get("jobExperiences", [])
        ]
        skills = [skill.get("skillName", "N/A") for skill in filtered_data.get("skills", [])]

        # Display in a clean table format
        st.table(pd.DataFrame([
            {"Key": "_id", "Value": filtered_data["_id"]},
            {"Key": "resumeId", "Value": filtered_data["resumeId"]},
            {"Key": "name", "Value": filtered_data["name"]},
            {"Key": "email", "Value": filtered_data["email"]},
            {"Key": "contactNo", "Value": filtered_data["contactNo"]},
            {"Key": "address", "Value": filtered_data["address"]},
            {"Key": "educationalQualifications", "Value": "; ".join(edu_qual)},
            {"Key": "jobExperiences", "Value": "; ".join(job_exp)},
            {"Key": "keywords", "Value": "; ".join(filtered_data.get("keywords", []))},
            {"Key": "skills", "Value": "; ".join(skills)},
        ]))
    else:
        st.warning("Resume details not found!")

# New Feature: Natural Language JD Search
def natural_language_jd_search():
    st.title("Natural Language JD Search")
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
            # Convert JD to structured JSON
            st.info("Structuring the Job Description...")
            structured_jd = format_job_description(jd_input)
            # st.json(structured_jd)  # Commented as requested

            # Create embedding for the structured JD
            st.info("Generating embedding for the structured JD...")
            structured_jd_text = json.dumps(structured_jd)
            jd_embedding = create_embedding(structured_jd_text)

            # Find top matches
            st.info("Finding matching resumes...")
            matches = find_top_matches(jd_embedding, num_candidates=num_candidates)

            # Display results
            if matches:
                st.subheader("Top Matching Resumes")
                match_df = pd.DataFrame(matches)
                st.dataframe(match_df, use_container_width=True)

                # Option to view resume details
                selected_name = st.selectbox("Select a Resume to View Details:", [m["Name"] for m in matches])
                if selected_name:
                    selected_resume_id = next(m["Resume ID"] for m in matches if m["Name"] == selected_name)
                    display_resume_details(selected_resume_id)
            else:
                st.info("No matching resumes found.")
        except ValueError as e:
            st.error(f"Error: {str(e)}")

# Helper function to create embeddings
def create_embedding(text):
    url = "https://api.openai.com/v1/embeddings"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {st.secrets['openai']['api_key']}"
    }
    data = {
        "input": text,
        "model": "text-embedding-3-large"
    }

    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        response_data = response.json()
        return response_data['data'][0]['embedding']
    else:
        raise ValueError(f"Error generating embedding: {response.json()}")

# Helper function to format JD
def format_job_description(jd_text):
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {st.secrets['openai']['api_key']}"
    }
    data = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": "Convert JD to structured JSON"},
            {"role": "user", "content": f"Please structure this JD:\n{jd_text}"}
        ]
    }

    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        return json.loads(response.json()['choices'][0]['message']['content'])
    else:
        raise ValueError(f"Error structuring JD: {response.json()}")

# Call JD search first
load_css()
natural_language_jd_search()

# Existing Main Functionality
def main():
    st.title("Resume and Job Description Matching Dashboard")

    # Metrics
    total_jds = jd_collection.count_documents({})
    total_resumes = resume_collection.count_documents({})
    st.markdown("<div class='metrics-container'>", unsafe_allow_html=True)
    st.metric(label="Total Resumes", value=total_resumes)
    st.metric(label="Total Job Descriptions", value=total_jds)
    st.markdown("</div>", unsafe_allow_html=True)

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
        st.subheader("Selected Job Description")
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
    main()
