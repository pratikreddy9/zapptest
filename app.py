import re
from rapidfuzz import fuzz

def preprocess_keyword(keyword):
    """Preprocess a keyword by normalizing its format."""
    keyword = keyword.casefold().strip()  # Lowercase and strip spaces
    keyword = re.sub(r'[^\w\s]', '', keyword)  # Remove special characters
    return ' '.join(sorted(keyword.split()))  # Sort multi-word phrases

def fuzzy_match(keyword, target_keywords, threshold=80):
    """Perform fuzzy matching with a similarity threshold."""
    return any(fuzz.ratio(keyword, tk) >= threshold for tk in target_keywords)

def find_keyword_matches(jd_keywords, num_candidates=10, keyword_weight=0.7, vector_weight=0.3):
    """Match resumes to job descriptions using keywords and vector similarity."""
    results = []
    resumes = resume_collection.find().limit(num_candidates)

    # Preprocess JD keywords
    jd_keywords_normalized = [preprocess_keyword(keyword) for keyword in jd_keywords]

    for resume in resumes:
        resume_keywords = resume.get("keywords", [])
        if not resume_keywords:
            continue

        # Preprocess resume keywords
        resume_keywords_normalized = [preprocess_keyword(keyword) for keyword in resume_keywords]

        # Exact match and fuzzy match
        matching_keywords = [
            keyword for keyword in jd_keywords_normalized
            if any(preprocess_keyword(keyword) == rk or fuzzy_match(keyword, [rk]) for rk in resume_keywords_normalized)
        ]

        match_count = len(matching_keywords)
        total_keywords = len(jd_keywords_normalized)
        if total_keywords == 0:
            continue
        match_percentage = round((match_count / total_keywords) * 100, 2)

        # Example: Combine with vector similarity score (mocked here for demo)
        vector_score = 85  # Placeholder value for vector similarity
        final_score = (match_percentage * keyword_weight) + (vector_score * vector_weight)

        results.append({
            "Resume ID": resume.get("resumeId"),
            "Name": resume.get("name", "N/A"),
            "Match Percentage (Keywords)": match_percentage,
            "Final Score": round(final_score, 2),
            "Matching Keywords": matching_keywords
        })

    # Return sorted results by final score
    return sorted(results, key=lambda x: x["Final Score"], reverse=True)
