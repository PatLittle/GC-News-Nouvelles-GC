import pandas as pd
import datetime

# Read the combined_news.csv file
df = pd.read_csv('combined_news.csv')

# Convert PUBDATE to datetime
df['PUBDATE'] = pd.to_datetime(df['PUBDATE'])

# Get today's date
today = datetime.datetime.now()

# Calculate the date 12 months ago
twelve_months_ago = today - datetime.timedelta(days=365)

# Filter data for the last 12 months
df_last_12_months = df[df['PUBDATE'] >= twelve_months_ago]

# Extract month and year from PUBDATE
df_last_12_months['Month'] = df_last_12_months['PUBDATE'].dt.to_period('M')

# Explode TOPIC_EN if it contains multiple topics
df_last_12_months['TOPIC_EN'] = df_last_12_months['TOPIC_EN'].fillna('Unknown')
df_last_12_months['TOPIC_EN'] = df_last_12_months['TOPIC_EN'].str.split(';')
df_exploded = df_last_12_months.explode('TOPIC_EN')

# Trim whitespace from topics
df_exploded['TOPIC_EN'] = df_exploded['TOPIC_EN'].str.strip()

# Group by Month and TOPIC_EN, count the number of releases
grouped = df_exploded.groupby(['Month', 'TOPIC_EN']).size().reset_index(name='Counts')

# Get the list of all months in the last 12 months
start_period = pd.Timestamp(twelve_months_ago).to_period('M')
end_period = pd.Timestamp(today).to_period('M')
month_range = pd.period_range(start=start_period, end=end_period, freq='M')

# Create a pivot table with Months as columns and TOPIC_EN as rows
pivot_table = grouped.pivot(index='TOPIC_EN', columns='Month', values='Counts').fillna(0)

# Ensure all months are included in the columns
pivot_table = pivot_table.reindex(columns=month_range, fill_value=0)

# Calculate total releases per TOPIC_EN
total_releases = df_exploded['TOPIC_EN'].value_counts()

# Select top N topics
N = 5  # Adjust N as needed
top_topics = total_releases.head(N).index.tolist()

# Filter pivot_table for top topics
pivot_table_top = pivot_table.loc[top_topics]

# Build the x-axis labels (months)
x_axis_labels = [str(month) for month in month_range]

# Build Mermaid.js xychart-beta code
mermaid_chart_code = 'xychart-beta\n'
mermaid_chart_code += '    title "Number of Releases by Topic Over the Last 12 Months"\n'
mermaid_chart_code += f'    x-axis [{", ".join(x_axis_labels)}]\n'

# For each topic, add a line with label and data
for topic in top_topics:
    counts = pivot_table_top.loc[topic].astype(int).tolist()
    counts_str = ', '.join(map(str, counts))
    topic_escaped = topic.replace('"', '\\"')
    mermaid_chart_code += f'    line "{topic_escaped}" [{counts_str}]\n'

# Save the Mermaid.js code to a file
with open('topic_en_line_chart.mmd', 'w') as f:
    f.write(mermaid_chart_code)

print("Mermaid.js line chart code generated and saved to 'topic_en_line_chart.mmd'")
