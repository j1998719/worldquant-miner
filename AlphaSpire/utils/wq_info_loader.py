import json
import logging
from pathlib import Path
from typing import List, Dict

import requests
import pandas as pd
from requests.auth import HTTPBasicAuth
from utils.config_loader import ConfigLoader

# --- 目录 ---
BASE_DIR = Path(__file__).resolve().parents[1]
WQ_FIELD_DIR = BASE_DIR / "data" / "wq_fields"
WQ_FIELD_DIR.mkdir(parents=True, exist_ok=True)
WQ_OPERATOR_DIR = BASE_DIR / "data" / "wq_operators"
WQ_OPERATOR_DIR.mkdir(parents=True, exist_ok=True)

FIELDS_CSV = WQ_FIELD_DIR
OPERATORS_CSV = WQ_OPERATOR_DIR / "operators.csv"


class OpAndFeature:
    def __init__(self):
        self.sess = requests.Session()
        username = ConfigLoader.get("worldquant_account")
        password = ConfigLoader.get("worldquant_password")
        self.setup_auth(username, password)

    def setup_auth(self, username, password) -> None:
        """Set up authentication with WorldQuant Brain."""
        self.sess.auth = HTTPBasicAuth(username, password)

        print("Authenticating with WorldQuant Brain...")
        response = self.sess.post('https://api.worldquantbrain.com/authentication')
        print(f"Authentication response status: {response.status_code}")
        logging.debug(f"Authentication response: {response.text[:500]}...")

        if response.status_code != 201:
            raise Exception(f"Authentication failed: {response.text}")

    def get_data_fields(self):
        """
        Fetch available data fields from WorldQuant Brain.
        Dynamically discovers available datasets instead of using hardcoded list.
        """
        from utils.config_loader import ConfigLoader
        
        # Get configuration
        region = ConfigLoader.get('worldquant_region', 'USA')
        universe = ConfigLoader.get('worldquant_universe', 'TOP3000')
        
        print(f"Fetching data fields for region={region}, universe={universe}")
        
        try:
            # Fetch for both delay values (if supported by region)
            delays = [1] if region in ["ASI", "CHN"] else [0, 1]
            
            for delay in delays:
                print(f"\n{'='*80}")
                print(f"Fetching fields with delay={delay}")
                print(f"{'='*80}")
                
                # Step 1: Get available datasets for this configuration
                datasets_params = {
                    'delay': delay,
                    'instrumentType': 'EQUITY',
                    'region': region,
                    'universe': universe,
                    'limit': 50  # API maximum limit
                }
                
                print("Getting available datasets from API...")
                datasets_response = self.sess.get('https://api.worldquantbrain.com/data-sets', 
                                                  params=datasets_params)
                
                if datasets_response.status_code != 200:
                    print(f"❌ Failed to get datasets: {datasets_response.status_code}")
                    print(f"   Response: {datasets_response.text[:500]}")
                    continue
                
                datasets_data = datasets_response.json()
                available_datasets = datasets_data.get('results', [])
                dataset_ids = [ds.get('id') for ds in available_datasets if ds.get('id')]
                
                print(f"✅ Found {len(dataset_ids)} available datasets")
                print(f"   Datasets: {dataset_ids[:20]}...")  # Show first 20
                
                # Step 2: Fetch ALL fields from each available dataset
                for dataset in dataset_ids:
                    des = FIELDS_CSV / f"{dataset}.csv"
                    
                    if des.exists():
                        print(f"⏭️  {dataset}: Already exists, skipping")
                        continue
                    
                    print(f"📥 {dataset}: ", end='', flush=True)
                    
                    all_fields = []
                    base_params = {
                        'delay': delay,
                        'instrumentType': 'EQUITY',
                        'region': region,
                        'universe': universe,
                        'dataset.id': dataset,
                        'limit': 50,  # API limit
                        'offset': 0
                    }
                    
                    # Get total count first
                    count_response = self.sess.get('https://api.worldquantbrain.com/data-fields', 
                                                   params={**base_params, 'limit': 1})
                    
                    if count_response.status_code != 200:
                        print(f"❌ Failed to get count")
                        continue
                    
                    total_fields = count_response.json().get('count', 0)
                    print(f"{total_fields} fields", end='', flush=True)
                    
                    if total_fields == 0:
                        print(" [EMPTY]")
                        # Still create empty CSV
                        df = pd.DataFrame()
                        df.to_csv(des, index=False, encoding='utf-8')
                        continue
                    
                    # Fetch all fields with pagination
                    offset = 0
                    while offset < total_fields:
                        params = base_params.copy()
                        params['offset'] = offset
                        params['limit'] = min(50, total_fields - offset)
                        
                        response = self.sess.get('https://api.worldquantbrain.com/data-fields', 
                                               params=params)
                        
                        if response.status_code == 200:
                            fields = response.json().get('results', [])
                            all_fields.extend(fields)
                            offset += len(fields)
                            print('.', end='', flush=True)
                        else:
                            print(f" [ERROR at offset {offset}]")
                            break
                    
                    # Remove duplicates
                    unique_fields = {field['id']: field for field in all_fields}
                    unique_fields = list(unique_fields.values())
                    
                    # Save to CSV
                    if unique_fields:
                        df = pd.DataFrame(unique_fields)
                        df.to_csv(des, index=False, encoding='utf-8')
                        print(f" ✅ ({len(unique_fields)} unique)")
                    else:
                        print(" [NO DATA]")
            
            print(f"\n{'='*80}")
            print("✅ Data fields fetch complete")
            print(f"{'='*80}\n")
            
        except Exception as e:
            print(f"❌ Failed to fetch data fields: {e}")
            import traceback
            traceback.print_exc()

    def get_operators(self) -> List[Dict]:
        """Fetch available operators from WorldQuant Brain."""
        if OPERATORS_CSV.exists():
            print(f"Operators CSV already exists at {OPERATORS_CSV}, skipping download.")
            return pd.read_csv(OPERATORS_CSV).to_dict(orient='records')

        print("Requesting operators...")
        response = self.sess.get('https://api.worldquantbrain.com/operators')
        print(f"Operators response status: {response.status_code}")
        logging.debug(f"Operators response: {response.text[:500]}...")  # Print first 500 chars

        if response.status_code != 200:
            raise Exception(f"Failed to get operators: {response.text}")

        data = response.json()
        if isinstance(data, list):
            operators = data
        elif 'results' in data:
            operators = data['results']
        else:
            raise Exception(f"Unexpected operators response format. Response: {data}")

        df = pd.DataFrame(operators)
        df.to_csv(OPERATORS_CSV, index=False, encoding='utf-8')
        print(f"✅ Saved operators CSV to {OPERATORS_CSV}")

        return operators
