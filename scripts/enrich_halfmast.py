import pandas as pd
import re
import spacy

# Load the English language model for spaCy
nlp = spacy.load("en_core_web_sm")

def extract_dates(period_string):
    """
    Extracts start and end dates from a period string, attempting to infer the year
    from other dates in the string if a partial date is found.

    Args:
        period_string: The string containing period information.

    Returns:
        A tuple containing the start and end date strings, or (None, None) if dates cannot be extracted.
    """
    if not isinstance(period_string, str):
        return (None, None)

    # Patterns to capture dates in various formats, including capturing the year if present
    date_patterns = [
        r"(\w+ \d+, \d{4})",  # Month Day, Year (e.g., April 16, 2011)
        r"(\w+ \d+)",        # Month Day (e.g., April 16)
        r"(\d+/\d+/\d{2,4})", # MM/DD/YY or MM/DD/YYYY
        r"(\d{4}-\d{2}-\d{2})", # YYYY-MM-DD
        r"(\w+ \d{4})",      # Month Year (e.g., November 2025)
        r"(\d+ \w+)",        # Day Month (e.g., 16 April)
        r"(\w+ \d+(?:st|nd|rd|th))", # Month Day with suffix (e.g., May 27th)
    ]

    # Combine patterns to find all potential dates and years
    all_dates_with_years = []
    all_dates_without_years = []
    potential_years = []

    for pattern in date_patterns:
        matches = re.findall(pattern, period_string)
        for match in matches:
            if re.search(r"\d{4}", match):
                all_dates_with_years.append(match)
                year_match = re.search(r"\d{4}", match)
                if year_match:
                  potential_years.append(year_match.group(0))
            else:
                all_dates_without_years.append(match)

    # Attempt to find date ranges first
    range_patterns = [
        r"From (.+) until sunset on (.+)", # From Date until sunset on Date
        r"From (.+) until (.+)",          # From Date until Date
        r"From (.+) to (.+)",             # From Date to Date
        r"(.+) to (.+)",                  # Date to Date
        r"(.+) and (.+)",                 # Date and Date (less likely for ranges, but possible)
    ]

    start_date = None
    end_date = None

    for pattern in range_patterns:
        match = re.search(pattern, period_string)
        if match:
            start_candidate = match.group(1).strip()
            end_candidate = match.group(2).strip()

            # Try to extract a proper date string from the captured groups
            start_dates_in_range = []
            end_dates_in_range = []
            for dp in date_patterns:
                 start_dates_in_range.extend(re.findall(dp, start_candidate))
                 end_dates_in_range.extend(re.findall(dp, end_candidate))

            if start_dates_in_range and end_dates_in_range:
                start_date = start_dates_in_range[0]
                end_date = end_dates_in_range[0]

                # Attempt to infer year if missing
                if re.search(r"\d{4}", start_date) is None and potential_years:
                    start_date = f"{start_date}, {potential_years[0]}"
                if re.search(r"\d{4}", end_date) is None and potential_years:
                     end_date = f"{end_date}, {potential_years[0]}"

                return (start_date, end_date)

            elif start_dates_in_range:
                 # If only start date is found in range pattern, assume it's a single date
                 start_date = start_dates_in_range[0]
                 if re.search(r"\d{4}", start_date) is None and potential_years:
                    start_date = f"{start_date}, {potential_years[0]}"
                 return (start_date, start_date)

            elif end_dates_in_range:
                # If only end date is found in range pattern, assume it's a single date
                end_date = end_dates_in_range[0]
                if re.search(r"\d{4}", end_date) is None and potential_years:
                     end_date = f"{end_date}, {potential_years[0]}"
                return (end_date, end_date)


    # If no range found, check for single dates
    all_found_dates = all_dates_with_years + all_dates_without_years
    if all_found_dates:
        # If multiple dates are found without a clear range pattern, take the first and last as start and end
        if len(all_found_dates) > 1:
            start_date = all_found_dates[0]
            end_date = all_found_dates[-1]

            # Attempt to infer year if missing
            if re.search(r"\d{4}", start_date) is None and potential_years:
                 start_date = f"{start_date}, {potential_years[0]}"
            if re.search(r"\d{4}", end_date) is None and potential_years:
                 end_date = f"{end_date}, {potential_years[-1]}" # Use last potential year for end date

            return (start_date, end_date)
        else:
            # If only one date is found, it's both the start and end date
            single_date = all_found_dates[0]
            if re.search(r"\d{4}", single_date) is None and potential_years:
                 single_date = f"{single_date}, {potential_years[0]}"
            return (single_date, single_date)


    return (None, None)

def extract_person(text):
    """
    Extracts person entities from a given text using spaCy.

    Args:
        text: The input text string.

    Returns:
        A string containing the extracted person entity (including titles and ranks)
        or None if no person entity is found.
    """
    if not isinstance(text, str):
        return None

    doc = nlp(text)
    person_entities = []
    for ent in doc.ents:
        if ent.label_ == "PERSON":
            person_entities.append(ent.text)

    # Return the first identified person entity
    if person_entities:
        return person_entities[0]
    else:
        return None

def enrich_data(df):
    """
    Enriches the DataFrame by extracting dates and person entities.

    Args:
        df: The input DataFrame.

    Returns:
        The enriched DataFrame.
    """
    # Date Extraction
    df['dt_start'] = None
    df['dt_end'] = None

    df[['dt_start', 'dt_end']] = df['period_en'].apply(lambda x: pd.Series(extract_dates(x)))
    df[['dt_start_fr', 'dt_end_fr']] = df['period_fr'].apply(lambda x: pd.Series(extract_dates(x)))

    df['dt_start'] = df['dt_start'].fillna(df['dt_start_fr'])
    df['dt_end'] = df['dt_end'].fillna(df['dt_end_fr'])

    df = df.drop(columns=['dt_start_fr', 'dt_end_fr'])

    df['dt_start'] = pd.to_datetime(df['dt_start'], errors='coerce')
    df['dt_end'] = pd.to_datetime(df['dt_end'], errors='coerce')

    single_day_keywords_en = r'sunrise to sunset on|until sunset today|until sunset the day'
    single_day_keywords_fr = r"l’aube au crépuscule le|jusqu’au crépuscule aujourd’hui|jusqu’au crépuscule le jour"

    single_day_mask = df['period_en'].str.contains(single_day_keywords_en, na=False, case=False) | \
                      df['period_fr'].str.contains(single_day_keywords_fr, na=False, case=False)

    single_day_mask = single_day_mask & ~(df['dt_start'].notnull() & df['dt_end'].notnull())

    df.loc[single_day_mask & (df['dt_start'].notnull()) & (df['dt_start'] != df['dt_end']), 'dt_end'] = df['dt_start']

    # Person Extraction
    df['person'] = df['notice_en'].apply(extract_person).fillna(
        df['details_en'].apply(extract_person)
    ).fillna(
        df['period_en'].apply(extract_person)
    ).fillna(
        df['location_en'].apply(extract_person)
    )

    return df

# Specify the input and output file paths
input_csv_path = 'data/half_masting_combined.csv'
output_csv_path = 'data/half_masting_enriched.csv'

# Load the data
df = pd.read_csv(input_csv_path)

# Enrich the data
df_enriched = enrich_data(df)

# Save the enriched data to a new CSV file
df_enriched.to_csv(output_csv_path, index=False)

print(f"Enriched data saved to {output_csv_path}")
