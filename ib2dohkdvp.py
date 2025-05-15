import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime
import requests
from decimal import Decimal, ROUND_HALF_UP
import os
import glob
import json
from pathlib import Path
import lxml.etree as etree
import urllib.request
from collections import OrderedDict

# ========== USER: Edit your personal info here ==========
ZAVEZANEC = {
    'DavcnaStevilka': '12345678',
    'Ime': 'Janez',
    'Priimek': 'Novak',
    'Naslov': 'Ulica 1',
    'Posta': '1000',
    'Obcina': 'LJUBLJANA',
}
# =======================================================

# ========== USER: Input/output directories ==============
INPUT_DIR = 'files'
OUTPUT_DIR = 'output'
CACHE_FILE = 'exchange_rates_cache.json'
XSD_FILE = 'Doh_Kdvp_1_8.xsd'
# =======================================================

# Initialize exchange rate cache
exchange_rate_cache = {}

def load_exchange_rate_cache():
    """Load exchange rates from cache file"""
    global exchange_rate_cache
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r') as f:
                exchange_rate_cache = json.load(f)
        except Exception as e:
            print(f"Error loading cache: {e}")
            exchange_rate_cache = {}

def save_exchange_rate_cache():
    """Save exchange rates to cache file"""
    try:
        with open(CACHE_FILE, 'w') as f:
            json.dump(exchange_rate_cache, f)
    except Exception as e:
        print(f"Error saving cache: {e}")

def get_exchange_rate(date, from_currency, to_currency='EUR'):
    """Get exchange rate from ECB for a specific date"""
    if from_currency == to_currency:
        return Decimal('1.0')
    
    # Format date as YYYY-MM-DD
    date_str = date.strftime('%Y-%m-%d')
    
    # Check cache first
    cache_key = f"{date_str}_{from_currency}_{to_currency}"
    if cache_key in exchange_rate_cache:
        return Decimal(str(exchange_rate_cache[cache_key]))
    
    # Try multiple APIs if one fails
    apis = [
        # ECB API
        f'https://api.exchangerate.host/{date_str}?base={from_currency}&symbols={to_currency}',
        # Alternative API 1
        f'https://api.frankfurter.app/{date_str}?from={from_currency}&to={to_currency}',
        # Alternative API 2
        f'https://api.vatcomply.com/rates?date={date_str}&base={from_currency}'
    ]
    
    for api_url in apis:
        try:
            response = requests.get(api_url, timeout=10)
            data = response.json()
            
            # Handle different API response formats
            if 'rates' in data and to_currency in data['rates']:
                rate = data['rates'][to_currency]
            elif 'rates' in data:
                rate = data['rates'].get(to_currency)
            else:
                continue
                
            if rate:
                # Cache the result
                exchange_rate_cache[cache_key] = float(rate)
                save_exchange_rate_cache()
                return Decimal(str(rate))
                
        except Exception as e:
            print(f"Warning: API {api_url} failed: {e}")
            continue
    
    print(f"Warning: Could not get exchange rate for {from_currency} to {to_currency} on {date_str}")
    # Use a fallback rate if all APIs fail
    fallback_rates = {
        'USD': Decimal('0.85'),  # Approximate USD to EUR rate
        'GBP': Decimal('1.15'),  # Approximate GBP to EUR rate
        'CHF': Decimal('0.95'),  # Approximate CHF to EUR rate
    }
    return fallback_rates.get(from_currency, Decimal('1.0'))

def convert_to_eur(value, currency, date_str):
    """Convert value to EUR using exchange rate for the given date"""
    if not value or not currency or currency == 'EUR':
        return value
    
    try:
        value_decimal = Decimal(str(value))
        date = datetime.strptime(date_str, '%Y-%m-%d')
        rate = get_exchange_rate(date, currency)
        eur_value = value_decimal * rate
        return format(eur_value.quantize(Decimal('.01'), rounding=ROUND_HALF_UP), '.2f')
    except Exception as e:
        print(f"Error converting {value} {currency} to EUR: {e}")
        return value

def parse_ib_xml(path):
    """Parse IB XML file and return root element"""
    tree = ET.parse(path)
    root = tree.getroot()
    return root

def find_trades_and_lots(root):
    """Find all trades and lots in the XML"""
    trades = []
    lots = []
    
    # Find all Trade elements
    for trade in root.findall('.//Trade'):
        trades.append(trade)
    
    # Find all Lot elements
    for lot in root.findall('.//Lot'):
        lots.append(lot)
    
    print(f"Found {len(trades)} trades and {len(lots)} lots")
    return trades, lots

