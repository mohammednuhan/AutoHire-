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

JOB_SCORING_SYSTEM = """
You are evaluating how well a job matches a candidate's profile.
Return ONLY a JSON object. No preamble, no markdown, no backticks.
Be strict and honest - do not inflate scores. A realistic score matters more than an encouraging one.
"""

JOB_SCORING_PROMPT = """
Score this job against the candidate profile on a scale of 0-100.

CANDIDATE PROFILE (static - always the same for this user):
Name: {full_name}
Skills: {skills}
Experience: {experience}
Education: {education}
Preferred roles: {target_roles}
Preferred locations: {preferred_locations}
Work type preference: {work_type}

JOB TO SCORE (dynamic):
Title: {title}
Company: {company}
Location: {location}
Work type: {job_work_type}
Description: {description}

Scoring weights:
- Technical skills match (40%): What % of required skills does candidate have?
- Experience level fit (25%): Does their experience level match what's asked?
- Domain/industry match (15%): Is this the type of work they've done or want?
- Location/work type match (10%): Does location and remote/onsite preference align?
- Growth potential (10%): Would this role advance their career meaningfully?

Return ONLY this JSON:
{{
  "total_score": integer 0-100,
  "technical_match": integer 0-100,
  "experience_match": integer 0-100,
  "domain_match": integer 0-100,
  "location_match": integer 0-100,
  "growth_potential": integer 0-100,
  "missing_skills": ["skill1", "skill2"],
  "matching_skills": ["skill1", "skill2"],
  "score_explanation": "2-3 sentence plain English explanation of why this score",
  "recommendation": "APPLY" or "SKIP" or "STRETCH"
}}
"""

COMPANY_RESEARCH_SYSTEM = "You are a company research assistant. Return ONLY JSON. No markdown."

COMPANY_RESEARCH_PROMPT = """
Provide a brief summary of {company_name} for use in a job application cover letter.
Return ONLY this JSON:
{{
  "known": true or false,  (false if you have no reliable info about this company)
  "industry": "string",
  "what_they_do": "1 sentence max - what product/service",
  "culture_signals": "1 sentence max - work culture, values, mission",
  "why_interesting": "1 sentence max - why a candidate would want to work here"
}}
If 'known' is false, set all other fields to null.
"""

COVER_LETTER_SYSTEM = """
You are writing a cover letter for a job application.
Return ONLY the cover letter text. No subject line, no greeting instructions, no metadata.
"""

COVER_LETTER_PROMPT = """
Write a cover letter for this candidate applying to this job.

STRICT RULES - VIOLATION MEANS FAILURE:
1. EVERY claim you make must be directly supported by something in the candidate's profile below
2. Do NOT invent achievements, metrics, technologies, or experiences not in the profile
3. Do NOT use these banned phrases: "passionate about", "quick learner", "great fit", "I am writing to apply for", "team player", "go-getter", "results-driven", "synergy"
4. Do NOT open with "I" as the first word
5. First person, active voice, natural professional tone
6. Exactly 3 paragraphs:
   - Paragraph 1 (2-3 sentences): What draws you to this specific company and role - use the company_research below. Make it specific, not generic.
   - Paragraph 2 (3-4 sentences): Specific evidence from your background (projects, experience, skills) that matches what this role needs. Name real projects and real technologies.
   - Paragraph 3 (2 sentences): Clear call to action. Express genuine interest in an interview.
7. Total word count: 200-300 words. Count carefully.

CANDIDATE PROFILE (only use information from here - nothing else):
Name: {full_name}
Skills: {skills}
Experience: {experience}
Projects: {projects}
Education: {education}

JOB DETAILS:
Title: {job_title}
Company: {job_company}
Description: {job_description}
Key requirements identified: {job_skills_required}

COMPANY CONTEXT (use this for Paragraph 1):
What they do: {company_what_they_do}
Culture/values: {company_culture_signals}
Why interesting: {company_why_interesting}

{correction_instructions}
Write the cover letter now. Return ONLY the letter text.
"""

COVER_LETTER_VALIDATION_SYSTEM = "You are a fact-checker. Return ONLY JSON. No markdown, no preamble."

COVER_LETTER_VALIDATION_PROMPT = """
A cover letter was written for a job application. Your job is to check every claim in the cover letter against the candidate's actual profile.

CANDIDATE PROFILE (the ground truth):
{full_profile}

COVER LETTER TO CHECK:
{cover_letter}

Find every claim in the cover letter and check if it is directly supported by the candidate profile above.
A claim is UNSUPPORTED if:
- It mentions a technology, skill, or tool not in the profile
- It describes an achievement not in the profile
- It quantifies something (years, percentages, numbers) not in the profile
- It describes a role or responsibility not in the profile

Return ONLY this JSON:
{{
  "all_claims_supported": true or false,
  "unsupported_claims": [
    {{"claim": "exact sentence from cover letter", "reason": "why it's unsupported"}}
  ],
  "word_count": integer
}}
"""

