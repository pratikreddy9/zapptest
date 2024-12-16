import streamlit as st
import pandas as pd
from pymongo import MongoClient
import re
import os
import json

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

# Function to preprocess and normalize text
def preprocess_text(text):
    """Normalize text by lowercasing, stripping, and removing special characters."""
    return re.sub(r'[^a-zA-Z0-9\s]', '', text.strip().lower())

# Function to combine keywords and skills into a unified list
def combine_keywords_and_skills(keywords, skills):
    """Combine keywords and skills into a single list after preprocessing."""
    # Debug print
    st.write("Input to combine_keywords_and_skills:")
    st.write("Keywords:", keywords)
    st.write("Skills:", skills)
    
    # Extract valid skillName values from the skills array
    valid_skills = [skill.get("skillName", "") for skill in skills if isinstance(skill, dict) and skill.get("skillName")]
    # Ensure keywords is a list
    keyword_list = keywords if isinstance(keywords, list) else []
    
    # Debug print
    st.write("Processed skills:", valid_skills)
    st.write("Processed keywords:", keyword_list)
    
    combined = keyword_list + valid_skills
    processed = [preprocess_text(item) for item in combined if item]
    
    # Debug print
    st.write("Final combined and processed list:", processed)
    
    return processed

# Function to find exact matches between two lists
def find_exact_matches(jd_terms, resume_terms):
    """Find exact matches between job description and resume terms."""
    matches = list(set(jd_terms) & set(resume_terms))
    # Debug print
    st.write("Matching terms found:", matches)
    return matches

# Function to calculate match percentages and details
def calculate_match_percentage(jd_combined, num_candidates=10):
    """Match resumes to job descriptions using combined keywords and skills."""
    st.write("JD Combined Terms for Matching:", jd_combined)
    
    results = []
    resumes = resume_collection.find().limit(num_candidates)

    for resume in resumes:
        # Debug print
        st.write(f"\nProcessing Resume ID: {resume.get('resumeId')}")
        
        # Combine resume keywords and skills
        resume_keywords = resume.get("keywords", [])
        resume_skills = resume.get("skills", [])
        
        st.write("Resume Keywords:", resume_keywords)
        st.write("Resume Skills:", resume_skills)
        
        resume_combined = combine_keywords_and_skills(resume_keywords, resume_skills)
        st.write("Combined Resume Terms:", resume_combined)

        # Find exact matches
        matching_terms = find_exact_matches(jd_combined, resume_combined)
        match_count = len(matching_terms)
        total_terms = len(jd_combined)
        match_percentage = round((match_count / total_terms) * 100, 2) if total_terms > 0 else 0

        st.write(f"Match count: {match_count}")
        st.write(f"Total terms: {total_terms}")
        st.write(f"Match percentage: {match_percentage}%")

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
    st.title("JD and Resume Matching")
    
    # Database summary
    total_resumes = resume_collection.count_documents({})
    total_jds = jd_collection.count_documents({})
    st.metric("Total Resumes", total_resumes)
    st.metric("Total Job Descriptions", total_jds)

    # Select JD for matching
    jds = list(jd_collection.find())
    
    # Debug print
    st.write("Available JDs:")
    for jd in jds:
        st.write(f"ID: {jd.get('jobId')}, Description: {jd.get('jobDescription')[:100]}...")
    
    jd_mapping = {jd.get("jobDescription", "N/A"): jd.get("jobId", "N/A") for jd in jds}
    selected_jd_description = st.selectbox("Select a Job Description:", list(jd_mapping.keys()))

    if selected_jd_description:
        selected_jd_id = jd_mapping[selected_jd_description]
        selected_jd = next(jd for jd in jds if jd.get("jobId") == selected_jd_id)

        # Debug print full JD
        st.write("Selected JD Full Content:")
        st.write(selected_jd)

        # Combine JD keywords and skills
        jd_keywords = selected_jd.get("keywords", [])
        jd_skills = selected_jd.get("skills", [])
        
        st.write("Raw JD Keywords:", jd_keywords)
        st.write("Raw JD Skills:", jd_skills)
        
        jd_combined = combine_keywords_and_skills(jd_keywords, jd_skills)

        st.write("Combined JD Keys:", jd_combined)

        if not jd_combined:
            st.error("No keywords or skills found in the selected job description!")
            return

        # Perform matching
        st.subheader("Resume Matching Results")
        matches = calculate_match_percentage(jd_combined)
        if matches:
            match_df = pd.DataFrame(matches)
            st.dataframe(match_df, use_container_width=True)
        else:
            st.info("No matching resumes found.")

if __name__ == "__main__":
    main()
