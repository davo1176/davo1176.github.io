import pandas as pd
import json
import re
import os

class JobParser:
    def __init__(self, job_desc_file):
        """Load job descriptions from CSV/JSON."""
        if not os.path.exists(job_desc_file):
            raise FileNotFoundError(f"File {job_desc_file} not found.")

        self.job_desc_file = job_desc_file
        self.df = self.load_data()

    def load_data(self):
        """Load job descriptions into a Pandas DataFrame."""
        if self.job_desc_file.endswith(".json"):
            return pd.read_json(self.job_desc_file)
        elif self.job_desc_file.endswith(".csv"):
            return pd.read_csv(self.job_desc_file)
        else:
            raise ValueError("Unsupported file format. Use JSON or CSV.")

    def clean_html(self, text):
        """Remove HTML tags from job descriptions."""
        return re.sub(r'<.*?>', '', str(text))

    def get_job_by_id(self, job_id):
        """Fetch job details for a given job ID."""
        job = self.df[self.df["Uniq Id"] == job_id]
        if job.empty:
            return None

        job_data = job.iloc[0].to_dict()
        job_data["Job Description"] = self.clean_html(job_data.get("Job Description", ""))
        return job_data

    def search_jobs_by_keyword(self, keyword, num_results=5):
        """Search for jobs based on a keyword in title or description."""
        matched_jobs = self.df[
            self.df["Job Title"].str.contains(keyword, case=False, na=False) |
            self.df["Job Description"].str.contains(keyword, case=False, na=False)
        ].head(num_results)

        results = []
        for _, row in matched_jobs.iterrows():
            job_data = row.to_dict()
            job_data["Job Description"] = self.clean_html(job_data.get("Job Description", ""))
            results.append(job_data)

        return results

if __name__ == "__main__":
    job_parser = JobParser("Projects\Job_Matching_Agent\data\marketing_sample_for_trulia_com-real_estate__20190901_20191031__30k_data.csv")  # Update path if needed

    # Test fetching a job by ID
    job_id = "511f9a53920f4641d701d51d3589349f"
    job_details = job_parser.get_job_by_id(job_id)
    print(json.dumps(job_details, indent=4))

    # Test searching for jobs with keyword
    keyword_search = job_parser.search_jobs_by_keyword("manager")
    print(json.dumps(keyword_search, indent=4))

