from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import json
import time
import os

def scrape_nafdac(nafdac_number):
    # Setup Chrome options
    chrome_options = Options()
    chrome_options.add_argument('--headless')  # Run in background
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    
    # Initialize the driver
    driver = webdriver.Chrome(options=chrome_options)
    
    try:
        # Navigate to the website
        driver.get('https://greenbook.nafdac.gov.ng/')
        
        # Wait for the search input to be present
        wait = WebDriverWait(driver, 10)
        search_input = wait.until(
            EC.presence_of_element_located((By.ID, 'search_nrn'))
        )
        
        # Enter the NAFDAC number
        search_input.clear()
        search_input.send_keys(nafdac_number)
        
        # Wait for the table to load with results
        time.sleep(3)  # Give time for AJAX to complete
        
        # Wait for table rows to appear
        wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'table.data-table tbody tr'))
        )
        
        # Extract data from the table
        results = []
        rows = driver.find_elements(By.CSS_SELECTOR, 'table.data-table tbody tr')
        
        for row in rows:
            cells = row.find_elements(By.TAG_NAME, 'td')
            if len(cells) >= 10:
                result = {
                    'product_name': cells[0].text,
                    'active_ingredients': cells[1].text,
                    'product_category': cells[2].text,
                    'nrn': cells[3].text,
                    'status': cells[9].text,
                }
                results.append(result)
        
        return results
        
    finally:
        driver.quit()

# Main execution
if __name__ == '__main__':
    # Delete previous items.json if it exists
    if os.path.exists('items.json'):
        os.remove('items.json')
    
    nafdac_number = 'a4-101466'
    results = scrape_nafdac(nafdac_number)
    
    # Save to JSON file
    with open('items.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"Scraped {len(results)} items")
    for item in results:
        print(item)