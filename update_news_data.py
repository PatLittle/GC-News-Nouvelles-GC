import json
import pandas as pd
import re
import requests
import hashlib

# Function to fetch data from a URL
def fetch_json_data(url):
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        return None

# Function to clean text by removing newline characters
def clean_text(text):
    return text.replace('\n', ' ').replace('\r', ' ') if text else text

# Function to separate text from URL in the TITLE fields using regex for accuracy
def extract_title_url(entry):
    title_text_en = ""
    title_url_en = ""
    title_text_fr = ""
    title_url_fr = ""

    # Separate English title and URL
    if 'TITLE_EN' in entry and entry['TITLE_EN']:
        match_en = re.search(r"<a href='(.*?)'>(.*?)</a>", entry['TITLE_EN'])
        if match_en:
            title_url_en = match_en.group(1)
            title_text_en = match_en.group(2)
        else:
            title_text_en = entry['TITLE_EN']

    # Separate French title and URL
    if 'TITLE_FR' in entry and entry['TITLE_FR']:
        match_fr = re.search(r"<a href='(.*?)'>(.*?)</a>", entry['TITLE_FR'])
        if match_fr:
            title_url_fr = match_fr.group(1)
            title_text_fr = match_fr.group(2)
        else:
            title_text_fr = entry['TITLE_FR']

    entry['TITLE_TEXT_EN'] = clean_text(title_text_en)
    entry['TITLE_URL_EN'] = clean_text(title_url_en)
    entry['TITLE_TEXT_FR'] = clean_text(title_text_fr)
    entry['TITLE_URL_FR'] = clean_text(title_url_fr)
    return entry

# Function to normalize Minister names
def normalize_minister_name(name):
    if name.startswith("Hon. "):
        return name.replace("Hon. ", "")
    elif name.startswith("L'hon. "):
        return name.replace("L'hon. ", "")
    return name

# Function to compute MD5 hash of a row
def hash_row(row):
    # Sort the items by column names to ensure consistent order
    items = row.fillna('').items()
    sorted_items = sorted(items, key=lambda x: x[0])
    row_str = ','.join(str(value) for key, value in sorted_items)
    return hashlib.md5(row_str.encode()).hexdigest()