RESUME_TAILORING_SYSTEM = """
You are tailoring a resume for a specific job application.
CRITICAL RULES:
- You may only REORDER and REPHRASE what already exists in the profile
- You may NOT add any skill, experience, project, or achievement not already in the profile
- You may NOT invent metrics or numbers not stated in the profile
- You may NOT change dates, company names, or role titles
Return ONLY JSON.
"""

RESUME_TAILORING_PROMPT = """
Tailor this candidate's resume for the job below. Return the COMPLETE tailored profile - include everything, just reordered and rephrased.

JOB REQUIREMENTS:
Title: {job_title}
Required skills: {job_skills_required}
Key phrases from JD: {key_phrases}

ORIGINAL PROFILE (only work with what's here):
{full_profile}

Instructions:
1. Reorder skills sections: put skills that match the JD requirements FIRST
2. Rewrite project descriptions to emphasize technologies relevant to this JD (using words from the JD)
3. Rewrite experience bullet points to emphasize responsibilities relevant to this role
4. Write a 2-sentence summary/objective at the top targeting this specific role
5. Remove projects or experiences that are completely irrelevant (keep if any part is relevant)
6. Single-column layout: no tables, no graphics, no text boxes

Return the complete tailored profile as JSON in the same ResumeProfile format as input.
Every modification must be traceable to original content.
"""

APPLICATION_PLAN_SYSTEM = "You are planning a job application form filling. Return ONLY JSON."

APPLICATION_PLAN_PROMPT = """
Create a step-by-step plan to fill out the job application form at this URL.

JOB URL: {job_url}
JOB TITLE: {job_title}
COMPANY: {job_company}

CANDIDATE PROFILE (use ONLY these values when filling fields):
Name: {full_name}
Email: {email}
Phone: {phone}
Location: {location}
LinkedIn: {linkedin_url}
GitHub: {github_url}
Portfolio: {portfolio_url}
Education: {education}
Experience: {experience}
Work authorization: Eligible to work in India

COVER LETTER TEXT:
{cover_letter}

SPECIAL RULES:
- For any salary/CTC field: use value "NEEDS_HUMAN" (we always pause for human input on salary)
- For any D&I/diversity questions: use "Prefer not to answer" if available, else "NEEDS_HUMAN"
- For any field asking about visa sponsorship: "No sponsorship required"
- For any question not answerable from the profile: use "NEEDS_HUMAN"
- Cover letter text is provided separately (file or text area)
- Resume file: {resume_pdf_path} (tailored PDF)
- Do not create a final submit action. Stop when all fields are filled and the submit button is visible.

Return ONLY a JSON array of actions in order:
[
  {{"step": 1, "action": "navigate", "url": "{job_url}", "expected_state": "Application form page loaded"}},
  {{"step": 2, "action": "fill", "field_description": "First name input", "value": "{first_name}", "expected_state": "First name field shows the name"}},
  {{"step": 3, "action": "fill", "field_description": "Email address", "value": "{email}", "expected_state": "Email field populated"}},
  {{"step": 4, "action": "upload", "field_description": "Resume upload button", "file_path": "{resume_pdf_path}", "expected_state": "Resume filename visible in upload area"}},
  {{"step": 5, "action": "screenshot", "field_description": "Final form review", "expected_state": "All fields filled, submit button visible"}}
]

Action types: "navigate", "fill", "click", "select", "upload", "checkbox", "screenshot", "scroll"
"""

ACTION_VALIDATION_SYSTEM = (
    "You are checking if a browser automation action completed successfully. Return ONLY JSON."
)

ACTION_VALIDATION_PROMPT = """
A browser automation agent just performed this action: "{action_description}"
The expected result was: "{expected_state}"

Look at the screenshot carefully and determine:
1. Did the action complete successfully as expected?
2. Are there any error messages, validation failures, or warning dialogs visible?
3. Is the page in the state we'd expect after this action?
4. Are there any popups, modals, or overlays blocking the form?

Return ONLY this JSON:
{{
  "confidence": float between 0.0 and 1.0,
  "passed": true or false,
  "observation": "1 sentence: what you see in the screenshot",
  "error_detected": true or false,
  "error_text": "exact error text visible on screen, or null",
  "blocking_element": "description of any popup/modal blocking the form, or null"
}}

Confidence guide:
1.0 = Form field clearly shows the correct value, no issues visible
0.9 = Very likely correct, minor uncertainty
0.8 = Probably correct (threshold - below this -> NEEDS_HUMAN)
0.6 = Uncertain - field may not have filled correctly
0.3 = Something clearly went wrong
0.0 = Definite error - wrong page, session expired, form error visible
"""
