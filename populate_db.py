import sqlite3
import pandas as pd

# Load the filtered CSV file
file_path = 'filtered_airports_filtered.csv'
airports_df = pd.read_csv(file_path)

# Remove duplicates based on 'iata_code' and 'name'
airports_df = airports_df.drop_duplicates(subset=['iata_code', 'name'])

# Print the first few rows of the dataframe to verify the data
print("First few rows of the CSV file:")
print(airports_df.head())

# Connect to the SQLite database (it will be created if it doesn't exist)
conn = sqlite3.connect('airports.db')
cursor = conn.cursor()

# Create the airports table
cursor.execute('''
CREATE TABLE IF NOT EXISTS airports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    iata_code TEXT NOT NULL
)
''')
print("Table created successfully.")

# Insert data into the airports table
for index, row in airports_df.iterrows():
    cursor.execute('INSERT INTO airports (name, iata_code) VALUES (?, ?)', (row['name'], row['iata_code']))

# Commit the changes and close the connection
conn.commit()
conn.close()

print("Data inserted successfully.")