# Main function to fetch data, process it, and return the DataFrame
def main():
    timestamp = int(time.time() * 1000)
    url_en = f"https://www.canada.ca/en/news.datatable.json?_={timestamp}"
    url_fr = f"https://www.canada.ca/fr/nouvelles.datatable.json?_={timestamp}"

    # Fetch the JSON data
    data_en = fetch_json_data(url_en)
    data_fr = fetch_json_data(url_fr)

    if data_en is None or data_fr is None:
        print("Failed to fetch data from URLs.")
        return None

    news_en = data_en['data']
    news_fr = data_fr['data']

    # Normalize Minister names in both datasets and clean text fields
    for entry in news_en:
        entry['MINISTER_EN'] = normalize_minister_name(clean_text(entry.get('MINISTER', '')))
        for key in entry:
            entry[key] = clean_text(entry[key])
    for entry in news_fr:
        entry['MINISTER_FR'] = normalize_minister_name(clean_text(entry.get('MINISTER', '')))
        for key in entry:
            entry[key] = clean_text(entry[key])

    # Combine the data into a single DataFrame based on timestamp and minister name
    combined_data = []
    for en in news_en:
        match_fr = None
        for fr in news_fr:
            if (en.get("PUBDATE") == fr.get("PUBDATE") and
                normalize_minister_name(en.get("MINISTER", "")) == normalize_minister_name(fr.get("MINISTER", ""))):
                match_fr = fr
                break
        if match_fr:
            combined_entry = {
                "PUBDATE": en.get("PUBDATE", ""),
                "TITLE_EN": en.get("TITLE", ""),
                "TEASER_EN": en.get("TEASER", ""),
                "ADDITIONAL_TOPICS_EN": en.get("ADDITIONAL_TOPICS", ""),
                "AUDIENCE_EN": en.get("AUDIENCE", ""),
                "TYPE_EN": en.get("TYPE", ""),
                "DEPT_EN": en.get("DEPT", ""),
                "LOCATION_EN": en.get("LOCATION", ""),
                "MINISTER_EN": en.get("MINISTER", ""),
                "TOPIC_EN": en.get("TOPIC", ""),
                "SUBJECT_EN": en.get("SUBJECT", ""),
                "TITLE_FR": match_fr.get("TITLE", ""),
                "TEASER_FR": match_fr.get("TEASER", ""),
                "ADDITIONAL_TOPICS_FR": match_fr.get("ADDITIONAL_TOPICS", ""),
                "AUDIENCE_FR": match_fr.get("AUDIENCE", ""),
                "TYPE_FR": match_fr.get("TYPE", ""),
                "DEPT_FR": match_fr.get("DEPT", ""),
                "LOCATION_FR": match_fr.get("LOCATION", ""),
                "MINISTER_FR": match_fr.get("MINISTER", ""),
                "TOPIC_FR": match_fr.get("TOPIC", ""),
                "SUBJECT_FR": match_fr.get("SUBJECT", "")
            }
            combined_data.append(extract_title_url(combined_entry))

    # Create a DataFrame
    df_combined = pd.DataFrame(combined_data)

    # Reorder the columns to include the separated TITLE_TEXT and TITLE_URL fields
    ordered_columns = [
        "PUBDATE",
        "TITLE_TEXT_EN", "TITLE_URL_EN", "TITLE_TEXT_FR", "TITLE_URL_FR",
        "TEASER_EN", "TEASER_FR",
        "ADDITIONAL_TOPICS_EN", "ADDITIONAL_TOPICS_FR",
        "AUDIENCE_EN", "AUDIENCE_FR",
        "TYPE_EN", "TYPE_FR",
        "DEPT_EN", "DEPT_FR",
        "LOCATION_EN", "LOCATION_FR",
        "MINISTER_EN", "MINISTER_FR",
        "TOPIC_EN", "TOPIC_FR",
        "SUBJECT_EN", "SUBJECT_FR"
    ]

    # Create a copy to avoid SettingWithCopyWarning
    df_combined_ordered = df_combined[ordered_columns].copy()

    # Convert PUBDATE to datetime
    df_combined_ordered['PUBDATE'] = pd.to_datetime(df_combined_ordered['PUBDATE'])

    # Sort by PUBDATE ascending and TITLE_TEXT_EN ascending
    df_combined_ordered = df_combined_ordered.sort_values(by=['PUBDATE', 'TITLE_TEXT_EN'], ascending=[False, True])

    return df_combined_ordered

if __name__ == "__main__":
    new_data = main()
    if new_data is not None:
        # Compute the hash for the new data
        new_data['hash'] = new_data.apply(hash_row, axis=1)

        # Move the 'hash' column to the first position
        columns = new_data.columns.tolist()
        columns.insert(0, columns.pop(columns.index('hash')))
        new_data = new_data[columns]

        # Load the existing CSV
        existing_csv_path = 'combined_news.csv'
        try:
            existing_data = pd.read_csv(existing_csv_path)
            existing_data['PUBDATE'] = pd.to_datetime(existing_data['PUBDATE'])

            # Check if 'hash' column exists in the existing data
            if 'hash' not in existing_data.columns:
                # Compute the hash for the existing data
                existing_data['hash'] = existing_data.apply(hash_row, axis=1)
                print("Backfilled 'hash' column for existing data.")

            # Define the unique identifier columns
            id_columns = ['PUBDATE', 'TITLE_TEXT_EN', 'TITLE_URL_EN']

            # Combine data and remove duplicates based on unique identifiers
            combined_data = pd.concat([existing_data, new_data], ignore_index=True)
            combined_data.drop_duplicates(subset=id_columns, keep='last', inplace=True)

        except FileNotFoundError:
            # If the file does not exist, use new data as the combined data
            combined_data = new_data.copy()
            print("Created new data with 'hash' column.")

        # Sort by PUBDATE descending and TITLE_TEXT_EN ascending
        combined_data = combined_data.sort_values(by=['PUBDATE', 'TITLE_TEXT_EN'], ascending=[False, True])

        # Save the updated CSV file
        combined_data.to_csv(existing_csv_path, index=False)
        print(f"Updated combined CSV saved to {existing_csv_path}")
