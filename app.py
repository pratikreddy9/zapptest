import streamlit as st
import pandas as pd
from pymongo import MongoClient
import requests
import re
from rapidfuzz import fuzz
import os
import json

# Disable Streamlit's file watcher to avoid inotify limit issues
os.environ["STREAMLIT_SERVER_FILE_WATCHER_TYPE"] = "none"

# Set Streamlit page configuration for a wider layout
st.set_page_config(layout="wide")

# MongoDB connection details
mongo_uri = st.secrets["mongo"]["uri"]
client = MongoClient(mongo_uri)

# Accessing the database and collections
db = client["resumes_database"]
resume_collection = db["resumes"]  # Collection for resumes
jd_collection = db["job_description"]  # Collection for job descriptions

def load_css():
    """Load custom CSS for styling."""
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
        unsafe_allow_html=True
    )

def preprocess_keyword(keyword):
    """Preprocess a keyword by normalizing its format."""
    keyword = keyword.casefold().strip()
    keyword = re.sub(r'[^\w\s]', '', keyword)
    return ' '.join(sorted(keyword.split()))

def fuzzy_match(keyword, target_keywords, threshold=80):
    """Perform fuzzy matching with a similarity threshold."""
    return any(fuzz.ratio(keyword, tk) >= threshold for tk in target_keywords)

def find_duplicate_resumes():
    """Find duplicate resumes based on email and phone number."""
    duplicates = {}
    all_resumes = list(resume_collection.find())
    
    for resume in all_resumes:
        email = resume.get('email')
        phone = resume.get('contactNo')
        
        if email or phone:
            key = f"{email}_{phone}"
            if key in duplicates:
                duplicates[key].append(resume)
            else:
                duplicates[key] = [resume]
    
    duplicate_groups = {k: v for k, v in duplicates.items() if len(v) > 1}
    total_duplicates = sum(len(group) - 1 for group in duplicate_groups.values())
    
    return total_duplicates

def display_resume_details(resume_id):
    """Display detailed resume information."""
    resume = resume_collection.find_one({"resumeId": resume_id})
    if not resume:
        st.warning("Resume details not found!")
        return

    st.markdown("<div class='section-heading'>Resume Details</div>", unsafe_allow_html=True)
    
    # Basic Information
    st.subheader("Personal Information")
    basic_info = {
        "Resume ID": resume.get('resumeId', 'N/A'),
        "Name": resume.get('name', 'N/A'),
        "Email": resume.get('email', 'N/A'),
        "Contact": resume.get('contactNo', 'N/A'),
        "Country": resume.get('country', 'N/A'),
        "State": resume.get('state', 'N/A'),
        "Address": resume.get('address', 'N/A')
    }
    st.dataframe(pd.DataFrame([basic_info]).T, use_container_width=True)

    # Skills Section
    st.subheader("Skills")
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("Keywords")
        if resume.get('keywords'):
            keywords_df = pd.DataFrame({'Keywords': resume['keywords']})
            st.dataframe(keywords_df, use_container_width=True)
    
    with col2:
        st.write("Technical Skills")
        if resume.get('skills'):
            skills_df = pd.DataFrame({'Skills': resume['skills']})
            st.dataframe(skills_df, use_container_width=True)

    # Education
    st.subheader("Educational Qualifications")
    if resume.get('educationalQualifications'):
        education_df = pd.DataFrame(resume['educationalQualifications'])
        st.dataframe(education_df, use_container_width=True)

    # Experience
    st.subheader("Job Experiences")
    if resume.get('jobExperiences'):
        experience_df = pd.DataFrame(resume['jobExperiences'])
        st.dataframe(experience_df, use_container_width=True)

    # Display full JSON
    st.subheader("Complete Resume Data")
    display_resume = resume.copy()
    if 'embedding' in display_resume:
        del display_resume['embedding']
    if '_id' in display_resume:
        display_resume['_id'] = str(display_resume['_id'])
    st.json(display_resume)

def display_jd_details(jd):
    """Display detailed job description information."""
    st.markdown("<div class='section-heading'>Job Description Details</div>", unsafe_allow_html=True)
    
    # Basic JD Information
    st.subheader("Basic Information")
    basic_jd_info = {
        "Job ID": jd.get('jobId', 'N/A'),
        "Title": jd.get('title', 'N/A'),
        "Location": jd.get('location', 'N/A'),
        "Department": jd.get('department', 'N/A')
    }
    st.dataframe(pd.DataFrame([basic_jd_info]).T, use_container_width=True)

    # Required Skills
    st.subheader("Required Skills")
    if jd.get('structured_query', {}).get('keywords'):
        skills_df = pd.DataFrame({'Required Skills': jd['structured_query']['keywords']})
        st.dataframe(skills_df, use_container_width=True)

    # Display full JSON
    st.subheader("Complete Job Description Data")
    display_jd = jd.copy()
    if 'embedding' in display_jd:
        del display_jd['embedding']
    if '_id' in display_jd:
        display_jd['_id'] = str(display_jd['_id'])
    st.json(display_jd)

