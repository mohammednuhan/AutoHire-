RESUME_EXTRACTION_SYSTEM = """
You are a resume parser. Extract every piece of information from the resume text below.
Return ONLY a JSON object. No preamble, no explanation, no markdown formatting, no backticks.
If a field is not present in the resume, use null for scalar fields or [] for array fields.
Do not infer or add information not explicitly stated in the resume.
"""

RESUME_EXTRACTION_PROMPT = """
Extract all information from this resume and return it as a JSON object with this exact structure:

{{
  "full_name": "string",
  "email": "string or null",
  "phone": "string or null",
  "location": "string or null",
  "linkedin_url": "string or null",
  "github_url": "string or null",
  "portfolio_url": "string or null",
  "summary": "string or null",
  "education": [
    {{
      "institution": "string",
      "degree": "string",
      "field": "string",
      "graduation_year": integer or null,
      "gpa": "string or null",
      "relevant_courses": []
    }}
  ],
  "experience": [
    {{
      "company": "string",
      "role": "string",
      "start_date": "YYYY-MM or 'Present'",
      "end_date": "YYYY-MM or 'Present'",
      "is_current": boolean,
      "location": "string or null",
      "description": ["bullet point 1", "bullet point 2"],
      "tech_stack": []
    }}
  ],
  "projects": [
    {{
      "name": "string",
      "description": "string",
      "tech_stack": [],
      "url": "string or null",
      "duration": "string or null"
    }}
  ],
  "skills": {{
    "languages": [],
    "frameworks": [],
    "databases": [],
    "tools": [],
    "cloud": [],
    "soft_skills": []
  }},
  "certifications": [
    {{
      "name": "string",
      "issuer": "string or null",
      "year": integer or null
    }}
  ],
  "achievements": [],
  "languages_spoken": []
}}

RESUME TEXT:
{raw_text}
"""
