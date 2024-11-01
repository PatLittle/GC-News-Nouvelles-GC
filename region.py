import pandas as pd

# Read the combined_news.csv file
df = pd.read_csv('combined_news.csv')

# Check if TYPE_EN column exists
if 'LOCATION_EN' not in df.columns:
    print("Error: 'LOCATION_EN' column not found in combined_news.csv")
    exit(1)

# Calculate the breakdown of TYPE_EN
loc_counts = df['LOCATION_EN'].value_counts()

# Start building the Mermaid.js pie chart code
mermaid_pie_chart = 'pie showData title Breakdown of LOCATION_EN\n\n'

# Add each TYPE_EN and its count to the pie chart code
for loc_en, count in loc_counts.items():
    # Escape double quotes in type_en if necessary
    loc_en_escaped = loc_en.replace('"', '\\"')
    mermaid_pie_chart += f'    "{loc_en_escaped}" : {count}\n'

# Save the Mermaid.js code to a file
with open('loc_en_pie_chart.mmd', 'w') as f:
    f.write(mermaid_pie_chart)

print("Mermaid.js pie chart code generated and saved to 'loc_en_pie_chart.mmd'")
