'''
First Script -- Colorado Ski
'''
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime

# Path to your ChromeDriver
driver_path = "C:/Users/danie/chromedriver-win64/chromedriver.exe"
csv_file_path = "C:/Users/danie/OneDrive/Desktop/PersonalProjects/SkiWebScraping/snow_report_data_soloradoski.csv"

# Set up the Chrome driver using Service
service = Service(driver_path)
driver = webdriver.Chrome(service=service)

# Open the website
url = "https://www.coloradoski.com/snow-report/"
driver.get(url)

# Dynamic wait: Wait until at least one Mid-Mt Depth value is not "0"
try:
    WebDriverWait(driver, 30).until(
        lambda d: any(
            mid_mt.text.strip() != '0"'
            for mid_mt in d.find_elements(By.CLASS_NAME, "answer.mid-mtn")
        )
    )
except Exception as e:
    print("Timeout waiting for Mid-Mt Depth to load:", e)
    driver.quit()

# Get page source after JavaScript has loaded
html = driver.page_source
soup = BeautifulSoup(html, "html.parser")

# Close the browser
driver.quit()

# Initialize list to hold data
snow_data = []

# Extract resort data
resorts = soup.find_all("div", class_="inner")

for resort in resorts:
    # Extract Resort Name
    name_tag = resort.find("h3", class_="h5 text-left")
    
    # Extract Snow-related Data
    snow_24hr_tag = resort.find("span", class_="answer twentyfour")
    snow_48hr_tag = resort.find("span", class_="answer fortyeight")
    mid_mt_depth_tag = resort.find("span", class_="answer mid-mtn")
    surface_conditions_tag = resort.find("p", class_="surface")
    lifts_open_tag = resort.find("p", class_="lifts-open")
    green_runs_tag = resort.find("p", class_="green-runs")
    blue_runs_tag = resort.find("p", class_="blue-runs")
    black_runs_tag = resort.find("p", class_="diamond-runs")
    double_black_runs_tag = resort.find("p", class_="double-diamond-runs")

    # Ensure Resort Name exists
    if name_tag:
        name = name_tag.text.strip()
        snow_24hr = snow_24hr_tag.text.strip() if snow_24hr_tag else "N/A"
        snow_48hr = snow_48hr_tag.text.strip() if snow_48hr_tag else "N/A"
        mid_mt_depth = mid_mt_depth_tag.text.strip() if mid_mt_depth_tag else "N/A"
        surface_conditions = surface_conditions_tag.text.strip() if surface_conditions_tag else "N/A"
        lifts_open = lifts_open_tag.text.strip() if lifts_open_tag else "N/A"
        green_runs = green_runs_tag.text.strip() if green_runs_tag else "N/A"
        blue_runs = blue_runs_tag.text.strip() if blue_runs_tag else "N/A"
        black_runs = black_runs_tag.text.strip() if black_runs_tag else "N/A"
        double_black_runs = double_black_runs_tag.text.strip() if double_black_runs_tag else "N/A"

        # Append data
        snow_data.append({
            "Date": datetime.now().strftime("%Y-%m-%d"),
            "Resort": name,
            "Snow (24hr)": snow_24hr,
            "Snow (48hr)": snow_48hr,
            "Mid-Mt Depth": mid_mt_depth,
            "Surface Conditions": surface_conditions,
            "Lifts Open": lifts_open,
            "Green Runs": green_runs,
            "Blue Runs": blue_runs,
            "Black Runs": black_runs,
            "Double Black Runs": double_black_runs
        })

# Convert to DataFrame
new_data_df = pd.DataFrame(snow_data)

# Check if the CSV already exists
if os.path.exists(csv_file_path):
    # Read existing data
    existing_data_df = pd.read_csv(csv_file_path)
    
    # Append new data to existing data
    combined_df = pd.concat([existing_data_df, new_data_df], ignore_index=True)
else:
    # If CSV doesn't exist, the new data becomes the initial data
    combined_df = new_data_df

# Save the combined DataFrame back to CSV
combined_df.to_csv(csv_file_path, index=False)

# Display the newly added data
print(new_data_df)


'''
Second Script -- OnTheSnow
'''
# Note: Takes the Higher Base Depth Value if a Range is Given
import os
import re
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime

# File paths
driver_path = r"C:\Users\danie\chromedriver-win64\chromedriver.exe"
csv_file_path = r"C:\Users\danie\OneDrive\Desktop\PersonalProjects\SkiWebScraping\snow_report_data_onthesnow.csv"
log_file_path = r"C:\Users\danie\OneDrive\Desktop\PersonalProjects\SkiWebScraping\scraper_log.txt"