def find_keyword_matches(jd_keywords, num_candidates=10):
    """Match resumes to job descriptions using keywords."""
    results = []
    seen_keys = set()
    resumes = resume_collection.find().limit(num_candidates * 2)

    jd_keywords_normalized = [preprocess_keyword(keyword) for keyword in jd_keywords]

    for resume in resumes:
        key = f"{resume.get('email')}_{resume.get('contactNo')}"
        if key in seen_keys:
            continue
        seen_keys.add(key)

        resume_keywords = resume.get("keywords", [])
        resume_skills = resume.get("skills", [])
        all_skills = resume_keywords + resume_skills

        if not all_skills:
            continue

        resume_keywords_normalized = [preprocess_keyword(keyword) for keyword in all_skills]
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
            "Match Percentage": match_percentage,
            "Matching Keywords": matching_keywords,
            "Keywords": resume_keywords,
            "Skills": resume_skills,
            "Education": resume.get("educationalQualifications", "N/A"),
            "Experience": resume.get("jobExperiences", "N/A")
        })

        if len(results) >= num_candidates:
            break

    return sorted(results, key=lambda x: x["Match Percentage"], reverse=True)

def find_top_matches(jd_embedding, num_candidates=10):
    """Find top matches using vector similarity."""
    results = []
    seen_keys = set()
    resumes = resume_collection.find().limit(num_candidates * 2)

    for resume in resumes:
        key = f"{resume.get('email')}_{resume.get('contactNo')}"
        if key in seen_keys:
            continue
        seen_keys.add(key)

        resume_embedding = resume.get("embedding")
        if not resume_embedding:
            continue

        dot_product = sum(a * b for a, b in zip(jd_embedding, resume_embedding))
        magnitude_jd = sum(a * a for a in jd_embedding) ** 0.5
        magnitude_resume = sum(b * b for b in resume_embedding) ** 0.5
        
        if magnitude_jd == 0 or magnitude_resume == 0:
            continue
            
        similarity_score = dot_product / (magnitude_jd * magnitude_resume)
        match_percentage = round(similarity_score * 100, 2)

        results.append({
            "Resume ID": resume.get("resumeId"),
            "Name": resume.get("name", "N/A"),
            "Match Percentage (Vector)": match_percentage
        })

        if len(results) >= num_candidates:
            break

    return sorted(results, key=lambda x: x["Match Percentage (Vector)"], reverse=True)

def main():
    """Main application function."""
    st.markdown("<div class='metrics-container'>", unsafe_allow_html=True)

    total_resumes = resume_collection.count_documents({})
    total_jds = jd_collection.count_documents({})
    col1, col2 = st.columns(2)

    with col1:
        st.metric(label="Total Resumes", value=total_resumes)
    with col2:
        st.metric(label="Total Job Descriptions", value=total_jds)

    total_duplicates = find_duplicate_resumes()
    st.write(f"Number of duplicate resumes found: {total_duplicates}")

    st.markdown("</div>", unsafe_allow_html=True)

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
        jd_keywords = selected_jd.get("structured_query", {}).get("keywords", [])
        jd_embedding = selected_jd.get("embedding")

        display_jd_details(selected_jd)

        st.subheader("Top Matches")
        keyword_matches = find_keyword_matches(jd_keywords)
        if keyword_matches:
            for idx, match in enumerate(keyword_matches, 1):
                with st.expander(f"Match {idx}: {match['Name']} - {match['Match Percentage']}% Match"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write("**Basic Information**")
                        st.write(f"Resume ID: {match['Resume ID']}")
                        st.write(f"Name: {match['Name']}")
                        st.write(f"Match Percentage: {match['Match Percentage']}%")
                    
                    with col2:
                        st.write("**Matching Keywords**")
                        st.write(match['Matching Keywords'])
                    
                    st.write("**All Keywords**")
                    st.write(match['Keywords'])
                    
                    st.write("**Technical Skills**")
                    st.write(match['Skills'])
                    
                    if st.button(f"View Complete Details for {match['Name']}", key=f"view_{match['Resume ID']}"):
                        display_resume_details(match['Resume ID'])
        else:
            st.info("No matching resumes found.")

        if jd_embedding:
            st.subheader("Vector Similarity Matches")
            vector_matches = find_top_matches(jd_embedding)
            if vector_matches:
                vector_match_df = pd.DataFrame(vector_matches).astype(str)
                st.dataframe(vector_match_df, use_container_width=True)
            else:
                st.info("No vector matches found.")
        else:
            st.error("Embedding not found for the selected JD.")

if __name__ == "__main__":
    load_css()
    main()
