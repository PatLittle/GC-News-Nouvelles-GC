import pandas as pd
import datetime

# Read the combined_news.csv file
df = pd.read_csv('combined_news.csv')

# Convert PUBDATE to datetime
df['PUBDATE'] = pd.to_datetime(df['PUBDATE'])

# Get today's date
today = datetime.datetime.now()

# Calculate the date 30 days ago
thirty_days_ago = today - datetime.timedelta(days=30)

# Filter data for the last 30 days
df_last_30_days = df[df['PUBDATE'] >= thirty_days_ago]

# Extract date from PUBDATE
df_last_30_days['Date'] = df_last_30_days['PUBDATE'].dt.date

# Group by Date and DEPT_EN, count the number of releases
grouped = df_last_30_days.groupby(['Date', 'DEPT_EN']).size().reset_index(name='Counts')

# Get the list of all dates in the last 30 days
date_range = pd.date_range(start=thirty_days_ago.date(), end=today.date())

# Create a pivot table with Dates as columns and DEPT_EN as rows
pivot_table = grouped.pivot(index='DEPT_EN', columns='Date', values='Counts').fillna(0)

# Ensure all dates are included in the columns
pivot_table = pivot_table.reindex(columns=date_range.date, fill_value=0)

# Calculate total releases per DEPT_EN
total_releases = df_last_30_days['DEPT_EN'].value_counts()

# Select top 5 departments
top_departments = total_releases.head(5).index.tolist()

# Filter pivot_table for top departments
pivot_table_top = pivot_table.loc[top_departments]

# Build the x-axis labels (dates)
x_axis_labels = [date.strftime('%Y-%m-%d') for date in date_range]

# Build Mermaid.js xychart-beta code
mermaid_chart_code = 'xychart-beta\n'
mermaid_chart_code += '    title "Number of Releases by Department Over the Last 30 Days"\n'
mermaid_chart_code += f'    x-axis [{", ".join(x_axis_labels)}]\n'

# For each department, add a line with label and data
for dept in top_departments:
    counts = pivot_table_top.loc[dept].astype(int).tolist()
    counts_str = ', '.join(map(str, counts))
    dept_escaped = dept.replace('"', '\\"')
    mermaid_chart_code += f'    line "{dept_escaped}" [{counts_str}]\n'

# Save the Mermaid.js code to a file
with open('dept_releases_line_chart.mmd', 'w') as f:
    f.write(mermaid_chart_code)

print("Mermaid.js line chart code generated and saved to 'dept_releases_line_chart.mmd'")
