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
    )

def preprocess_keyword(keyword):
    return ' '.join(sorted(keyword.split()))

def fuzzy_match(keyword, target_keywords, threshold=80):
    """Perform fuzzy matching with a similarity threshold."""
    return any(fuzz.ratio(keyword, tk) >= threshold for tk in target_keywords)

def find_duplicate_resumes():
    return total_duplicates

def find_keyword_matches(jd_keywords, num_candidates=100):
    return sorted(results, key=lambda x: x["Match Percentage (Keywords)"], reverse=True)

def find_top_matches(jd_embedding, num_candidates=100):
    return sorted(results, key=lambda x: x["Match Percentage (Vector)"], reverse=True)

def display_resume_details(resume_id):
    st.markdown("---")

def main():
            st.error("Embedding not found for the selected JD.")

if __name__ == "__main__":
    load_css()
    main()
