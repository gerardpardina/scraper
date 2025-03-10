import streamlit as st
import pandas as pd
import json
import asyncio
from datetime import datetime, timedelta
import re
from httpx import AsyncClient
import numpy as np
import altair as alt
import os
import logging
from typing import List, Dict, Any, Optional

# Configure logging2
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("hostel_scraper.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("hostel_scraper")

# Set page configuration
st.set_page_config(
    page_title="Barcelona Hostel Analysis",
    page_icon="🏨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Constants
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36",
}

# Predefined hostels that will always be available
DEFAULT_HOSTELS = [
    {
        "name": "Hostal Ramos",
        "type": "Privado",
        "url": "https://www.booking.com/hotel/es/hostal-ramos.es.html"
    },
    {
        "name": "Hostal Santa Ana",
        "type": "Hibrido",
        "url": "https://www.booking.com/hotel/es/hostal-santa-ana.es.html"
    },
    {
        "name": "Hostal Europa",
        "type": "Hibrido",
        "url": "https://www.booking.com/hotel/es/hostal-europa.es.html"
    },
    {
        "name": "Hostal Levante Barcelona",
        "type": "Privado",
        "url": "https://www.booking.com/hotel/es/hostal-levante-s-c-p.es.html"
    },
    {
        "name": "Hostal Nuevo Colon",
        "type": "Hibrido",
        "url": "https://www.booking.com/hotel/es/hostal-nuevo-colon.es.html"
    },
    {
        "name": "Hostal Benidorm",
        "type": "Privado",
        "url": "https://www.booking.com/hotel/es/hostal-benidorm.es.html"
    },
    {
        "name": "Hostal Fina",
        "type": "Privado",
        "url": "https://www.booking.com/hotel/es/hostal-fina.es.html"
    },
    {
        "name": "Hostal Paris",
        "type": "Privado",
        "url": "https://www.booking.com/hotel/es/hostal-paris.es.html"
    },
    {
        "name": "Pensión Iznájar Barcelona",
        "type": "Privado",
        "url": "https://www.booking.com/hotel/es/hostal-iznajar-barcelona.es.html"
    },
    {
        "name": "Hotel Lloret Ramblas",
        "type": "Privado",
        "url": "https://www.booking.com/hotel/es/lloret.es.html"
    },
    {
        "name": "Hostal Lausanne",
        "type": "Privado",
        "url": "https://www.booking.com/hotel/es/hostal-lausanne.es.html"
    },
    {
        "name": "Hostal Hera",
        "type": "Privado",
        "url": "https://www.booking.com/hotel/es/pension-francia.es.html"
    },
    {
        "name": "Hostal Marenostrum",
        "type": "Privado",
        "url": "https://www.booking.com/hotel/es/hostal-mare-nostrum.es.html"
    },
    {
        "name": "Hotel Lyon",
        "type": "Privado",
        "url": "https://www.booking.com/hotel/es/lyon.es.html"
    },
    {
        "name": "Pensión 45",
        "type": "Compartido",
        "url": "https://www.booking.com/hotel/es/pension-45.es.html"
    },
    {
        "name": "Hostal Capitol Ramblas",
        "type": "Compartido",
        "url": "https://www.booking.com/hotel/es/hostal-capitol-ramblas.es.html"
    }
]

# Debug mode toggle
def toggle_debug_mode():
    st.session_state.debug_mode = not st.session_state.get('debug_mode', False)
    if st.session_state.debug_mode:
        logger.setLevel(logging.DEBUG)
        logger.debug("Debug mode enabled")
    else:
        logger.setLevel(logging.INFO)
        logger.info("Debug mode disabled")

# Initialize session state
if "hostel_data" not in st.session_state:
    st.session_state.hostel_data = []

# Initialize editable hostel list in session state if not present
if "editable_hostels" not in st.session_state:
    st.session_state.editable_hostels = DEFAULT_HOSTELS.copy()

# Initialize custom hostels if not present
if "custom_hostels" not in st.session_state:
    st.session_state.custom_hostels = []

# Initialize editing state
if "editing_hostel" not in st.session_state:
    st.session_state.editing_hostel = None
if "editing_index" not in st.session_state:
    st.session_state.editing_index = -1

if "scraping_results" not in st.session_state:
    st.session_state.scraping_results = []

if "debug_mode" not in st.session_state:
    st.session_state.debug_mode = False

# Function to load hostel data from JSON
def load_hostel_data(file_path=None):
    # Always start with the current editable predefined hostels
    hostels = st.session_state.editable_hostels.copy()
    
    # If file_path is None, return only predefined hostels
    if file_path is None:
        logger.info(f"Using {len(hostels)} predefined hostels.")
        return hostels

    # Try to load additional hostels from the specified file
    try:
        logger.info(f"Attempting to load additional hostel data from: {file_path}")
        st.info(f"Attempting to load additional hostels from: {file_path}")
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Extract hostels from the data and convert 'link' property to 'url'
        additional_hostels = data.get('hostels', [])
        if not additional_hostels:
            logger.warning("No additional hostels found in the JSON file or invalid format.")
            st.warning("No additional hostels found in the JSON file or invalid format.")
            return hostels
            
        # Make sure every hostel has a URL property
        for hostel in additional_hostels:
            if 'link' in hostel and 'url' not in hostel:
                hostel['url'] = hostel['link']
            
            # Verify essential data
            if not hostel.get('url') and not hostel.get('link'):
                logger.warning(f"Missing URL for hostel: {hostel.get('name', 'Unknown')}")
                st.warning(f"Missing URL for hostel: {hostel.get('name', 'Unknown')}")
            else:
                # Only add hostels that have a URL
                hostels.append(hostel)
                
        logger.info(f"Successfully loaded {len(hostels)} hostels total ({len(hostels) - len(st.session_state.editable_hostels)} additional from file).")
        st.success(f"Successfully loaded {len(hostels)} hostels total ({len(hostels) - len(st.session_state.editable_hostels)} additional from file).")
        return hostels
    except FileNotFoundError:
        logger.error(f"Error: File '{file_path}' not found. Using only predefined hostels.")
        st.error(f"Error: File '{file_path}' not found. Using only predefined hostels.")
        # Try alternative filenames
        alternatives = ['hotels predefined.json', 'hotels_predefined.json', 'Hotels Predefined.json']
        for alt_path in alternatives:
            if alt_path != file_path and os.path.exists(alt_path):
                logger.info(f"Found alternative file: {alt_path}. Try changing the filename parameter.")
                st.info(f"Found alternative file: {alt_path}. Try changing the filename parameter.")
        return hostels
    except json.JSONDecodeError:
        logger.error(f"Error: '{file_path}' is not a valid JSON file. Using only predefined hostels.")
        st.error(f"Error: '{file_path}' is not a valid JSON file. Using only predefined hostels.")
        return hostels
    except Exception as e:
        logger.error(f"Unexpected error loading hostels: {str(e)}. Using only predefined hostels.")
        st.error(f"Unexpected error loading hostels: {str(e)}. Using only predefined hostels.")
        return hostels

# Parse hotel HTML to extract name
def parse_hotel(html):
    # Extract the hotel name using regex
    hotel_name_match = re.search(r'hotelName:\s*"(.+?)"', html)
    if hotel_name_match:
        hotel_name = hotel_name_match.group(1)
    else:
        # Try alternative pattern that might be in the URL
        url_match = re.search(r'hotel/\w+/([^.]+)', html)
        if url_match:
            # Convert URL format (e.g., "sixtytwo-barcelona") to readable name
            hotel_name = ' '.join(url_match.group(1).split('-')).title()
        else:
            hotel_name = "Unknown Hotel"
            
    return {
        "name": hotel_name
    }

# Parse price data into a dataframe
def parse_hotel_prices(price_data):
    if not price_data:
        return pd.DataFrame()
    
    # Create a DataFrame from the price data
    df = pd.DataFrame(price_data)
    
    # Clean and convert the price format
    if 'avgPriceFormatted' in df.columns:
        # Extract numeric values from formatted prices
        df['price'] = df['avgPriceFormatted'].str.extract(r'(\d+\.?\d*)').astype(float)
    
    # Convert checkin to datetime
    if 'checkin' in df.columns:
        df['date'] = pd.to_datetime(df['checkin'])
    
    return df

# Scrape hotels
async def scrape_hotels(hostels, session, start_date, end_date=None, num_adults=2):
    async def scrape_hostel(hostel):
        # Use 'url' property if available, otherwise use 'link'
        url = hostel.get('url', hostel.get('link', ''))
        
        if not url:
            logger.warning(f"Missing URL for hostel: {hostel.get('name', 'Unknown Hostel')}")
            print(f"Missing URL for hostel: {hostel.get('name', 'Unknown Hostel')}")
            return {
                "name": hostel.get('name', 'Unknown Hotel'),
                "type": hostel.get('type', 'Unknown Type'),
                "url": url, 
                "error": "Missing URL"
            }
            
        try:
            logger.debug(f"Fetching URL: {url}")
            resp = await session.get(url)
            
            # Check if the response was successful
            if resp.status_code != 200:
                logger.error(f"Error fetching URL {url}: HTTP status {resp.status_code}")
                print(f"Error fetching URL {url}: HTTP status {resp.status_code}")
                return {
                    "name": hostel.get('name', 'Unknown Hotel'),
                    "type": hostel.get('type', 'Unknown Type'),
                    "url": url, 
                    "error": f"HTTP status {resp.status_code}"
                }
                
            # Parse hotel details
            hotel_info = parse_hotel(resp.text)
            hotel_info["url"] = str(resp.url)
            hotel_info["type"] = hostel.get('type', 'Unknown Type')
            hotel_info["original_name"] = hostel.get('name', 'Unknown Hotel')
            
            # For background requests we need to find some variables
            try:
                _hotel_country = re.findall(r'hotelCountry:\s*"(.+?)"', resp.text)[0]
            except (IndexError, ValueError):
                _hotel_country = "unknown"
                
            try:
                _hotel_name = re.findall(r'hotelName:\s*"(.+?)"', resp.text)[0]
            except (IndexError, ValueError):
                # Try to extract from URL
                url_match = re.search(r'hotel/\w+/([^.]+)', str(resp.url))
                if url_match:
                    _hotel_name = ' '.join(url_match.group(1).split('-')).title()
                else:
                    _hotel_name = hotel_info["original_name"]
            
            try:
                _csrf_token = re.findall(r"b_csrf_token:\s*'(.+?)'", resp.text)[0]
            except (IndexError, ValueError):
                _csrf_token = ""
                
            # Ensure the hotel name is properly set
            if _hotel_name and not hotel_info.get("name"):
                hotel_info["name"] = _hotel_name
                
            # Scrape for 2 adults
            try:
                price_data_2_adults = await scrape_prices(
                    hotel_name=_hotel_name, 
                    hotel_country=_hotel_country, 
                    csrf_token=_csrf_token, 
                    num_adults=2,
                    start_date=start_date,
                    end_date=end_date
                )
                hotel_info["price_2_adults"] = price_data_2_adults
            except Exception as e:
                print(f"Error fetching 2 adult prices for {_hotel_name}: {str(e)}")
                hotel_info["price_2_adults"] = []
                hotel_info["price_2_adults_error"] = str(e)
            
            # Scrape for 1 adult
            try:
                price_data_1_adult = await scrape_prices(
                    hotel_name=_hotel_name, 
                    hotel_country=_hotel_country, 
                    csrf_token=_csrf_token, 
                    num_adults=1,
                    start_date=start_date,
                    end_date=end_date
                )
                hotel_info["price_1_adult"] = price_data_1_adult
            except Exception as e:
                print(f"Error fetching 1 adult prices for {_hotel_name}: {str(e)}")
                hotel_info["price_1_adult"] = []
                hotel_info["price_1_adult_error"] = str(e)
                
            return hotel_info
            
        except Exception as e:
            # Log the error but don't fail the entire process
            error_msg = f"Error processing URL {url}: {str(e)}"
            print(error_msg)
            return {
                "name": hostel.get('name', 'Unknown Hotel'),
                "type": hostel.get('type', 'Unknown Type'),
                "url": url, 
                "error": str(e)
            }

    async def scrape_prices(hotel_name, hotel_country, csrf_token, num_adults, start_date, end_date=None):
        # Calculate days to check
        if end_date:
            price_n_days = (end_date - start_date).days + 1
            logger.debug(f"Scraping date range: {start_date} to {end_date} ({price_n_days} days)")
        else:
            price_n_days = 1
            logger.debug(f"Scraping single date: {start_date}")
            
        # Ensure price_n_days is reasonable (booking.com typically limits to ~30 days)
        if price_n_days > 30:
            logger.warning(f"Date range too long ({price_n_days} days). Limiting to 30 days.")
            price_n_days = 30
            
        try:
            # Make GraphQL query
            gql_body = json.dumps(
                {
                    "operationName": "AvailabilityCalendar",
                    "variables": {
                        "input": {
                            "travelPurpose": 2,
                            "pagenameDetails": {
                                "countryCode": hotel_country,
                                "pagename": hotel_name,
                            },
                            "searchConfig": {
                                "searchConfigDate": {
                                    "startDate": start_date.strftime("%Y-%m-%d"),
                                    "amountOfDays": price_n_days,
                                },
                                "nbAdults": num_adults,
                                "nbRooms": 1,
                            },
                        }
                    },
                    "extensions": {},
                    "query": "query AvailabilityCalendar($input: AvailabilityCalendarQueryInput!) {\n  availabilityCalendar(input: $input) {\n    ... on AvailabilityCalendarQueryResult {\n      hotelId\n      days {\n        available\n        avgPriceFormatted\n        checkin\n        minLengthOfStay\n        __typename\n      }\n      __typename\n    }\n    ... on AvailabilityCalendarQueryError {\n      message\n      __typename\n    }\n    __typename\n  }\n}\n",
                },
                separators=(",", ":"),
            )
            
            logger.debug(f"Sending GraphQL query for {hotel_name} with {num_adults} adults")
            
            # Scrape booking GraphQL
            result_price = await session.post(
                "https://www.booking.com/dml/graphql?lang=en-gb",
                content=gql_body,
                headers={
                    "content-type": "application/json",
                    "x-booking-csrf-token": csrf_token,
                    "origin": "https://www.booking.com",
                },
            )
            
            price_data = json.loads(result_price.content)
            
            # Check if we got a valid response
            if "data" not in price_data or "availabilityCalendar" not in price_data["data"]:
                logger.error(f"Invalid response format from Booking.com API: {price_data}")
                return []
                
            if "days" not in price_data["data"]["availabilityCalendar"]:
                logger.error(f"No 'days' data in Booking.com response: {price_data}")
                return []
                
            days_data = price_data["data"]["availabilityCalendar"]["days"]
            logger.debug(f"Successfully fetched {len(days_data)} days of price data")
            
            return days_data
            
        except Exception as e:
            logger.error(f"Error in GraphQL request: {str(e)}", exc_info=True)
            raise e

    hostels_data = await asyncio.gather(*[scrape_hostel(hostel) for hostel in hostels])
    return hostels_data

# Process the scraped data to add calculated fields
def process_hostel_data(hostels_data, selected_date=None, end_date=None):
    results = []
    error_hostels = []
    
    # Determine if we're dealing with a date range
    is_date_range = end_date is not None and end_date != selected_date
    
    for hostel in hostels_data:
        if 'error' in hostel:
            error_hostels.append(hostel)
            continue
            
        result = {
            'Nombre Hotel': hostel.get('original_name', hostel.get('name', 'Unknown Hotel')),
            'Tipo': hostel.get('type', 'Unknown Type'),
            'URL': hostel.get('url', '')
        }
        
        # Process prices for 2 adults
        if 'price_2_adults' in hostel and hostel['price_2_adults']:
            df_2_adults = parse_hotel_prices(hostel['price_2_adults'])
            
            if not df_2_adults.empty:
                # Filtramos valores de 0 (sin disponibilidad) antes de calcular
                df_2_adults_filtered = df_2_adults[df_2_adults['price'] > 0.01]
                
                # Logging for debugging
                total_days = len(df_2_adults)
                valid_days = len(df_2_adults_filtered)
                filtered_out = total_days - valid_days
                
                if filtered_out > 0:
                    logger.info(f"Hotel: {hostel.get('name')} - Filtered out {filtered_out} days with no availability (zero prices) out of {total_days} total days")
                
                # Si después de filtrar no hay valores, no agregamos precios
                if df_2_adults_filtered.empty:
                    logger.warning(f"No hay precios válidos (>0) para 2 adultos en {hostel.get('name')}")
                    continue
                
                # Si tenemos una fecha específica y NO es un rango de fechas, filtramos para esa fecha
                if selected_date and not is_date_range:
                    df_date_filtered = df_2_adults_filtered[df_2_adults_filtered['date'].dt.date == selected_date]
                    
                    # Si no hay precios para la fecha específica después de filtrar los ceros
                    if df_date_filtered.empty:
                        logger.warning(f"No hay disponibilidad para 2 adultos en {hostel.get('name')} en la fecha {selected_date}")
                        continue
                    
                    df_2_adults_filtered = df_date_filtered
                    price_method = "min"  # Para día único, usamos el precio mínimo
                else:
                    # Para rango de fechas, calculamos el promedio diario (ya tenemos filtrados los ceros)
                    price_method = "mean"
                    # Save information about available days
                    available_days_count = len(df_2_adults_filtered)
                    total_days_in_range = (end_date - selected_date).days + 1 if end_date else 1
                    result['Días con Disponibilidad'] = available_days_count
                    result['Total Días en Rango'] = total_days_in_range
                    
                if not df_2_adults_filtered.empty:
                    # Obtenemos el precio según el método (mínimo o media)
                    if price_method == "min":
                        price_2_adults = df_2_adults_filtered['price'].min()
                    else:
                        price_2_adults = df_2_adults_filtered['price'].mean()
                    
                    # Apply pricing rules based on hostel type
                    if hostel.get('type') == 'Privado':
                        # Private room price is scraped, shared room is calculated
                        result['Precio Hab Baño Privado 2 Adultos'] = round(price_2_adults, 2)
                        result['Precio Hab Baño Compartido 2 Adultos'] = round(price_2_adults * 0.8, 2)
                        result['Precio Hab Baño Compartido 2 Adultos (Calculado)'] = True
                        
                        # Cálculo del precio sin tasa y sin interés (2 adultos)
                        precio_sin_tasa_privado = (price_2_adults - (5.5 * 2))
                        interes_privado = precio_sin_tasa_privado * 0.08
                        precio_sin_tasa_privado_final = precio_sin_tasa_privado - interes_privado
                        result['Precio Sin Tasa Privado 2 Adultos'] = round(precio_sin_tasa_privado_final, 2)
                        result['Tasa Turística 2 Adultos'] = 5.5 * 2
                        result['Interés 8% Privado 2 Adultos'] = round(interes_privado, 2)
                        
                        precio_sin_tasa_compartido = (price_2_adults * 0.8 - (5.5 * 2))
                        interes_compartido = precio_sin_tasa_compartido * 0.08
                        precio_sin_tasa_compartido_final = precio_sin_tasa_compartido - interes_compartido
                        result['Precio Sin Tasa Compartido 2 Adultos'] = round(precio_sin_tasa_compartido_final, 2)
                        result['Interés 8% Compartido 2 Adultos'] = round(interes_compartido, 2)
                        
                    elif hostel.get('type') == 'Compartido':
                        # Shared room price is scraped, private room is calculated
                        result['Precio Hab Baño Compartido 2 Adultos'] = round(price_2_adults, 2)
                        result['Precio Hab Baño Privado 2 Adultos'] = round(price_2_adults * 1.2, 2)
                        result['Precio Hab Baño Privado 2 Adultos (Calculado)'] = True
                        
                        # Cálculo del precio sin tasa y sin interés (2 adultos)
                        precio_sin_tasa_compartido = (price_2_adults - (5.5 * 2))
                        interes_compartido = precio_sin_tasa_compartido * 0.08
                        precio_sin_tasa_compartido_final = precio_sin_tasa_compartido - interes_compartido
                        result['Precio Sin Tasa Compartido 2 Adultos'] = round(precio_sin_tasa_compartido_final, 2)
                        result['Tasa Turística 2 Adultos'] = 5.5 * 2
                        result['Interés 8% Compartido 2 Adultos'] = round(interes_compartido, 2)
                        
                        precio_sin_tasa_privado = (price_2_adults * 1.2 - (5.5 * 2))
                        interes_privado = precio_sin_tasa_privado * 0.08
                        precio_sin_tasa_privado_final = precio_sin_tasa_privado - interes_privado
                        result['Precio Sin Tasa Privado 2 Adultos'] = round(precio_sin_tasa_privado_final, 2)
                        result['Interés 8% Privado 2 Adultos'] = round(interes_privado, 2)
                        
                    elif hostel.get('type') == 'Híbrido' or hostel.get('type') == 'Hibrido':
                        # Assume scraped price is for shared rooms, calculate private
                        result['Precio Hab Baño Compartido 2 Adultos'] = round(price_2_adults, 2)
                        result['Precio Hab Baño Privado 2 Adultos'] = round(price_2_adults * 1.2, 2)
                        result['Precio Hab Baño Privado 2 Adultos (Calculado)'] = True
                        
                        # Cálculo del precio sin tasa y sin interés (2 adultos)
                        precio_sin_tasa_compartido = (price_2_adults - (5.5 * 2))
                        interes_compartido = precio_sin_tasa_compartido * 0.08
                        precio_sin_tasa_compartido_final = precio_sin_tasa_compartido - interes_compartido
                        result['Precio Sin Tasa Compartido 2 Adultos'] = round(precio_sin_tasa_compartido_final, 2)
                        result['Tasa Turística 2 Adultos'] = 5.5 * 2
                        result['Interés 8% Compartido 2 Adultos'] = round(interes_compartido, 2)
                        
                        precio_sin_tasa_privado = (price_2_adults * 1.2 - (5.5 * 2))
                        interes_privado = precio_sin_tasa_privado * 0.08
                        precio_sin_tasa_privado_final = precio_sin_tasa_privado - interes_privado
                        result['Precio Sin Tasa Privado 2 Adultos'] = round(precio_sin_tasa_privado_final, 2)
                        result['Interés 8% Privado 2 Adultos'] = round(interes_privado, 2)
        
        # Process prices for 1 adult
        if 'price_1_adult' in hostel and hostel['price_1_adult']:
            df_1_adult = parse_hotel_prices(hostel['price_1_adult'])
            
            if not df_1_adult.empty:
                # Filtramos valores de 0 (sin disponibilidad) antes de calcular
                df_1_adult_filtered = df_1_adult[df_1_adult['price'] > 0.01]
                
                # Logging for debugging
                total_days = len(df_1_adult)
                valid_days = len(df_1_adult_filtered)
                filtered_out = total_days - valid_days
                
                if filtered_out > 0:
                    logger.info(f"Hotel: {hostel.get('name')} - Filtered out {filtered_out} days with no availability (zero prices) for 1 adult out of {total_days} total days")
                
                # Si después de filtrar no hay valores, no agregamos precios
                if df_1_adult_filtered.empty:
                    logger.warning(f"No hay precios válidos (>0) para 1 adulto en {hostel.get('name')}")
                    continue
                
                # Si tenemos una fecha específica y NO es un rango de fechas, filtramos para esa fecha
                if selected_date and not is_date_range:
                    df_date_filtered = df_1_adult_filtered[df_1_adult_filtered['date'].dt.date == selected_date]
                    
                    # Si no hay precios para la fecha específica después de filtrar los ceros
                    if df_date_filtered.empty:
                        logger.warning(f"No hay disponibilidad para 1 adulto en {hostel.get('name')} en la fecha {selected_date}")
                        continue
                    
                    df_1_adult_filtered = df_date_filtered
                    price_method = "min"  # Para día único, usamos el precio mínimo
                else:
                    # Para rango de fechas, calculamos el promedio diario (ya tenemos filtrados los ceros)
                    price_method = "mean"
                    # Save information about available days
                    available_days_count = len(df_1_adult_filtered)
                    total_days_in_range = (end_date - selected_date).days + 1 if end_date else 1
                    result['Días con Disponibilidad 1A'] = available_days_count
                    result['Total Días en Rango 1A'] = total_days_in_range
                
                if not df_1_adult_filtered.empty:
                    # Obtenemos el precio según el método (mínimo o media)
                    if price_method == "min":
                        price_1_adult = df_1_adult_filtered['price'].min()
                    else:
                        price_1_adult = df_1_adult_filtered['price'].mean()
                    
                    # Apply pricing rules based on hostel type
                    if hostel.get('type') == 'Privado':
                        # Private room price is scraped, shared room is calculated
                        # Eliminamos el cálculo de baño privado para 1 adulto
                        result['Precio Hab Baño Compartido 1 Adulto'] = round(price_1_adult * 0.8, 2)
                        
                        # Cálculo del precio sin tasa y sin interés (1 adulto) - solo para compartido
                        precio_sin_tasa_compartido = (price_1_adult * 0.8 - 5.5)
                        interes_compartido = precio_sin_tasa_compartido * 0.08
                        precio_sin_tasa_compartido_final = precio_sin_tasa_compartido - interes_compartido
                        result['Precio Sin Tasa Compartido 1 Adulto'] = round(precio_sin_tasa_compartido_final, 2)
                        result['Tasa Turística 1 Adulto'] = 5.5
                        result['Interés 8% Compartido 1 Adulto'] = round(interes_compartido, 2)
                        
                    elif hostel.get('type') == 'Compartido':
                        # Shared room price is scraped
                        result['Precio Hab Baño Compartido 1 Adulto'] = round(price_1_adult, 2)
                        
                        # Cálculo del precio sin tasa y sin interés (1 adulto) - solo para compartido
                        precio_sin_tasa_compartido = (price_1_adult - 5.5)
                        interes_compartido = precio_sin_tasa_compartido * 0.08
                        precio_sin_tasa_compartido_final = precio_sin_tasa_compartido - interes_compartido
                        result['Precio Sin Tasa Compartido 1 Adulto'] = round(precio_sin_tasa_compartido_final, 2)
                        result['Tasa Turística 1 Adulto'] = 5.5
                        result['Interés 8% Compartido 1 Adulto'] = round(interes_compartido, 2)
                        
                    elif hostel.get('type') == 'Híbrido' or hostel.get('type') == 'Hibrido':
                        # Assume scraped price is for shared rooms
                        result['Precio Hab Baño Compartido 1 Adulto'] = round(price_1_adult, 2)
                        
                        # Cálculo del precio sin tasa y sin interés (1 adulto) - solo para compartido
                        precio_sin_tasa_compartido = (price_1_adult - 5.5)
                        interes_compartido = precio_sin_tasa_compartido * 0.08
                        precio_sin_tasa_compartido_final = precio_sin_tasa_compartido - interes_compartido
                        result['Precio Sin Tasa Compartido 1 Adulto'] = round(precio_sin_tasa_compartido_final, 2)
                        result['Tasa Turística 1 Adulto'] = 5.5
                        result['Interés 8% Compartido 1 Adulto'] = round(interes_compartido, 2)
        
        # Check if prices were found
        if not any(key.startswith('Precio') for key in result.keys()):
            result['Error'] = 'No pricing data available for this hostel'
            
        results.append(result)
    
    # Return both the processed results and any error hostels
    return results, error_hostels

# Function to run the scraping process
async def run_scrape(hostels, start_date, end_date=None):
    async with AsyncClient(headers=HEADERS) as session:
        hostels_data = await scrape_hotels(
            hostels,
            session,
            start_date,
            end_date
        )
        # Procesar los datos hosteleros para calcular precios derivados
        return process_hostel_data(hostels_data, start_date, end_date)

# Main application
def main():
    st.title("🏨 Barcelona Hostel Price Analysis")
    
    # Add debug mode option
    with st.expander("Debug Options"):
        debug_mode = st.checkbox("Enable Debug Mode")
        if debug_mode:
            st.markdown("### Debug Test for Hostal Ramos")
            if st.button("Test Hostal Ramos (March 11, 2025)"):
                with st.spinner("Testing specific price for Hostal Ramos..."):
                    test_hostel = {
                        "name": "Hostal Ramos",
                        "type": "Privado",
                        "url": "https://www.booking.com/hotel/es/hostal-ramos.html"
                    }
                    test_date = datetime(2025, 3, 11)
                    
                    # Run test
                    async def run_test():
                        async with AsyncClient(headers=HEADERS) as session:
                            result = await scrape_hotels([test_hostel], session, test_date)
                            return result
                    
                    test_result = asyncio.run(run_test())
                    
                    # Display results
                    for hotel in test_result:
                        if 'error' in hotel:
                            st.error(f"Error: {hotel['error']}")
                            continue
                            
                        st.markdown(f"**Hotel Name:** {hotel.get('name', 'Unknown')}")
                        st.markdown(f"**Hotel Type:** {hotel.get('type', 'Unknown')}")
                        
                        # Check 2 adults pricing data
                        if 'price_2_adults' in hotel and hotel['price_2_adults']:
                            price_df = parse_hotel_prices(hotel['price_2_adults'])
                            st.dataframe(price_df)
                            
                            # Filter for the specific test date
                            filtered_prices = price_df[price_df['date'].dt.date == test_date.date()]
                            
                            if not filtered_prices.empty:
                                price = filtered_prices['price'].values[0]
                                st.markdown(f"**Raw Price from Booking.com for 2 adults on {test_date.strftime('%d/%m/%Y')}:** {price}€")
                                
                                # Calculate price without tax and interest (for private room)
                                precio_sin_tasa = price - (5.5 * 2)
                                interes = precio_sin_tasa * 0.08
                                precio_final = precio_sin_tasa - interes
                                
                                st.markdown(f"**Price without tax (11€):** {round(precio_sin_tasa, 2)}€")
                                st.markdown(f"**Interest (8%):** {round(interes, 2)}€")
                                st.markdown(f"**Final price without tax and interest:** {round(precio_final, 2)}€")
                                
                                # Shared room price (80% of private room price)
                                shared_price = price * 0.8
                                shared_sin_tasa = shared_price - (5.5 * 2)
                                shared_interes = shared_sin_tasa * 0.08
                                shared_final = shared_sin_tasa - shared_interes
                                
                                st.markdown(f"**Calculated shared room price (80% of private):** {round(shared_price, 2)}€")
                                st.markdown(f"**Shared room price without tax and interest:** {round(shared_final, 2)}€")
                                
                                # Verify if the price matches the expected value
                                if abs(price - 101) < 0.01:  # Allow small floating-point difference
                                    st.success("✅ PASSED: Raw price matches expected value of 101€")
                                else:
                                    st.warning(f"❌ NOTE: Raw price {price}€ does not match expected value of 101€")
                                    
                                # Display detailed calculation steps
                                with st.expander("View detailed calculation steps"):
                                    st.markdown("""
                                    **Private Room Calculation:**
                                    1. Original Booking.com price: {:.2f}€
                                    2. Subtract tourist tax (5.5€ x 2 people): {:.2f}€ - {:.2f}€ = {:.2f}€
                                    3. Calculate 8% interest: {:.2f}€ x 0.08 = {:.2f}€
                                    4. Subtract interest: {:.2f}€ - {:.2f}€ = {:.2f}€
                                    
                                    **Shared Room Calculation:**
                                    1. Apply 20% reduction: {:.2f}€ x 0.8 = {:.2f}€
                                    2. Subtract tourist tax: {:.2f}€ - {:.2f}€ = {:.2f}€
                                    3. Calculate 8% interest: {:.2f}€ x 0.08 = {:.2f}€
                                    4. Subtract interest: {:.2f}€ - {:.2f}€ = {:.2f}€
                                    """.format(
                                        price, price, 11, precio_sin_tasa, 
                                        precio_sin_tasa, interes, 
                                        precio_sin_tasa, interes, precio_final,
                                        price, shared_price,
                                        shared_price, 11, shared_sin_tasa,
                                        shared_sin_tasa, shared_interes,
                                        shared_sin_tasa, shared_interes, shared_final
                                    ))
                            else:
                                st.warning(f"No price data found for the date {test_date.strftime('%d/%m/%Y')}")
                        else:
                            st.warning("No price data available for 2 adults")
    
    # Main content - moved from sidebar
    st.header("Hostel Data Source")
    
    # Hostel data source options - simplified to only include the two requested options
    data_source = st.radio(
        "Choose data source:",
        ["Predefined Hostels", "Manage Predefined Hostels"]
    )
    
    if data_source == "Predefined Hostels":
        # Use only predefined hostels
        if st.button("Load Predefined Hostels"):
            st.session_state.hostel_data = st.session_state.editable_hostels.copy()
            st.success(f"Loaded {len(st.session_state.hostel_data)} predefined hostels")

    elif data_source == "Manage Predefined Hostels":
        st.subheader("Edit Predefined Hostels")
        
        # Display and manage predefined hostels
        if st.session_state.editable_hostels:
            for i, hostel in enumerate(st.session_state.editable_hostels):
                col1, col2, col3 = st.columns([3, 1, 1])
                with col1:
                    st.write(f"{i+1}. {hostel['name']} ({hostel['type']})")
                with col2:
                    if st.button("Edit", key=f"edit_{i}"):
                        st.session_state.editing_hostel = hostel.copy()
                        st.session_state.editing_index = i
                        st.rerun()
                with col3:
                    if st.button("Delete", key=f"delete_{i}"):
                        st.session_state.editable_hostels.pop(i)
                        st.success(f"Deleted hostel: {hostel['name']}")
                        st.rerun()
                        
        # Reset button
        if st.button("Reset to Original Predefined List"):
            st.session_state.editable_hostels = DEFAULT_HOSTELS.copy()
            st.success("Reset predefined hostels to original list")
            st.rerun()
        
        # Display editing form if user is editing a hostel
        if st.session_state.editing_hostel is not None:
            st.subheader(f"Editing: {st.session_state.editing_hostel['name']}")
            
            edit_name = st.text_input("Hotel/Hostel Name", st.session_state.editing_hostel['name'])
            edit_type = st.selectbox("Type", ["Privado", "Compartido", "Hibrido"], 
                                    index=["Privado", "Compartido", "Hibrido"].index(st.session_state.editing_hostel['type']))
            edit_url = st.text_input("Booking.com URL", st.session_state.editing_hostel['url'])
            
            # Validate URL
            if edit_url and not edit_url.startswith("https://www.booking.com"):
                st.error("Please enter a valid Booking.com URL")
                valid_url = False
            else:
                valid_url = True
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Save Changes") and edit_name and edit_url and valid_url:
                    updated_hostel = {
                        "name": edit_name,
                        "type": edit_type,
                        "url": edit_url
                    }
                    st.session_state.editable_hostels[st.session_state.editing_index] = updated_hostel
                    st.session_state.editing_hostel = None
                    st.session_state.editing_index = -1
                    st.success(f"Updated hostel: {edit_name}")
                    st.rerun()
            with col2:
                if st.button("Cancel Editing"):
                    st.session_state.editing_hostel = None
                    st.session_state.editing_index = -1
                    st.rerun()
        
        # Add new hostel form
        st.subheader("Add New Hostel to Predefined List")
        new_hostel_name = st.text_input("New Hotel/Hostel Name", "")
        new_hostel_type = st.selectbox("New Hostel Type", ["Privado", "Compartido", "Hibrido"])
        new_hostel_url = st.text_input("New Booking.com URL", "")
        
        # Validate URL
        if new_hostel_url and not new_hostel_url.startswith("https://www.booking.com"):
            st.error("Please enter a valid Booking.com URL")
        
        # Add new hostel button
        if st.button("Add to Predefined List") and new_hostel_name and new_hostel_url and new_hostel_url.startswith("https://www.booking.com"):
            new_hostel = {
                "name": new_hostel_name,
                "type": new_hostel_type,
                "url": new_hostel_url
            }
            st.session_state.editable_hostels.append(new_hostel)
            st.success(f"Added new hostel to predefined list: {new_hostel_name}")
            st.rerun()
            
        # Use current list button
        if st.button("Use Current Predefined List"):
            st.session_state.hostel_data = st.session_state.editable_hostels.copy()
            st.success(f"Loaded {len(st.session_state.hostel_data)} predefined hostels")
    
    # Display loaded hostels
    if "hostel_data" in st.session_state and st.session_state.hostel_data:
        st.info(f"Loaded {len(st.session_state.hostel_data)} hostels:")
        for i, hostel in enumerate(st.session_state.hostel_data[:5]):  # Show first 5
            st.write(f"{i+1}. {hostel.get('name', 'Unknown')}")
        if len(st.session_state.hostel_data) > 5:
            st.write(f"...and {len(st.session_state.hostel_data) - 5} more")
    
    st.divider()
    
    # Date selection
    st.subheader("Date Selection")
    date_option = st.radio(
        "Choose date option:",
        ["Single Day", "Date Range"]
    )
    
    if date_option == "Single Day":
        selected_date = st.date_input(
            "Select Date",
            value=datetime.now().date()
        )
        end_date = None
        st.info("Se mostrarán los precios mínimos para el día seleccionado.")
    else:
        col1, col2 = st.columns(2)
        with col1:
            selected_date = st.date_input(
                "Start Date",
                value=datetime.now().date()
            )
        with col2:
            end_date = st.date_input(
                "End Date",
                value=datetime.now().date() + timedelta(days=7)
            )
        
        if selected_date > end_date:
            st.error("End date must be after start date.")
            return
            
        date_diff = (end_date - selected_date).days
        st.info(f"Se analizarán {date_diff + 1} días.")
    
    # Run scraping
    if st.button("Run Analysis"):
        if not st.session_state.hostel_data:
            st.error("Please load hostel data first.")
            return
        
        with st.spinner("Scraping hostel data... This may take a while."):
            results = asyncio.run(run_scrape(st.session_state.hostel_data, selected_date, end_date))
            process_results(results, selected_date, end_date, date_option)

def process_results(results_tuple, start_date, end_date=None, date_option="Single Day"):
    # Extraer resultados y errores asegurándose de manejar diferentes formatos
    if isinstance(results_tuple, tuple) and len(results_tuple) == 2:
        results, error_hostels = results_tuple
    else:
        # Si no es una tupla de 2 elementos, asumimos que es solo los resultados
        results = results_tuple
        error_hostels = []
    
    # Display results
    if results:
        # Create a DataFrame from results
        df = pd.DataFrame(results)
        
        # Verificar si la columna URL está disponible
        if 'URL' in df.columns:
            st.success(f"✅ Successfully analyzed {len(results)} hostels with URLs available!")
        else:
            st.success(f"✅ Successfully analyzed {len(results)} hostels but URLs are not available.")
            # Intentar extraer URL del DataFrame si está en otra columna
            for col in df.columns:
                if 'url' in col.lower() or 'link' in col.lower():
                    df['URL'] = df[col]
                    st.info(f"Found URLs in column '{col}' and added them as 'URL'")
                    break
        
        # Display tabs for different views
        tab1, tab2, tab3 = st.tabs(["📊 Resumen", "📋 Comparativa de Precios", "📑 Errores"])
        
        with tab1:
            st.header("Resumen de Precios")
            
            # Agrupar columnas relevantes
            booking_cols = [col for col in df.columns if col.startswith('Precio') and not col.endswith('(Calculado)')]
            sin_tasa_cols = [col for col in df.columns if col.startswith('Precio Sin Tasa')]
            
            # Crear un DataFrame simplificado
            simple_df = df[['Nombre Hotel', 'Tipo'] + booking_cols + sin_tasa_cols].copy()
            
            # Calcular medias por tipo de hostal
            if 'Tipo' in df.columns and not df.empty:
                st.subheader("Media de Precios por Tipo de Hotel")
                
                grupos = []
                
                # Crear las columnas comunes para todos los grupos
                common_columns = ['Tipo', 'Precio Original', 'Precio Sin Tasa', 'Categoría']
                
                # 1. Habitaciones Privadas 2 Adultos
                if 'Precio Hab Baño Privado 2 Adultos' in df.columns and 'Precio Sin Tasa Privado 2 Adultos' in df.columns:
                    privado_2a = df.groupby('Tipo')[['Precio Hab Baño Privado 2 Adultos', 'Precio Sin Tasa Privado 2 Adultos']].mean().reset_index()
                    privado_2a['Categoría'] = 'Hab. Baño Privado 2 Adultos'
                    privado_2a.columns = common_columns  # Establecer nombres de columnas consistentes
                    grupos.append(privado_2a)
                
                # 2. Habitaciones Compartidas 2 Adultos
                if 'Precio Hab Baño Compartido 2 Adultos' in df.columns and 'Precio Sin Tasa Compartido 2 Adultos' in df.columns:
                    compartido_2a = df.groupby('Tipo')[['Precio Hab Baño Compartido 2 Adultos', 'Precio Sin Tasa Compartido 2 Adultos']].mean().reset_index()
                    compartido_2a['Categoría'] = 'Hab. Baño Compartido 2 Adultos'
                    compartido_2a.columns = common_columns  # Establecer nombres de columnas consistentes
                    grupos.append(compartido_2a)
                
                # 3. Habitaciones Compartidas 1 Adulto
                if 'Precio Hab Baño Compartido 1 Adulto' in df.columns and 'Precio Sin Tasa Compartido 1 Adulto' in df.columns:
                    compartido_1a = df.groupby('Tipo')[['Precio Hab Baño Compartido 1 Adulto', 'Precio Sin Tasa Compartido 1 Adulto']].mean().reset_index()
                    compartido_1a['Categoría'] = 'Hab. Baño Compartido 1 Adulto'
                    compartido_1a.columns = common_columns  # Establecer nombres de columnas consistentes
                    grupos.append(compartido_1a)
                
                if grupos:
                    try:
                        # Combinar todos los grupos
                        summary_df = pd.concat(grupos)
                        
                        # Renombrar columnas para la visualización
                        summary_df.columns = ['Tipo de Hotel', 'Precio Original Booking (€)', 'Precio Sin Tasa e Interés (€)', 'Categoría']
                        summary_df['Precio Original Booking (€)'] = summary_df['Precio Original Booking (€)'].round(2)
                        summary_df['Precio Sin Tasa e Interés (€)'] = summary_df['Precio Sin Tasa e Interés (€)'].round(2)
                        
                        # Mostrar tabla pivote para mejor visualización
                        try:
                            # Crear múltiples tablas pivote, una para cada tipo de precio
                            pivot_orig = summary_df.pivot(index='Tipo de Hotel', columns='Categoría', values='Precio Original Booking (€)').reset_index()
                            pivot_orig.columns = ['Tipo de Hotel'] + [f"{col} - Original" for col in pivot_orig.columns[1:]]
                            
                            pivot_sin_tasa = summary_df.pivot(index='Tipo de Hotel', columns='Categoría', values='Precio Sin Tasa e Interés (€)').reset_index()
                            pivot_sin_tasa.columns = ['Tipo de Hotel'] + [f"{col} - Sin Tasa" for col in pivot_sin_tasa.columns[1:]]
                            
                            # Combinar las dos tablas pivote
                            pivot_df = pd.merge(pivot_orig, pivot_sin_tasa, on='Tipo de Hotel')
                            
                            st.dataframe(pivot_df, use_container_width=True)
                        except Exception as e:
                            # Si la creación de la tabla pivote falla, mostrar el DataFrame original
                            st.warning(f"No se pudo crear la vista pivote: {str(e)}")
                            st.dataframe(summary_df, use_container_width=True)
                        
                        # Añadir explicación de las columnas
                        st.info("**Explicación de los precios:**\n"
                              "- **Precio Original Booking (€)**: Precio bruto obtenido directamente de Booking.com\n"
                              "- **Precio Sin Tasa e Interés (€)**: Precio original - Tasa Turística - 8% de interés")

                        # Mostrar gráfico de barras agrupadas
                        try:
                            # Crear un dataframe en formato largo para los gráficos
                            chart_df = pd.melt(summary_df, 
                                              id_vars=['Tipo de Hotel', 'Categoría'],
                                              value_vars=['Precio Original Booking (€)', 'Precio Sin Tasa e Interés (€)'],
                                              var_name='Tipo de Precio', value_name='Precio (€)')
                            
                            # Crear un gráfico de barras agrupadas
                            chart = alt.Chart(chart_df).mark_bar().encode(
                                x=alt.X('Tipo de Hotel:N', title='Tipo de Hotel'),
                                y=alt.Y('Precio (€):Q', title='Precio (€)'),
                                color=alt.Color('Tipo de Precio:N', 
                                              scale=alt.Scale(domain=['Precio Original Booking (€)', 
                                                            'Precio Sin Tasa e Interés (€)'],
                                                      range=['#1f77b4', '#ff7f0e']), 
                                              legend=alt.Legend(title="Tipo de Precio")),
                                column=alt.Column('Categoría:N', title=None)
                            ).properties(
                                width=200
                            ).configure_view(
                                stroke=None
                            )
                            
                            st.altair_chart(chart, use_container_width=True)
                        except Exception as e:
                            st.warning(f"No se pudo crear el gráfico: {str(e)}")
                    except Exception as e:
                        st.error(f"Error al procesar los datos para la visualización: {str(e)}")
                        # Mostrar datos simples como alternativa
                        st.subheader("Datos disponibles:")
                        for col in booking_cols:
                            if col in df.columns:
                                st.write(f"{col}: Media = {df[col].mean():.2f} €")
                else:
                    st.info("No hay suficientes datos para mostrar la comparativa de precios por tipo de hotel.")
            
        with tab2:
            st.header("Comparativa de Precios")
            
            # Crear pestañas por tipo de habitación
            subtab1, subtab2, subtab3 = st.tabs(["Habitación Privada 2 Adultos", "Habitación Compartida 2 Adultos", "Habitación Compartida 1 Adulto"])
            
            with subtab1:
                if 'Precio Hab Baño Privado 2 Adultos' in df.columns and 'Precio Sin Tasa Privado 2 Adultos' in df.columns:
                    # Crear DataFrame simplificado con columnas de disponibilidad si es un rango
                    if date_option == "Date Range":
                        if 'Días con Disponibilidad' in df.columns and 'Total Días en Rango' in df.columns:
                            privado_2a_df = df[['Nombre Hotel', 'Tipo', 'Precio Hab Baño Privado 2 Adultos', 
                                                'Precio Sin Tasa Privado 2 Adultos', 'Tasa Turística 2 Adultos', 
                                                'Interés 8% Privado 2 Adultos', 'Días con Disponibilidad', 
                                                'Total Días en Rango']].copy()
                            
                            # Añadir columna de porcentaje
                            privado_2a_df['% Disponibilidad'] = (privado_2a_df['Días con Disponibilidad'] / 
                                                                privado_2a_df['Total Días en Rango'] * 100).round(1)
                            
                            # Renombrar columnas
                            privado_2a_df.columns = ['Hotel', 'Tipo', 'Precio Original Booking (€)', 
                                                    'Precio Sin Tasa e Interés (€)', 'Tasa Turística (€)', 
                                                    'Interés (€)', 'Días Disponibles', 'Total Días', '% Disponibilidad']
                        else:
                            privado_2a_df = df[['Nombre Hotel', 'Tipo', 'Precio Hab Baño Privado 2 Adultos', 
                                                'Precio Sin Tasa Privado 2 Adultos', 'Tasa Turística 2 Adultos', 
                                                'Interés 8% Privado 2 Adultos']].copy()
                            
                            # Renombrar columnas
                            privado_2a_df.columns = ['Hotel', 'Tipo', 'Precio Original Booking (€)', 
                                                    'Precio Sin Tasa e Interés (€)', 'Tasa Turística (€)', 'Interés (€)']
                    else:
                        # Si es día único, no incluimos información de disponibilidad
                        privado_2a_df = df[['Nombre Hotel', 'Tipo', 'Precio Hab Baño Privado 2 Adultos', 
                                            'Precio Sin Tasa Privado 2 Adultos', 'Tasa Turística 2 Adultos', 
                                            'Interés 8% Privado 2 Adultos']].copy()
                        
                        # Renombrar columnas
                        privado_2a_df.columns = ['Hotel', 'Tipo', 'Precio Original Booking (€)', 
                                                'Precio Sin Tasa e Interés (€)', 'Tasa Turística (€)', 'Interés (€)']
                    
                    # Ordenar por precio de Booking
                    privado_2a_df = privado_2a_df.sort_values('Precio Original Booking (€)')
                    
                    # Mostrar tabla
                    st.dataframe(privado_2a_df, hide_index=True, use_container_width=True)
                    
                    # Añadir explicación de las columnas
                    if date_option == "Date Range" and 'Días Disponibles' in privado_2a_df.columns:
                        st.info("**Explicación de los precios:**\n"
                              "- **Precio Original Booking (€)**: Precio bruto promedio obtenido de Booking.com\n"
                              "- **Precio Sin Tasa e Interés (€)**: Precio original - Tasa Turística - 8% de interés\n"
                              "- **% Disponibilidad**: Porcentaje de días en el rango con disponibilidad (precios > 0)\n\n"
                              "**Nota importante:** El promedio solo considera los días con disponibilidad, ignorando aquellos sin precios.")
                    else:
                        st.info("**Explicación de los precios:**\n"
                              "- **Precio Original Booking (€)**: Precio bruto obtenido directamente de Booking.com\n"
                              "- **Precio Sin Tasa e Interés (€)**: Precio original - Tasa Turística - 8% de interés")
                    
                    # Mostrar enlaces si están disponibles
                    if 'URL' in df.columns:
                        st.subheader("Enlaces a Booking.com")
                        for hotel_name in privado_2a_df['Hotel']:
                            # Encontrar la URL correspondiente
                            matching_rows = df[df['Nombre Hotel'] == hotel_name]
                            if not matching_rows.empty and 'URL' in matching_rows.columns:
                                url = matching_rows['URL'].iloc[0]
                                if url:
                                    st.markdown(f"🔗 [{hotel_name}]({url})")
                else:
                    st.warning("No hay datos disponibles para habitaciones privadas 2 adultos")
            
            with subtab2:
                if 'Precio Hab Baño Compartido 2 Adultos' in df.columns and 'Precio Sin Tasa Compartido 2 Adultos' in df.columns:
                    # Crear DataFrame simplificado con columnas de disponibilidad si es un rango
                    if date_option == "Date Range":
                        if 'Días con Disponibilidad' in df.columns and 'Total Días en Rango' in df.columns:
                            compartido_2a_df = df[['Nombre Hotel', 'Tipo', 'Precio Hab Baño Compartido 2 Adultos', 
                                                'Precio Sin Tasa Compartido 2 Adultos', 'Tasa Turística 2 Adultos', 
                                                'Interés 8% Compartido 2 Adultos', 'Días con Disponibilidad', 
                                                'Total Días en Rango']].copy()
                            
                            # Añadir columna de porcentaje
                            compartido_2a_df['% Disponibilidad'] = (compartido_2a_df['Días con Disponibilidad'] / 
                                                                compartido_2a_df['Total Días en Rango'] * 100).round(1)
                            
                            # Renombrar columnas
                            compartido_2a_df.columns = ['Hotel', 'Tipo', 'Precio Original Booking (€)', 
                                                    'Precio Sin Tasa e Interés (€)', 'Tasa Turística (€)', 
                                                    'Interés (€)', 'Días Disponibles', 'Total Días', '% Disponibilidad']
                        else:
                            compartido_2a_df = df[['Nombre Hotel', 'Tipo', 'Precio Hab Baño Compartido 2 Adultos', 
                                                'Precio Sin Tasa Compartido 2 Adultos', 'Tasa Turística 2 Adultos', 
                                                'Interés 8% Compartido 2 Adultos']].copy()
                            
                            # Renombrar columnas
                            compartido_2a_df.columns = ['Hotel', 'Tipo', 'Precio Original Booking (€)', 
                                                    'Precio Sin Tasa e Interés (€)', 'Tasa Turística (€)', 'Interés (€)']
                    else:
                        # Si es día único, no incluimos información de disponibilidad
                        compartido_2a_df = df[['Nombre Hotel', 'Tipo', 'Precio Hab Baño Compartido 2 Adultos', 
                                            'Precio Sin Tasa Compartido 2 Adultos', 'Tasa Turística 2 Adultos', 
                                            'Interés 8% Compartido 2 Adultos']].copy()
                        
                        # Renombrar columnas
                        compartido_2a_df.columns = ['Hotel', 'Tipo', 'Precio Original Booking (€)', 
                                                'Precio Sin Tasa e Interés (€)', 'Tasa Turística (€)', 'Interés (€)']
                    
                    # Ordenar por precio de Booking
                    compartido_2a_df = compartido_2a_df.sort_values('Precio Original Booking (€)')
                    
                    # Mostrar tabla
                    st.dataframe(compartido_2a_df, hide_index=True, use_container_width=True)
                    
                    # Añadir explicación de las columnas
                    if date_option == "Date Range" and 'Días Disponibles' in compartido_2a_df.columns:
                        st.info("**Explicación de los precios:**\n"
                              "- **Precio Original Booking (€)**: Precio bruto promedio obtenido de Booking.com\n"
                              "- **Precio Sin Tasa e Interés (€)**: Precio original - Tasa Turística - 8% de interés\n"
                              "- **% Disponibilidad**: Porcentaje de días en el rango con disponibilidad (precios > 0)\n\n"
                              "**Nota importante:** El promedio solo considera los días con disponibilidad, ignorando aquellos sin precios.")
                    else:
                        st.info("**Explicación de los precios:**\n"
                              "- **Precio Original Booking (€)**: Precio bruto obtenido directamente de Booking.com\n"
                              "- **Precio Sin Tasa e Interés (€)**: Precio original - Tasa Turística - 8% de interés")
                    
                    # Mostrar enlaces si están disponibles
                    if 'URL' in df.columns:
                        st.subheader("Enlaces a Booking.com")
                        for hotel_name in compartido_2a_df['Hotel']:
                            # Encontrar la URL correspondiente
                            matching_rows = df[df['Nombre Hotel'] == hotel_name]
                            if not matching_rows.empty and 'URL' in matching_rows.columns:
                                url = matching_rows['URL'].iloc[0]
                                if url:
                                    st.markdown(f"🔗 [{hotel_name}]({url})")
                else:
                    st.warning("No hay datos disponibles para habitaciones compartidas 2 adultos")
            
            with subtab3:
                if 'Precio Hab Baño Compartido 1 Adulto' in df.columns and 'Precio Sin Tasa Compartido 1 Adulto' in df.columns:
                    # Crear DataFrame simplificado con columnas de disponibilidad si es un rango
                    if date_option == "Date Range":
                        if 'Días con Disponibilidad 1A' in df.columns and 'Total Días en Rango 1A' in df.columns:
                            compartido_1a_df = df[['Nombre Hotel', 'Tipo', 'Precio Hab Baño Compartido 1 Adulto', 
                                                'Precio Sin Tasa Compartido 1 Adulto', 'Tasa Turística 1 Adulto', 
                                                'Interés 8% Compartido 1 Adulto', 'Días con Disponibilidad 1A', 
                                                'Total Días en Rango 1A']].copy()
                            
                            # Añadir columna de porcentaje
                            compartido_1a_df['% Disponibilidad'] = (compartido_1a_df['Días con Disponibilidad 1A'] / 
                                                                compartido_1a_df['Total Días en Rango 1A'] * 100).round(1)
                            
                            # Renombrar columnas
                            compartido_1a_df.columns = ['Hotel', 'Tipo', 'Precio Original Booking (€)', 
                                                    'Precio Sin Tasa e Interés (€)', 'Tasa Turística (€)', 
                                                    'Interés (€)', 'Días Disponibles', 'Total Días', '% Disponibilidad']
                        else:
                            compartido_1a_df = df[['Nombre Hotel', 'Tipo', 'Precio Hab Baño Compartido 1 Adulto', 
                                                'Precio Sin Tasa Compartido 1 Adulto', 'Tasa Turística 1 Adulto', 
                                                'Interés 8% Compartido 1 Adulto']].copy()
                            
                            # Renombrar columnas
                            compartido_1a_df.columns = ['Hotel', 'Tipo', 'Precio Original Booking (€)', 
                                                    'Precio Sin Tasa e Interés (€)', 'Tasa Turística (€)', 'Interés (€)']
                    else:
                        # Si es día único, no incluimos información de disponibilidad
                        compartido_1a_df = df[['Nombre Hotel', 'Tipo', 'Precio Hab Baño Compartido 1 Adulto', 
                                            'Precio Sin Tasa Compartido 1 Adulto', 'Tasa Turística 1 Adulto', 
                                            'Interés 8% Compartido 1 Adulto']].copy()
                        
                        # Renombrar columnas
                        compartido_1a_df.columns = ['Hotel', 'Tipo', 'Precio Original Booking (€)', 
                                                'Precio Sin Tasa e Interés (€)', 'Tasa Turística (€)', 'Interés (€)']
                    
                    # Ordenar por precio de Booking
                    compartido_1a_df = compartido_1a_df.sort_values('Precio Original Booking (€)')
                    
                    # Mostrar tabla
                    st.dataframe(compartido_1a_df, hide_index=True, use_container_width=True)
                    
                    # Añadir explicación de las columnas
                    if date_option == "Date Range" and 'Días Disponibles' in compartido_1a_df.columns:
                        st.info("**Explicación de los precios:**\n"
                              "- **Precio Original Booking (€)**: Precio bruto promedio obtenido de Booking.com\n"
                              "- **Precio Sin Tasa e Interés (€)**: Precio original - Tasa Turística - 8% de interés\n"
                              "- **% Disponibilidad**: Porcentaje de días en el rango con disponibilidad (precios > 0)\n\n"
                              "**Nota importante:** El promedio solo considera los días con disponibilidad, ignorando aquellos sin precios.")
                    else:
                        st.info("**Explicación de los precios:**\n"
                              "- **Precio Original Booking (€)**: Precio bruto obtenido directamente de Booking.com\n"
                              "- **Precio Sin Tasa e Interés (€)**: Precio original - Tasa Turística - 8% de interés")
                    
                    # Mostrar enlaces si están disponibles
                    if 'URL' in df.columns:
                        st.subheader("Enlaces a Booking.com")
                        for hotel_name in compartido_1a_df['Hotel']:
                            # Encontrar la URL correspondiente
                            matching_rows = df[df['Nombre Hotel'] == hotel_name]
                            if not matching_rows.empty and 'URL' in matching_rows.columns:
                                url = matching_rows['URL'].iloc[0]
                                if url:
                                    st.markdown(f"🔗 [{hotel_name}]({url})")
                else:
                    st.warning("No hay datos disponibles para habitaciones compartidas 1 adulto")
            
            # Opción de exportar
            if st.button("Exportar a CSV"):
                # Preparar datos para exportar
                export_df = df[['Nombre Hotel', 'Tipo'] + booking_cols + sin_tasa_cols].copy()
                
                # Convertir DataFrame a CSV
                csv = export_df.to_csv(index=False)
                
                # Crear botón de descarga
                date_str = start_date.strftime("%Y-%m-%d")
                if end_date:
                    date_str += f"_to_{end_date.strftime('%Y-%m-%d')}"
                st.download_button(
                    label="Descargar CSV",
                    data=csv,
                    file_name=f"precios_hoteles_{date_str}.csv",
                    mime="text/csv"
                )
                
        with tab3:
            st.header("Log de Errores")
            
            if error_hostels:
                error_df = pd.DataFrame(error_hostels)
                st.dataframe(error_df, use_container_width=True)
                st.warning(f"{len(error_hostels)} hoteles no pudieron ser procesados debido a errores.")
            else:
                st.success("No hubo errores durante el procesamiento!")
    else:
        st.error("No hay resultados para mostrar. Por favor, ejecute el análisis primero.")

if __name__ == "__main__":
    main() 
