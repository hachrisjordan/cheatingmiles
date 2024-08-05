from flask import Flask, render_template, request, jsonify
import sqlite3
import datetime
from difflib import SequenceMatcher
from copa import process_copa_url  # Import the function from copa.py
import pandas as pd
import requests

app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def index():
    form_data = {}
    urls = []
    error_message = None
    df = None  # Initialize df to None

    if request.method == 'POST':
        form_data = {
            'origin': request.form.get('origin'),
            'destination': request.form.get('destination'),
            'selected_date': request.form.get('selected_date'),
            'use_date_range': request.form.get('use_date_range') == 'on',
            'seats': request.form.get('seats', '1')
        }
        
        print("Form data:", form_data)  # Debug print
        
        if form_data['origin'] and form_data['destination']:
            date_range = calculate_date_range(form_data['selected_date'], form_data['use_date_range'])
            
            all_data = []
            base_url = "https://shopping.copaair.com/miles"
            airlines = ['AC', 'CA', 'AI', 'NH', 'OZ', 'OS', 'MS', 'ET', 'BR', 'LO', 'LH', 'SK', 'SQ', 'TK', 'UA']
            
            for date in date_range:
                # Original URL
                url = f"{base_url}?roundtrip=false&area1={form_data['origin']}&area2={form_data['destination']}&date1={date}&date2=&flexible_dates_v2=false&adults={form_data['seats']}&children=0&infants=0&isMiles=true&advanced_air_search=false&stopover=false&sf=gs&langid=en&promocode="
                urls.append(url)
                
                # Process original URL
                try:
                    result = process_copa_url(url)
                    print("Scraped result for original URL:", result)  # Debug print
                    if 'error' in result:
                        print(f"Error for URL {url}: {result['error']}")
                    else:
                        all_data.extend(result['data'])
                except requests.Timeout:
                    print(f"Timeout occurred for URL: {url}")
                except Exception as e:
                    print(f"An error occurred for URL {url}: {str(e)}")
                
                # New URL format with airline preferences
                for airline in airlines:
                    airline_url = f"{base_url}?roundtrip=false&adults={form_data['seats']}&children=0&infants=0&date1={date}&date2=null&promocode=&area1={form_data['origin']}&area2={form_data['destination']}&advanced_air_search=false&flexible_dates_v2=false&airline_preference={airline}"
                    urls.append(airline_url)
                    
                    # Process airline-specific URL
                    try:
                        airline_result = process_copa_url(airline_url)
                        print(f"Scraped result for {airline} URL:", airline_result)  # Debug print
                        if 'error' in airline_result:
                            print(f"Error for URL {airline_url}: {airline_result['error']}")
                        else:
                            all_data.extend(airline_result['data'])
                    except requests.Timeout:
                        print(f"Timeout occurred for URL: {airline_url}")
                    except Exception as e:
                        print(f"An error occurred for URL {airline_url}: {str(e)}")

            if all_data:
                scraped_data = {
                    'data': all_data
                }
                # New data preparation step
                for row in scraped_data['data']:
                    # Ensure the row has Economy and Business keys
                    if 'Economy' not in row:
                        row['Economy'] = None
                    if 'Business' not in row:
                        row['Business'] = None
                    
                    # Now safely process Economy and Business columns
                    for key in ['Economy', 'Business']:
                        if not row[key] or row[key] == 'Not available':
                            row[key] = None

                df = pd.DataFrame(scraped_data['data'])
                
                # Only process columns if df is not empty
                if not df.empty:
                    columns = df.columns.tolist()
                    data = df.values.tolist()
                else:
                    columns = []
                    data = []

                return render_template('table.html', 
                                       columns=columns,
                                       data=data)
            else:
                return "No flight data found.", 404

    return render_template('index.html', 
                           form_data=form_data, 
                           urls=urls, 
                           error_message=error_message)

def get_airports():
    conn = sqlite3.connect('airports.db')
    cursor = conn.cursor()
    cursor.execute('SELECT name, iata_code from airports')
    results = cursor.fetchall()
    conn.close()
    return results

def similar(a, b):
    return SequenceMatcher(None, a, b).ratio()

@app.route('/search_airports', methods=['GET'])
def search_airports():
    query = request.args.get('query', '').upper()
    print(f"Received search query: {query}")  # Debug print
    airports = get_airports()
    print(f"Total airports: {len(airports)}")  # Debug print
    ranked_airports = sorted(airports, key=lambda airport: max(similar(query, airport[1]), similar(query, airport[0])), reverse=True)
    results = [{"id": airport[1], "text": f"{airport[0]} ({airport[1]})"} for airport in ranked_airports[:10]]
    print(f"Search results: {results}")  # Debug print
    return jsonify(results)

def calculate_date_range(selected_date, use_range=False):
    if not selected_date:
        date = datetime.datetime.today()
    else:
        try:
            date = datetime.datetime.strptime(selected_date, '%Y-%m-%d')
        except ValueError:
            print(f"Invalid date format: {selected_date}. Using today's date.")
            date = datetime.datetime.today()

    destinationday = datetime.datetime.today()
    if use_range:
        date_list = [(date + datetime.timedelta(days=i)).strftime('%Y-%m-%d') for i in range(-1, 2)
                     if (date + datetime.timedelta(days=i)) >= destinationday]
    else:
        date_list = [date.strftime('%Y-%m-%d')]
    return date_list

if __name__ == '__main__':
    app.run(debug=True, port=5007)