# IB to DOH-KDVP XML Transformer

This Python script transforms Interactive Brokers (IB) XML reports into the Slovenian DOH-KDVP XML format required for tax reporting.

## Features

- Converts IB trade and lot data to DOH-KDVP format
- Handles both closed lots and individual trades
- Automatically converts currencies to EUR using exchange rates
- Validates output against DOH-KDVP XSD schema
- Caches exchange rates to minimize API calls
- Processes multiple input files in batch

## Requirements

- Python 3.6 or higher
- Required packages (install using `pip install -r requirements.txt`):
  - requests>=2.31.0
  - lxml>=4.9.3

## Installation

1. Clone or download this repository
2. Install required packages:
   ```bash
   pip install -r requirements.txt
   ```

## Configuration

Edit the following variables in `ib2dohkdvp.py`:

```python
# Personal information
ZAVEZANEC = {
    'DavcnaStevilka': '12345678',
    'Ime': 'Janez',
    'Priimek': 'Novak',
    'Naslov': 'Ulica 1',
    'Posta': '1000',
    'Obcina': 'LJUBLJANA',
}

# Directories
INPUT_DIR = 'files'      # Directory containing IB XML files
OUTPUT_DIR = 'output'    # Directory for transformed files
```

## Usage

1. Place your IB XML files in the `files` directory
2. Run the script:
   ```bash
   python ib2dohkdvp.py
   ```
3. Check the `output` directory for transformed files

## Input Format

The script expects IB XML files containing:

- Trade information (buy/sell transactions)
- Lot information (for closed positions)
- Asset details (symbol, description, ISIN)
- Transaction details (dates, amounts, commissions)

## Output Format

The script generates DOH-KDVP XML files containing:

- Personal information (Zavezanec)
- Trade details (Napovedi)
  - Year (Leto)
  - Asset type (VrstaVrednostnegaPapirja)
  - Country (Drzava)
  - Name (Naziv)
  - Purchase date and details (DatumNakupa, StroskiNakupa, VrednostNakupa)
  - Sale date and details (DatumProdaje, StroskiProdaje, VrednostProdaje)

## Exchange Rate Handling

- The script automatically converts all amounts to EUR
- Exchange rates are fetched from multiple APIs (ECB, Frankfurter, VATComply)
- Rates are cached to minimize API calls
- Fallback rates are used if APIs are unavailable

## Error Handling

The script provides clear success/failure messages for each file:

- `SUCCESS: filename.xml transformed and validated. Output: output/filename.xml`
- `FAIL: filename.xml did not pass XSD validation`
- `FAIL: Error processing filename.xml: error message`

## Notes

- The script processes both closed lots and individual trades
- If no lots are found, it will process trades directly
- All amounts are converted to EUR using exchange rates from the transaction date
- The output is validated against the DOH-KDVP XSD schema
