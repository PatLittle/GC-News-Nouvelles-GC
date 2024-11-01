import csv
import hashlib

input_file = '‎combined_news (3).csv'
output_file = 'combined_news.csv'

def hash_row(row):
    row_str = ','.join(row.values())
    return hashlib.md5(row_str.encode()).hexdigest()

with open(input_file, mode='r', newline='') as infile, open(output_file, mode='w', newline='') as outfile:
    reader = csv.DictReader(infile)
    fieldnames = reader.fieldnames + ['hash']
    writer = csv.DictWriter(outfile, fieldnames=fieldnames)
    writer.writeheader()

    for row in reader:
        row['hash'] = hash_row(row)
        writer.writerow(row)
