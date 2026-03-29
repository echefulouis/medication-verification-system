import json
import boto3
import os
import time
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext

logger = Logger()

dynamodb = boto3.resource('dynamodb')
cloudwatch_client = boto3.client('cloudwatch')
VERIFICATION_TABLE = os.environ['VERIFICATION_TABLE_NAME']
table = dynamodb.Table(VERIFICATION_TABLE)


def scrape_nafdac_greenbook(nafdac_number: str = None, product_name: str = None) -> dict:
    """
    Scrape NAFDAC Greenbook using Selenium with Chrome
    
    Searches by NAFDAC number if provided, otherwise searches by product name
    
    Returns validation result with product details if found
    """
    if not nafdac_number and not product_name:
        logger.warning("No search term provided")
        return {
            "success": False,
            "message": "No NAFDAC number or product name provided"
        }
    
    # Determine search field and term
    if nafdac_number:
        search_field_id = 'search_nrn'
        search_term = nafdac_number
        search_type = "NAFDAC number"
    else:
        search_field_id = 'search_product'
        # Use only the first word to avoid hyphen/space/punctuation issues
        search_term = product_name.split()[0] if product_name and product_name.split() else product_name
        search_type = "product name"
        if search_term != product_name:
            logger.info(f"Using first word from '{product_name}' → searching for '{search_term}'")
    
    logger.info(f"Starting NAFDAC Greenbook scraping for {search_type}: {search_term}")
    
    try:
        # Setup Chrome options for Lambda
        chrome_options = Options()
        chrome_options.add_argument('--headless=new')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--disable-dev-tools')
        chrome_options.add_argument('--no-zygote')
        chrome_options.add_argument('--single-process')
        chrome_options.add_argument('--user-data-dir=/tmp/chrome-user-data')
        chrome_options.add_argument('--data-path=/tmp/chrome-data')
        chrome_options.add_argument('--disk-cache-dir=/tmp/chrome-cache')
        chrome_options.add_argument('--remote-debugging-port=9222')
        
        chrome_options.binary_location = '/opt/chrome-linux64/chrome'
        service = Service(executable_path='/opt/chromedriver-linux64/chromedriver')
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        try:
            logger.info("Navigating to NAFDAC Greenbook...")
            driver.get('https://greenbook.nafdac.gov.ng/')
            
            logger.info(f"Waiting for search field: {search_field_id}")
            wait = WebDriverWait(driver, 10)
            search_input = wait.until(
                EC.presence_of_element_located((By.ID, search_field_id))
            )
            
            logger.info(f"Entering {search_type}: {search_term}")
            search_input.clear()
            search_input.send_keys(search_term)
            
            logger.info("Waiting for results...")
            time.sleep(4)  # Give time for AJAX
            
            try:
                wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'table.data-table tbody tr'))
                )
            except TimeoutException:
                logger.warning("No results found")
                driver.quit()
                return {
                    "success": True,
                    "searchTerm": search_term,
                    "searchType": search_type,
                    "nafdacNumber": nafdac_number,
                    "found": False,
                    "message": f"Product not found in NAFDAC Greenbook (searched by {search_type})"
                }
            
            logger.info("Extracting product data...")
            rows = driver.find_elements(By.CSS_SELECTOR, 'table.data-table tbody tr')
            
            results = []
            for row in rows:
                cells = row.find_elements(By.TAG_NAME, 'td')
                if len(cells) >= 10:
                    result = {
                        'product_name': cells[0].text.strip(),
                        'active_ingredients': cells[1].text.strip(),
                        'product_category': cells[2].text.strip(),
                        'nrn': cells[3].text.strip(),
                        'status': cells[9].text.strip(),
                    }
                    
                    # Filter: if searching by NAFDAC number, only include exact matches
                    if nafdac_number:
                        if result['nrn'].upper() == nafdac_number.upper():
                            results.append(result)
                            logger.info(f"Exact match found: {result['product_name']} (NRN: {result['nrn']})")
                        else:
                            logger.info(f"Skipping non-match: {result['nrn']} != {nafdac_number}")
                    else:
                        # For product name search, include all results
                        results.append(result)
                        logger.info(f"Found product by name: {result['product_name']}")
            
            driver.quit()
            
            if results:
                return {
                    "success": True,
                    "searchTerm": search_term,
                    "searchType": search_type,
                    "nafdacNumber": nafdac_number,
                    "found": True,
                    "results": results
                }
            else:
                return {
                    "success": True,
                    "searchTerm": search_term,
                    "searchType": search_type,
                    "nafdacNumber": nafdac_number,
                    "found": False,
                    "message": f"Product not found in NAFDAC Greenbook (searched by {search_type})"
                }
                
        except Exception as e:
            driver.quit()
            raise e
            
    except Exception as e:
        logger.error(f"Error scraping NAFDAC Greenbook: {str(e)}")
        return {
            "success": False,
            "error": f"Failed to validate: {str(e)}",
            "message": "Unable to connect to NAFDAC Greenbook. Please try again later."
        }