def get_trade_by_transaction_id(trades, transaction_id):
    for trade in trades:
        if trade.get('transactionID') == transaction_id:
            return trade
    return None

def format_date(date_str):
    # IB format: YYYYMMDD or YYYYMMDD;HHMMSS
    if not date_str:
        return ''
    date_str = date_str.split(';')[0]
    try:
        return datetime.strptime(date_str, '%Y%m%d').strftime('%Y-%m-%d')
    except Exception:
        return date_str

def lot_to_napoved(lot, trades):
    """Transform an IB lot into a DOH-KDVP napoved"""
    asset_map = {
        'STK': 'DELEZ',
        'BOND': 'OBVEZNICA',
        'FUND': 'INVESTICIJSKI_SKLAD',
        'OPT': 'DERIVAT',
        'FUT': 'DERIVAT',
        'CASH': 'DENAR',
        'ETF': 'INVESTICIJSKI_SKLAD',
        'WAR': 'DERIVAT',
    }
    asset_cat = lot.get('assetCategory', 'STK')
    vrsta = asset_map.get(asset_cat, 'DELEZ')
    isin = lot.get('isin', '')
    drzava = isin[:2] if len(isin) >= 2 else 'XX'
    naziv = lot.get('description', lot.get('symbol', ''))
    datum_nakupa = format_date(lot.get('openDateTime', ''))
    datum_prodaje = format_date(lot.get('dateTime', ''))
    currency = lot.get('currency', 'USD')
    buy_trade = None
    sell_trade = None
    for trade in trades:
        if (trade.get('symbol') == lot.get('symbol') and 
            trade.get('buySell') == 'SELL' and 
            trade.get('dateTime', '').startswith(datum_prodaje.replace('-', ''))):
            sell_trade = trade
            break
    for trade in trades:
        if (trade.get('symbol') == lot.get('symbol') and 
            trade.get('buySell') == 'BUY' and 
            trade.get('dateTime', '').startswith(datum_nakupa.replace('-', ''))):
            buy_trade = trade
            break
    if buy_trade is not None:
        vrednost_nakupa = convert_to_eur(str(abs(float(buy_trade.get('tradeMoney', '0')))), currency, datum_nakupa)
        stroski_nakupa = convert_to_eur(str(abs(float(buy_trade.get('ibCommission', '0')))), currency, datum_nakupa)
    else:
        vrednost_nakupa = '0'
        stroski_nakupa = '0'
    if sell_trade is not None:
        vrednost_prodaje = convert_to_eur(str(abs(float(sell_trade.get('tradeMoney', '0')))), currency, datum_prodaje)
        stroski_prodaje = convert_to_eur(str(abs(float(sell_trade.get('ibCommission', '0')))), currency, datum_prodaje)
    else:
        vrednost_prodaje = '0'
        stroski_prodaje = '0'
    leto = datum_prodaje[:4] if datum_prodaje else ''
    return OrderedDict([
        ('Leto', leto),
        ('VrstaVrednostnegaPapirja', vrsta),
        ('Drzava', drzava),
        ('Naziv', naziv),
        ('DatumNakupa', datum_nakupa),
        ('StroskiNakupa', stroski_nakupa),
        ('VrednostNakupa', vrednost_nakupa),
        ('DatumProdaje', datum_prodaje),
        ('StroskiProdaje', stroski_prodaje),
        ('VrednostProdaje', vrednost_prodaje),
    ])

