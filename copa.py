from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import pandas as pd
import time
from bs4 import BeautifulSoup
from html import unescape
import re
from datetime import datetime, timedelta
import math
import os
import zipfile
import undetected_chromedriver as uc
def create_proxy_extension(proxy_host, proxy_port, proxy_username, proxy_password):
    manifest_json = """
    {
        "version": "1.0.0",
        "manifest_version": 2,
        "name": "Chrome Proxy",
        "permissions": [
            "proxy",
            "tabs",
            "unlimitedStorage",
            "storage",
            "<all_urls>",
            "webRequest",
            "webRequestBlocking"
        ],
        "background": {
            "scripts": ["background.js"]
        },
        "minimum_chrome_version":"22.0.0"
    }
    """

    background_js = """
    var config = {
            mode: "fixed_servers",
            rules: {
              singleProxy: {
                scheme: "http",
                host: "%s",
                port: parseInt(%s)
              },
              bypassList: ["localhost"]
            }
          };

    chrome.proxy.settings.set({value: config, scope: "regular"}, function() {});

    function callbackFn(details) {
        return {
            authCredentials: {
                username: "%s",
                password: "%s"
            }
        };
    }

    chrome.webRequest.onAuthRequired.addListener(
                callbackFn,
                {urls: ["<all_urls>"]},
                ['blocking']
    );
    """ % (proxy_host, proxy_port, proxy_username, proxy_password)

    extension = 'proxy_auth_plugin.zip'
    with zipfile.ZipFile(extension, 'w') as zp:
        zp.writestr("manifest.json", manifest_json)
        zp.writestr("background.js", background_js)
    return extension

