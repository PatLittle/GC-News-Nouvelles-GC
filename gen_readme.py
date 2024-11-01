import os

def read_mermaid_file(file_path):
    with open(file_path, 'r') as file:
        return file.read()

def generate_readme():
    # File paths
    pie_chart_file = 'type_en_pie_chart.mmd'
    dept_line_chart_file = 'dept_releases_line_chart.mmd'
    topic_line_chart_file = 'topic_en_line_chart.mmd'

    # Read Mermaid.js code from files
    pie_chart_code = read_mermaid_file(pie_chart_file)
    dept_line_chart_code = read_mermaid_file(dept_line_chart_file)
    topic_line_chart_code = read_mermaid_file(topic_line_chart_file)

    # Start building the README content
    readme_content = '# Government of Canada News Releases Analysis\n\n'
    readme_content += 'This repository contains analyses of Government of Canada news releases. The following charts provide insights into the data.\n\n'

    # Add Pie Chart
    readme_content += '## Breakdown of Release Types\n\n'
    readme_content += '```mermaid\n'
    readme_content += pie_chart_code.strip() + '\n'
    readme_content += '```\n\n'

    # Add Department Releases Line Chart
    readme_content += '## Releases by Department Over the Last 30 Days\n\n'
    readme_content += '```mermaid\n'
    readme_content += dept_line_chart_code.strip() + '\n'
    readme_content += '```\n\n'

    # Add Topic Releases Line Chart
    readme_content += '## Releases by Topic Over the Last 12 Months\n\n'
    readme_content += '```mermaid\n'
    readme_content += topic_line_chart_code.strip() + '\n'
    readme_content += '```\n\n'

    # Save the README.md file
    with open('README.md', 'w') as readme_file:
        readme_file.write(readme_content)

    print("README.md has been generated successfully.")

if __name__ == '__main__':
    generate_readme()
