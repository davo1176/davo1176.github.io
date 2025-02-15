import json
import sys
import os

# Add the `src/` folder to Python's module search path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.resume_parser import ResumeParser
from src.job_parser import JobParser

class JobMatcher:
    def __init__(self, resume_path, job_desc_file):
        """Initialize the Job Matcher with resume and job descriptions"""
        self.resume_parser = ResumeParser(resume_path)
        self.job_parser = JobParser(job_desc_file)
        self.resume_data = self.resume_parser.parsed_data
        self.jobs = self.job_parser.df

    def calculate_match_score(self, job_data):
        """
        Calculate the match score based on the number of matched skills
        """
        resume_skills = set(self.resume_data["skills"].lower().split(", "))  # Convert skills to lowercase
        job_description = job_data.get("Job Description", "").lower()  # Lowercase job description

        # Count how many resume skills appear in the job description
        matched_skills = [skill for skill in resume_skills if skill in job_description]

        # Match score = (matched skills / total skills in resume) * 100
        match_percent = (len(matched_skills) / len(resume_skills)) * 100 if resume_skills else 0
        return round(match_percent, 2), matched_skills

    def find_best_matches(self, top_n=5):
        """
        Find the best job matches based on skill similarity
        """
        results = []

        for _, job_row in self.jobs.iterrows():
            job_data = job_row.to_dict()
            job_data["Job Description"] = self.job_parser.clean_html(job_data.get("Job Description", ""))
            match_score, matched_skills = self.calculate_match_score(job_data)

            if match_score > 0:  # Only consider jobs with at least one skill match
                results.append({
                    "Job Title": job_data.get("Job Title", "Unknown"),
                    "Company": job_data.get("Companydescription", "Unknown"),
                    "Location": job_data.get("Location", "Unknown"),
                    "Match Score": match_score,
                    "Matched Skills": matched_skills,
                    "Job Description": job_data.get("Job Description", "")[:250] + "..."  # Preview job description
                })

        # Sort jobs by highest match score
        results.sort(key=lambda x: x["Match Score"], reverse=True)
        return results[:top_n]

    def generate_html_report(self, output_file="job_match_report.html"):
        """
        Generate an HTML report summarizing the candidate profile and top job matches.
        """
        best_matches = self.find_best_matches()

        html_content = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Job Match Report</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    margin: 20px;
                    padding: 20px;
                    background-color: #f8f9fa;
                }}
                .container {{
                    max-width: 800px;
                    margin: auto;
                    background: white;
                    padding: 20px;
                    box-shadow: 0px 0px 10px rgba(0, 0, 0, 0.1);
                }}
                h1, h2 {{
                    color: #333;
                }}
                .profile {{
                    background: #007bff;
                    color: white;
                    padding: 15px;
                    border-radius: 8px;
                }}
                .job-list {{
                    max-height: 400px;
                    overflow-y: scroll;
                    border: 1px solid #ddd;
                    padding: 10px;
                    border-radius: 5px;
                    background-color: #ffffff;
                }}
                .job {{
                    padding: 10px;
                    border-bottom: 1px solid #ddd;
                }}
                .job:last-child {{
                    border-bottom: none;
                }}
                .job-title {{
                    font-size: 18px;
                    font-weight: bold;
                    color: #007bff;
                }}
                .company {{
                    font-size: 14px;
                    font-weight: bold;
                    color: #555;
                }}
                .match-score {{
                    color: green;
                    font-weight: bold;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Job Match Report</h1>
                
                <div class="profile">
                    <h2>Your Profile</h2>
                    <p><strong>Name:</strong> {self.resume_data.get("name", "Unknown")}</p>
                    <p><strong>Email:</strong> {self.resume_data.get("email", "N/A")}</p>
                    <p><strong>Phone:</strong> {self.resume_data.get("phone", "N/A")}</p>
                    <p><strong>LinkedIn:</strong> <a href="{self.resume_data.get("linkedin", "#")}" target="_blank">{self.resume_data.get("linkedin", "N/A")}</a></p>
                    <p><strong>Skills:</strong> {", ".join(self.resume_data.get("skills", "").split())}</p>
                </div>

                <h2>Top Job Matches</h2>
                <div class="job-list">
        """

        for job in best_matches:
            html_content += f"""
                <div class="job">
                    <p class="job-title">{job["Job Title"]}</p>
                    <p class="company">{job["Company"]} - {job["Location"]}</p>
                    <p class="match-score">Match Score: {job["Match Score"]}%</p>
                    <p>{job["Job Description"]}</p>
                </div>
            """

        html_content += """
                </div>
            </div>
        </body>
        </html>
        """

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(html_content)

        print(f"✅ Job match report generated: {output_file}")

if __name__ == "__main__":
    resume_path = r"Projects\Job_Matching_Agent\data\Daniel Volin Resume Winter w Summary 2024.pdf"
    job_desc_path = r"Projects\Job_Matching_Agent\data\marketing_sample_for_trulia_com-real_estate__20190901_20191031__30k_data.csv"

    matcher = JobMatcher(resume_path, job_desc_path)
    matcher.generate_html_report("job_match_report.html")
