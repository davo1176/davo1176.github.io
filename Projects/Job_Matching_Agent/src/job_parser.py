import pandas as pd
import json

class JobParser:
    def __init__(self, job_desc_file):
        self.job_desc_file = job_desc_file
        self.df = self.load_data()

    def load_data(self):
        """Load job descriptions from CSV/JSON."""
        if self.job_desc_file.endswith(".json"):
            return pd.read_json(self.job_desc_file)
        elif self.job_desc_file.endswith(".csv"):
            return pd.read_csv(self.job_desc_file)
        else:
            raise ValueError("Unsupported file format. Use JSON or CSV.")

    def get_job_details(self, job_id):
        """Fetch job details for a given job ID."""
        job = self.df.loc[self.df["job_posting_id"] == job_id]
        return job.to_dict(orient="records")[0] if not job.empty else None

# Example Usage
if __name__ == "__main__":
    job_parser = JobParser("data/jobs.json")
    job_data = job_parser.get_job_details("4143395504")
    print(json.dumps(job_data, indent=4))