def trade_to_napoved(trade, trades):
    """Transform an IB trade into a DOH-KDVP napoved"""
    asset_map = {
        'STK': 'DELEZ',
        'BOND': 'OBVEZNICA',
        'FUND': 'INVESTICIJSKI_SKLAD',
        'OPT': 'DERIVAT',
        'FUT': 'DERIVAT',
        'CASH': 'DENAR',
        'ETF': 'INVESTICIJSKI_SKLAD',
        'WAR': 'DERIVAT',
    }
    asset_cat = trade.get('assetCategory', 'STK')
    vrsta = asset_map.get(asset_cat, 'DELEZ')
    isin = trade.get('isin', '')
    drzava = isin[:2] if len(isin) >= 2 else 'XX'
    naziv = trade.get('description', trade.get('symbol', ''))
    datum = format_date(trade.get('dateTime', ''))
    currency = trade.get('currency', 'USD')
    matching_trade = None
    for t in trades:
        if (t.get('symbol') == trade.get('symbol') and 
            t.get('buySell') != trade.get('buySell') and
            t.get('dateTime', '') > trade.get('dateTime', '')):
            matching_trade = t
            break
    if trade.get('buySell') == 'BUY':
        datum_nakupa = datum
        datum_prodaje = format_date(matching_trade.get('dateTime', '')) if matching_trade else datum
        vrednost_nakupa = convert_to_eur(str(abs(float(trade.get('tradeMoney', '0')))), currency, datum_nakupa)
        stroski_nakupa = convert_to_eur(str(abs(float(trade.get('ibCommission', '0')))), currency, datum_nakupa)
        vrednost_prodaje = convert_to_eur(str(abs(float(matching_trade.get('tradeMoney', '0')))), currency, datum_prodaje) if matching_trade else '0'
        stroski_prodaje = convert_to_eur(str(abs(float(matching_trade.get('ibCommission', '0')))), currency, datum_prodaje) if matching_trade else '0'
    else:
        datum_prodaje = datum
        datum_nakupa = format_date(matching_trade.get('dateTime', '')) if matching_trade else datum
        vrednost_prodaje = convert_to_eur(str(abs(float(trade.get('tradeMoney', '0')))), currency, datum_prodaje)
        stroski_prodaje = convert_to_eur(str(abs(float(trade.get('ibCommission', '0')))), currency, datum_prodaje)
        vrednost_nakupa = convert_to_eur(str(abs(float(matching_trade.get('tradeMoney', '0')))), currency, datum_nakupa) if matching_trade else '0'
        stroski_nakupa = convert_to_eur(str(abs(float(matching_trade.get('ibCommission', '0')))), currency, datum_nakupa) if matching_trade else '0'
    leto = datum_prodaje[:4] if datum_prodaje else datum_nakupa[:4]
    return OrderedDict([
        ('Leto', leto),
        ('VrstaVrednostnegaPapirja', vrsta),
        ('Drzava', drzava),
        ('Naziv', naziv),
        ('DatumNakupa', datum_nakupa),
        ('StroskiNakupa', stroski_nakupa),
        ('VrednostNakupa', vrednost_nakupa),
        ('DatumProdaje', datum_prodaje),
        ('StroskiProdaje', stroski_prodaje),
        ('VrednostProdaje', vrednost_prodaje),
    ])

def create_xsd_schema():
    """Create the XSD schema file"""
    xsd_content = '''<?xml version="1.0" encoding="UTF-8"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" 
           targetNamespace="http://edavki.durs.si/Documents/Schemas/Doh_Kdvp_1_8.xsd"
           xmlns="http://edavki.durs.si/Documents/Schemas/Doh_Kdvp_1_8.xsd"
           elementFormDefault="qualified">
    
    <xs:element name="VlogaDohKdvp">
        <xs:complexType>
            <xs:sequence>
                <xs:element name="Zavezanec" type="ZavezanecType"/>
                <xs:element name="Napovedi">
                    <xs:complexType>
                        <xs:sequence>
                            <xs:element name="Napoved" type="NapovedType" minOccurs="1" maxOccurs="unbounded"/>
                        </xs:sequence>
                    </xs:complexType>
                </xs:element>
            </xs:sequence>
        </xs:complexType>
    </xs:element>

    <xs:complexType name="ZavezanecType">
        <xs:sequence>
            <xs:element name="DavcnaStevilka" type="xs:string"/>
            <xs:element name="Ime" type="xs:string"/>
            <xs:element name="Priimek" type="xs:string"/>
            <xs:element name="Naslov" type="xs:string"/>
            <xs:element name="Posta" type="xs:string"/>
            <xs:element name="Obcina" type="xs:string"/>
        </xs:sequence>
    </xs:complexType>

    <xs:complexType name="NapovedType">
        <xs:sequence>
            <xs:element name="Leto" type="xs:string"/>
            <xs:element name="VrstaVrednostnegaPapirja" type="xs:string"/>
            <xs:element name="Drzava" type="xs:string"/>
            <xs:element name="Naziv" type="xs:string"/>
            <xs:element name="DatumNakupa" type="xs:date"/>
            <xs:element name="StroskiNakupa" type="xs:decimal"/>
            <xs:element name="VrednostNakupa" type="xs:decimal"/>
            <xs:element name="DatumProdaje" type="xs:date"/>
            <xs:element name="StroskiProdaje" type="xs:decimal"/>
            <xs:element name="VrednostProdaje" type="xs:decimal"/>
        </xs:sequence>
    </xs:complexType>
</xs:schema>'''
    
    try:
        with open(XSD_FILE, 'w', encoding='utf-8') as f:
            f.write(xsd_content)
        print("XSD schema file created successfully")
        return True
    except Exception as e:
        print(f"Error creating XSD schema: {e}")
        return False

