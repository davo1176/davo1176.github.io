import fitz  # PyMuPDF for PDF parsing
import re
import json
import os

class ResumeParser:
    def __init__(self, file_path):
        self.file_path = file_path
        self.text = self.extract_text()
        self.parsed_data = self.parse_resume()

    def extract_text(self):
        """Extract raw text from a PDF file."""
        _, ext = os.path.splitext(self.file_path)

        if ext.lower() == ".pdf":
            doc = fitz.open(self.file_path)
            return "\n".join([page.get_text("text") for page in doc])
        else:
            raise ValueError("Unsupported file format. Currently supports PDFs only.")

    def extract_contact_info(self):
        """Extracts email, phone, and LinkedIn profile from resume text."""
        contact_info = {}
        
        # Extract email
        email_match = re.search(r'\b[\w.-]+@[\w.-]+\.[a-zA-Z]{2,}\b', self.text)
        contact_info['email'] = email_match.group(0) if email_match else None
        
        # Extract phone number
        phone_match = re.search(r'\+?\d{1,3}[\s-]?\(?\d{2,3}\)?[\s-]?\d{3,4}[\s-]?\d{3,4}', self.text)
        contact_info['phone'] = phone_match.group(0) if phone_match else None
        
        # Extract LinkedIn
        linkedin_match = re.search(r'https?://(www\.)?linkedin\.com/in/[\w-]+', self.text)
        contact_info['linkedin'] = linkedin_match.group(0) if linkedin_match else None
        
        return contact_info

    def extract_sections(self):
        """Splits resume text into key sections."""
        sections = {}
        
        # Identify sections based on common resume headers
        section_headers = ["SUMMARY", "EDUCATION", "EXPERIENCE", "SKILLS", "INTERESTS"]
        section_positions = {header: self.text.find(header) for header in section_headers if self.text.find(header) != -1}
        
        sorted_sections = sorted(section_positions.items(), key=lambda x: x[1])
        
        for i, (section, start_idx) in enumerate(sorted_sections):
            end_idx = sorted_sections[i + 1][1] if i + 1 < len(sorted_sections) else len(self.text)
            sections[section] = self.text[start_idx:end_idx].strip()
        
        return sections

    def parse_resume(self):
        """Extracts structured resume data."""
        contact_info = self.extract_contact_info()
        sections = self.extract_sections()
        
        return {
            "name": "Unknown",  # Name extraction can be refined with NLP later
            "email": contact_info.get("email"),
            "phone": contact_info.get("phone"),
            "linkedin": contact_info.get("linkedin"),
            "summary": sections.get("SUMMARY", ""),
            "education": sections.get("EDUCATION", ""),
            "experience": sections.get("EXPERIENCE", ""),
            "skills": sections.get("SKILLS", ""),
            "interests": sections.get("INTERESTS", ""),
        }

    def to_json(self):
        """Returns parsed data as JSON."""
        return json.dumps(self.parsed_data, indent=4)


# Example Usage
if __name__ == "__main__":
    resume_path = "/mnt/data/Daniel Volin Resume Winter w Summary 2024.pdf"
    parser = ResumeParser(resume_path)
    print(parser.to_json())