# Set up logging
logging.basicConfig(filename=log_file_path, level=logging.INFO, format='%(asctime)s - %(message)s')
logging.info("Script started.")

try:
    # Set up the Chrome driver using Service
    service = Service(driver_path)
    driver = webdriver.Chrome(service=service)

    # Open the website
    url = "https://www.onthesnow.com/colorado/skireport"
    driver.get(url)

    # Dynamic wait: Wait until resort rows are loaded
    WebDriverWait(driver, 40).until(
        EC.presence_of_element_located((By.CLASS_NAME, "styles_row__HA9Yq"))
    )
    logging.info("Resort data loaded successfully.")

    # Get page source after JavaScript has loaded
    html = driver.page_source
    soup = BeautifulSoup(html, "html.parser")

    # Close the browser
    driver.quit()

    # Initialize list to hold data
    snow_data = []

    # Extract resort data
    resorts = soup.find_all("tr", class_="styles_row__HA9Yq")  # Each resort is in a table row

    for resort in resorts:
        data_tags = resort.find_all("span", class_="h4 styles_h4__x3zzi")

        # Ensure enough data points exist
        if len(data_tags) >= 5:
            open_trails_raw = data_tags[3].text.strip() if data_tags[3] else "N/A"

            # Regex to extract Trails Open, Total Trails, and Percentage Open
            match = re.search(r"(\d+)\s*/\s*(\d+)(\d{2,3})?\s*(\d+%)?", open_trails_raw)

            if match:
                trails_open = int(match.group(1))
                total_trails_raw = match.group(2)
                last_digits = int(match.group(3)) if match.group(3) else "N/A"
                percentage_open = match.group(4) if match.group(4) else "N/A"

                # Correction logic
                total_trails = int(total_trails_raw)
                corrected_total_trails = total_trails

                # Attempt to correct by removing trailing digits
                for i in range(1, 4):  # Check removing 1 to 3 digits
                    possible_total = int(str(total_trails)[:-i]) if len(str(total_trails)) > i else total_trails

                    if possible_total >= trails_open:
                        if percentage_open != "N/A":
                            calculated_percentage = round((trails_open / possible_total) * 100)
                            if calculated_percentage == int(percentage_open.strip('%')):
                                corrected_total_trails = possible_total
                                break
                        else:
                            # If percentage is not provided, use logical deduction
                            if possible_total - trails_open <= 50:  # Assuming it's reasonable
                                corrected_total_trails = possible_total
                                break

                # Final validation
                if corrected_total_trails < trails_open:
                    corrected_total_trails = "N/A"

            else:
                trails_open, total_trails_raw, corrected_total_trails, percentage_open = "N/A", "N/A", "N/A", "N/A"

            snow_data.append({
                "Date": datetime.now().strftime("%Y-%m-%d"),
                "Resort": data_tags[0].text.strip() if data_tags[0] else "N/A",          # Resort Name
                "Snow (24hr)": data_tags[1].text.strip().rstrip('"').rstrip('-') if data_tags[1] else "N/A",      # Cleaned Snow (24hr)
                "Base Depth": data_tags[2].text.strip() if data_tags[2] else "N/A",       # Base Depth
                "Trails Open": trails_open,                                               # Cleaned Trails Open
                "Total Trails": corrected_total_trails,                                   # Renamed Corrected Total Trails
                "Lifts Open": data_tags[4].text.strip().rstrip('-') if data_tags[4] else "N/A"        # Cleaned Lifts Open
            })

    # Convert to DataFrame
    new_data_df = pd.DataFrame(snow_data)

    # Separate Base Depth into two columns
    new_data_df[['Base Depth', 'Base Depth Notes']] = new_data_df['Base Depth'].str.extract(r'(\d+\"(?:-\d+\")?)(.*)')

    # Calculate % Trails Open
    new_data_df["% Trails Open"] = (new_data_df["Trails Open"] / new_data_df["Total Trails"] * 100).round(2)

    # Append or create CSV
    if os.path.exists(csv_file_path):
        existing_data_df = pd.read_csv(csv_file_path)
        combined_df = pd.concat([existing_data_df, new_data_df], ignore_index=True)
    else:
        combined_df = new_data_df

    # Save combined data
    combined_df.to_csv(csv_file_path, index=False)
    logging.info(f"Data successfully saved to {csv_file_path}")

    # Display newly added data
    print(new_data_df)

except Exception as e:
    logging.error(f"An error occurred: {e}")
    print(f"An error occurred: {e}")