def process_copa_url(url):
    proxy_host = "geo.iproyal.com"
    proxy_port = 12321
    proxy_username = "kPMj8aoitK1MVa3e"
    proxy_password = "vNqkGCja6l6jSHdW_country-us"

    proxy_extension = create_proxy_extension(proxy_host, proxy_port, proxy_username, proxy_password)

    chrome_options = uc.ChromeOptions()
    chrome_options.add_extension(proxy_extension)
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--start-maximized")

    driver = uc.Chrome(options=chrome_options)

    try:
        driver.get(url)
        
        try:
            start_time = time.time()
            timeout = 15  # 15 seconds timeout
            
            while time.time() - start_time < timeout:
                # Check for the error message every 2 seconds
                error_message = driver.find_elements(By.CSS_SELECTOR, ".IbeMuiAlert-message.css-1xsto0d")
                if error_message and "We couldn't find flights on the selected dates" in error_message[0].text:
                    print("Error: No flights found for the selected dates.")
                    return {
                        'columns': [],
                        'data': [],
                        'error': "No flights found for the selected dates. Please try different dates."
                    }
                
                # Check if flight data has loaded
                flight_cards = driver.find_elements(By.CSS_SELECTOR, "[data-cy^='generalCard_']")
                if flight_cards:
                    break
                
                time.sleep(0.5)
            
            else:  # This block executes if the while loop completes without breaking
                print("Timeout: Could not load flight data.")
                return {
                    'columns': [],
                    'data': [],
                    'error': "Timeout: Could not load flight data. Please try again later."
                }
            
            # If we've reached here, flight data has loaded. Proceed with scraping.
            
            # Wait for the initial content to load
            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[data-cy^='generalCard_']"))
            )
            
            # Click "View more flight" button until it's no longer available
            while True:
                try:
                    view_more_button = WebDriverWait(driver, 3).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-cy='loadFlights-loadButton']"))
                    )
                    driver.execute_script("arguments[0].click();", view_more_button)
                    time.sleep(2)  # Wait for new content to load
                except (TimeoutException, NoSuchElementException):
                    # Button is no longer available, exit the loop
                    break
            
            # Get the page source after loading all flights
            html_content = driver.page_source
            
            # Parse the HTML content
            decoded_soup = BeautifulSoup(html_content, 'html.parser')
            
            # Define extraction functions
            def extract_text(soup, attr=None, attr_value=None, get_aria_label=False):
                """Extract text or aria-label based on attribute."""
                if attr:
                    element = soup.find(attrs={attr: attr_value})
                    if element:
                        if get_aria_label:
                            return element.get('aria-label', '')
                        else:
                            return element.get_text(strip=True)
                return None

            def extract_iata_code(text):
                """Extract IATA code from the text."""
                if text:
                    return text.split('(')[-1].split(')')[0]
                return None

            def convert_to_24hr(time_str):
                """Convert 12-hour time to 24-hour format."""
                try:
                    if time_str:
                        time_obj = pd.to_datetime(time_str, format='%I:%M %p')
                        return time_obj.strftime('%H:%M')
                except ValueError:
                    return None
                return None

            def convert_to_24hr_with_days(time_str):
                """Convert 12-hour time to 24-hour format and append (+1 days) if applicable."""
                if time_str:
                    # Check for the +1 indicator and remove it for conversion
                    plus_day = "+1" in time_str
                    time_str_clean = time_str.replace("+1", "").strip()
                    try:
                        time_obj = pd.to_datetime(time_str_clean, format='%I:%M %p')
                        time_24hr = time_obj.strftime('%H:%M')
                        if plus_day:
                            return f"{time_24hr} (+1 days)"
                        return time_24hr
                    except ValueError:
                        return None
                return None

            def format_flight_numbers(flight_numbers):
                """Format flight numbers by joining them with commas."""
                if flight_numbers:
                    return ', '.join(flight_numbers.split(' · '))
                return None

            def clean_price(price):
                """Clean up the price by removing 'miles'."""
                if price:
                    return price.replace(' miles', '')
                return None

            def clean_tax(tax):
                """Clean up the tax by removing '+'."""
                if tax:
                    return tax.replace('+ ', '')
                return None

            def combine_price_and_tax(price, tax):
                """Combine price and tax into a single formatted string."""
                if price and tax:
                    return f"{price} + {tax}"
                return None

            def calculate_real_price(miles_required, tax):
                """Calculate the real price based on the miles and tax."""
                miles_required = int(miles_required.replace(',', ''))
                tax = float(tax.split(' ')[0].replace(',', ''))
                cost_per_mile = 0.03  # 3 cents per mile

                def get_bonus_factor(miles):
                    if 5000 <= miles <= 9000:
                        return 1.6
                    elif 10000 <= miles <= 14000:
                        return 1.7
                    elif 15000 <= miles <= 19000:
                        return 1.8
                    elif miles >= 20000:
                        return 1.9
                    else:
                        return 1

                def calculate_purchase(miles):
                    bonus_factor = get_bonus_factor(miles)
                    return miles * cost_per_mile, miles * bonus_factor

                def find_cheapest_combination(target_miles):
                    best_cost = float('inf')
                    best_combination = None

                    for first_purchase in range(5000, 71000, 1000):
                        cost1, miles1 = calculate_purchase(first_purchase)
                        if miles1 >= target_miles:
                            if cost1 < best_cost:
                                best_cost = cost1
                                best_combination = [first_purchase]
                            continue

                        remaining_miles = target_miles - miles1
                        second_purchase = math.ceil(remaining_miles / get_bonus_factor(remaining_miles) / 1000) * 1000
                        second_purchase = max(1000, min(70000, second_purchase))
                        
                        cost2, miles2 = calculate_purchase(second_purchase)
                        total_cost = cost1 + cost2
                        total_miles = miles1 + miles2

                        if total_miles >= target_miles and total_cost < best_cost:
                            best_cost = total_cost
                            best_combination = [first_purchase, second_purchase]

                    return best_cost, best_combination

                total_cost, purchases = find_cheapest_combination(miles_required)
                real_price = total_cost + tax
                return f"${real_price:,.2f}"

            def parse_detailed_info(detailed_info):
                # Extract From and To
                from_match = re.search(r'from (.*?) to', detailed_info)
                to_match = re.search(r'to (.*?) with departure', detailed_info)
                from_city = from_match.group(1) if from_match else ''
                to_city = to_match.group(1) if to_match else ''

                # Extract departure and arrival times
                depart_match = re.search(r'departure time (\d{2}:\d{2} [ap]m)', detailed_info)
                arrive_match = re.search(r'arrival at (\d{2}:\d{2} [ap]m)(\+\d)?', detailed_info)
                
                # Extract date
                date_match = re.search(r'from (\d{2}), (\w+), (\d{4})', detailed_info)
                
                # Extract duration
                duration_match = re.search(r'Total flight duration is (\d+) hours (\d+) minutes', detailed_info)

                if depart_match and arrive_match and date_match and duration_match:
                    depart_time = datetime.strptime(depart_match.group(1), '%I:%M %p')
                    arrive_time = datetime.strptime(arrive_match.group(1), '%I:%M %p')
                    
                    date = datetime.strptime(f"{date_match.group(1)} {date_match.group(2)} {date_match.group(3)}", '%d %B %Y')
                    
                    depart_str = f"{depart_time.strftime('%H:%M')} {date.strftime('%d/%m')}"
                    
                    days_added = int(arrive_match.group(2)[1]) if arrive_match.group(2) else 0
                    arrive_date = date + timedelta(days=days_added)
                    arrive_str = f"{arrive_time.strftime('%H:%M')} {arrive_date.strftime('%d/%m')}"
                    
                    duration = f"{duration_match.group(1)}h{duration_match.group(2)}m"
                    
                    return from_city, to_city, depart_str, arrive_str, duration
                
                return '', '', '', '', ''

            def extract_all_flight_data(soup):
                rows = []
                general_cards = soup.find_all('div', attrs={'data-cy': lambda x: x and x.startswith('generalCard_')})

                for card in general_cards:
                    number = card['data-cy'].split('_')[-1]

                    # Extract the aria-label from the element with data-cy="tripCard_{number}"
                    detailed_info = extract_text(card, attr="data-cy", attr_value=f"tripCard_{number}", get_aria_label=True)

                    # Parse the detailed information
                    from_city, to_city, departs, arrives, duration = parse_detailed_info(detailed_info)

                    # Extract flight number using the correct data-cy attribute
                    flight_number = extract_text(card, attr="data-cy", attr_value=f"tripCard_{number}_codes")

                    # Extract layover information
                    layover = extract_text(card, attr="data-cy", attr_value=f"tripCard_{number}_layovers")
                    if layover:
                        layover = layover.replace("Layover in ", "").replace("Layovers in ", "")

                    economy_price = extract_text(card, attr="data-cy", attr_value=f"economic_{number}_price")
                    economy_tax = extract_text(card, attr="data-cy", attr_value=f"economic_{number}_originalPrice")

                    business_price = extract_text(card, attr="data-cy", attr_value=f"business_{number}_price")
                    business_tax = extract_text(card, attr="data-cy", attr_value=f"business_{number}_originalPrice")

                    economy_combined = combine_price_and_tax(clean_price(economy_price), clean_tax(economy_tax))
                    business_combined = combine_price_and_tax(clean_price(business_price), clean_tax(business_tax))

                    economy_real_price = calculate_real_price(clean_price(economy_price),
                                                                clean_tax(economy_tax)) if economy_combined else ''
                    business_real_price = calculate_real_price(clean_price(business_price),
                                                               clean_tax(business_tax)) if business_combined else ''

                    rows.append([
                        format_flight_numbers(flight_number) if flight_number else '',
                        from_city,
                        to_city,
                        departs,
                        arrives,
                        duration,
                        layover if layover else '',  # Add layover information
                        economy_real_price if economy_real_price else '',
                        business_real_price if business_real_price else '',
                    ])

                return rows

            # Extract and display the updated data
            all_flight_data = extract_all_flight_data(decoded_soup)
            all_flight_df = pd.DataFrame(all_flight_data, columns=[
                "Flight number",
                "From",
                "To",
                "Departs",
                "Arrives",
                "Duration",
                "Layover",  # Add Layover column
                "Economy",
                "Business",
            ])

            # Assuming all_flight_df is your final DataFrame
            if isinstance(all_flight_df, pd.DataFrame):
                data_dict = all_flight_df.to_dict('records')
                columns = all_flight_df.columns.tolist()
            else:
                # If all_flight_df is not a DataFrame, return an empty result
                data_dict = []
                columns = []

            print("Scraped Data:", {'columns': columns, 'data': data_dict[:5]})  # Debug print

            return {
                'columns': columns,
                'data': data_dict
            }
        
        except Exception as e:
            print(f"An error occurred during scraping: {str(e)}")
            return {
                'columns': [],
                'data': [],
                'error': f"An error occurred during scraping: {str(e)}"
            }
    
    finally:
        driver.quit()