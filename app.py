import streamlit as st
import pandas as pd
from pymongo import MongoClient
import requests
import re
from rapidfuzz import fuzz
import os
import json

# [Previous imports and configurations remain the same]

def display_resume_details(resume_id):
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
    # Remove embedding from display to save space
    display_resume = resume.copy()
    if 'embedding' in display_resume:
        del display_resume['embedding']
    if '_id' in display_resume:
        display_resume['_id'] = str(display_resume['_id'])  # Convert ObjectId to string
    st.json(display_resume)

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

def main():
    # [Previous main() code remains the same until the matches display]

    if selected_jd_description:
        selected_jd_id = jd_mapping[selected_jd_description]
        selected_jd = next(jd for jd in jds if jd.get("jobId") == selected_jd_id)
        jd_keywords = selected_jd.get("structured_query", {}).get("keywords", [])
        jd_embedding = selected_jd.get("embedding")

        # Display detailed JD information
        display_jd_details(selected_jd)

        st.subheader("Top Matches")
        keyword_matches = find_keyword_matches(jd_keywords)
        if keyword_matches:
            # Create expandable sections for each match
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