def validate_xml(xml_string, xsd_path):
    """Validate XML against XSD schema"""
    try:
        # Parse XML
        xml_doc = etree.fromstring(xml_string.encode('utf-8'))
        
        # Parse XSD
        xsd_doc = etree.parse(xsd_path)
        schema = etree.XMLSchema(xsd_doc)
        
        # Validate
        is_valid = schema.validate(xml_doc)
        
        if not is_valid:
            print("XML validation errors:")
            for error in schema.error_log:
                print(f"Line {error.line}: {error.message}")
        
        return is_valid
    except Exception as e:
        print(f"Error validating XML: {e}")
        return False

def build_doh_kdvp_xml(zavezanec, napovedi):
    """Build DOH-KDVP XML with proper namespace and formatting"""
    NS = 'http://edavki.durs.si/Documents/Schemas/Doh_Kdvp_1_8.xsd'
    
    # Create root element with schema location
    VlogaDohKdvp = ET.Element('VlogaDohKdvp', {
        'xmlns': NS,
        'xmlns:xsi': 'http://www.w3.org/2001/XMLSchema-instance',
        'xsi:schemaLocation': f'{NS} {XSD_FILE}'
    })
    
    # Add Zavezanec
    Zavezanec = ET.SubElement(VlogaDohKdvp, 'Zavezanec')
    zavezanec_fields = ['DavcnaStevilka', 'Ime', 'Priimek', 'Naslov', 'Posta', 'Obcina']
    for field in zavezanec_fields:
        if field in zavezanec:
            ET.SubElement(Zavezanec, field).text = zavezanec[field]
    
    # Add Napovedi
    Napovedi = ET.SubElement(VlogaDohKdvp, 'Napovedi')
    
    # Only add Napovedi if there are napovedi to add
    if napovedi:
        for napoved in napovedi:
            Napoved = ET.SubElement(Napovedi, 'Napoved')
            
            # Create a list of (field, value) pairs in the correct order
            fields_and_values = []
            for field in [
                'Leto',
                'VrstaVrednostnegaPapirja',
                'Drzava',
                'Naziv',
                'DatumNakupa',
                'StroskiNakupa',
                'VrednostNakupa',
                'DatumProdaje',
                'StroskiProdaje',
                'VrednostProdaje'
            ]:
                if field in napoved and napoved[field] is not None and napoved[field] != '':
                    fields_and_values.append((field, str(napoved[field])))
            
            # Create all elements in order
            for field, value in fields_and_values:
                element = ET.SubElement(Napoved, field)
                element.text = value
    
    return VlogaDohKdvp

def prettify(elem):
    """Create properly formatted XML string"""
    rough_string = ET.tostring(elem, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ", encoding='utf-8').decode('utf-8')

def main():
    load_exchange_rate_cache()
    if not os.path.exists(XSD_FILE):
        if not create_xsd_schema():
            print("Error: Could not create XSD schema. Exiting.")
            return
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    input_files = [f for f in os.listdir(INPUT_DIR) if f.lower().endswith('.xml')]
    if not input_files:
        print("No XML files found in the files directory.")
        return
    for filename in input_files:
        input_file = os.path.join(INPUT_DIR, filename)
        output_file = os.path.join(OUTPUT_DIR, filename)
        try:
            root = parse_ib_xml(input_file)
            trades, lots = find_trades_and_lots(root)
            closed_lots = [lot for lot in lots if lot.get('levelOfDetail') == 'CLOSED_LOT']
            if closed_lots:
                napovedi = [lot_to_napoved(lot, trades) for lot in closed_lots]
            else:
                buy_trades = [trade for trade in trades if trade.get('buySell') == 'BUY']
                napovedi = [trade_to_napoved(trade, trades) for trade in buy_trades]
            if not napovedi:
                print(f"Skipping {filename} - no trades or lots found")
                continue
            doh_kdvp_xml = build_doh_kdvp_xml(ZAVEZANEC, napovedi)
            xml_str = prettify(doh_kdvp_xml)
            if validate_xml(xml_str, XSD_FILE):
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(xml_str)
                print(f"SUCCESS: {filename} transformed and validated. Output: {output_file}")
            else:
                print(f"FAIL: {filename} did not pass XSD validation.")
        except Exception as e:
            print(f"FAIL: Error processing {filename}: {str(e)}")
    save_exchange_rate_cache()

if __name__ == '__main__':
    main() 