def store_verification_result(verification_id: str, timestamp: str, image_key: str, 
                              nafdac_number: str, validation_result: dict,
                              geolocation: dict = None) -> None:
    """Store verification result in DynamoDB"""
    geo_data = geolocation or {}
    item = {
        'verificationId': verification_id,
        'timestamp': timestamp,
        'imageKey': image_key,
        'validationResult': validation_result,
        'location': {
            'countryCode': geo_data.get('country_code', 'Unknown'),
            'countryName': geo_data.get('country_name', 'Unknown'),
            'region': geo_data.get('region', 'Unknown'),
        },
        'sourceIp': geo_data.get('source_ip', 'Unknown'),
        'ttl': int(datetime.utcnow().timestamp()) + (90 * 24 * 60 * 60)  # 90 days TTL
    }
    
    # Only add nafdacNumber if it's not None (GSI requires non-null values)
    if nafdac_number:
        item['nafdacNumber'] = nafdac_number
    
    table.put_item(Item=item)
    logger.info(f"Verification result stored: {verification_id}")


@logger.inject_lambda_context
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    """
    NAFDAC Validator Lambda Handler (Container)
    
    Validates NAFDAC number by scraping Greenbook and stores result in DynamoDB
    
    Input:
    {
        "verificationId": "uuid",
        "timestamp": "ISO8601_timestamp",
        "imageKey": "s3_key",
        "nafdacNumber": "nafdac_number_to_validate"
    }
    
    Output:
    {
        "verificationId": "uuid",
        "timestamp": "ISO8601_timestamp",
        "imageKey": "s3_key",
        "nafdacNumber": "nafdac_number",
        "validationResult": {...}
    }
    """
    try:
        logger.info(f"Received event: {json.dumps(event)}")
        logger.info(f"Lambda context: function_name={context.function_name}, memory={context.memory_limit_in_mb}MB, timeout={context.get_remaining_time_in_millis()}ms")
        
        # Parse request body
        if 'body' in event:
            body = json.loads(event['body']) if isinstance(event['body'], str) else event['body']
        else:
            body = event
        
        logger.info(f"Parsed body: {json.dumps(body)}")
        
        verification_id = body.get('verificationId')
        timestamp = body.get('timestamp')
        image_key = body.get('imageKey')
        nafdac_number = body.get('nafdacNumber')
        product_name = body.get('productName')
        geolocation = body.get('geolocation')
        
        logger.info(f"Processing verification: ID={verification_id}, NAFDAC={nafdac_number}, Product={product_name}")
        
        # Emit custom metrics for direct /validate calls (manual input from frontend)
        # Note: geolocation metrics are handled by the workflow orchestrator
        
        if not verification_id or not timestamp:
            error_result = {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Missing required fields'})
            }
            logger.error(f"Returning error response: {json.dumps(error_result)}")
            return error_result
        
        # Validate NAFDAC number or search by product name
        logger.info(f"Starting validation for NAFDAC number: {nafdac_number} or product name: {product_name}")
        if nafdac_number or product_name:
            validation_result = scrape_nafdac_greenbook(
                nafdac_number=nafdac_number,
                product_name=product_name
            )
            logger.info(f"Validation result: {json.dumps(validation_result)}")
        else:
            validation_result = {
                "success": False,
                "message": "No NAFDAC number or product name provided"
            }
            logger.warning("No NAFDAC number or product name provided")
        
        # Store result in DynamoDB
        logger.info(f"Storing result in DynamoDB for verification ID: {verification_id}")
        store_verification_result(
            verification_id=verification_id,
            timestamp=timestamp,
            image_key=image_key,
            nafdac_number=nafdac_number,
            validation_result=validation_result,
            geolocation=geolocation
        )
        logger.info("Successfully stored in DynamoDB")
        
        response = {
            'verificationId': verification_id,
            'timestamp': timestamp,
            'imageKey': image_key,
            'nafdacNumber': nafdac_number,
            'productName': product_name,
            'validationResult': validation_result
        }
        
        result = {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(response)
        }
        
        logger.info(f"Returning response: {json.dumps(result)}")
        return result
        
    except Exception as e:
        logger.exception("Error validating NAFDAC number")
        error_result = {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': str(e)})
        }
        logger.error(f"Returning error response: {json.dumps(error_result)}")
        return error_result
