"""
Export Available Fields, Operators, and Wrappers
将所有可用的字段、运算符和包装器导出到分类的 txt 文件中
"""

import sys
import json
import logging
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.append('.')

from adaptive_alpha_miner import AdaptiveAlphaMiner

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def export_to_txt(data_fields, operators, wrappers, region='USA', output_file='available_components.txt'):
    """
    Export fields, operators, and wrappers to a well-formatted txt file
    
    Args:
        data_fields: List of data field dictionaries
        operators: List of operator dictionaries
        wrappers: List of wrapper tuples
        region: Region name
        output_file: Output filename
    """
    
    with open(output_file, 'w', encoding='utf-8') as f:
        # Header
        f.write("=" * 80 + "\n")
        f.write("WorldQuant Brain - Available Components\n")
        f.write(f"Region: {region}\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 80 + "\n\n")
        
        # ==================== DATA FIELDS ====================
        f.write("╔" + "=" * 78 + "╗\n")
        f.write("║" + " " * 25 + "DATA FIELDS" + " " * 42 + "║\n")
        f.write("╚" + "=" * 78 + "╝\n\n")
        
        f.write(f"Total Fields: {len(data_fields)}\n")
        f.write("-" * 80 + "\n\n")
        
        # Group fields by dataset prefix
        field_groups = {}
        for field in data_fields:
            field_id = field['id']
            # Extract prefix (e.g., 'fn_def', 'anl4', 'fnd6')
            if '_' in field_id:
                prefix = field_id.split('_')[0]
                if len(field_id.split('_')) > 1:
                    prefix = '_'.join(field_id.split('_')[:2])
            else:
                prefix = 'basic'
            
            if prefix not in field_groups:
                field_groups[prefix] = []
            field_groups[prefix].append(field)
        
        # Write grouped fields
        for group_name in sorted(field_groups.keys()):
            fields_in_group = field_groups[group_name]
            f.write(f"【{group_name.upper()} - {len(fields_in_group)} fields】\n")
            f.write("-" * 80 + "\n")
            
            for i, field in enumerate(sorted(fields_in_group, key=lambda x: x['id']), 1):
                field_id = field['id']
                desc = field.get('description', 'No description')
                dataset = field.get('dataset', {})
                dataset_id = dataset.get('id', 'Unknown') if isinstance(dataset, dict) else 'Unknown'
                
                f.write(f"{i:3d}. {field_id}\n")
                f.write(f"     Dataset: {dataset_id}\n")
                f.write(f"     Description: {desc}\n")
                f.write("\n")
            
            f.write("\n")
        
        # ==================== OPERATORS ====================
        f.write("\n" + "=" * 80 + "\n")
        f.write("╔" + "=" * 78 + "╗\n")
        f.write("║" + " " * 25 + "OPERATORS" + " " * 44 + "║\n")
        f.write("╚" + "=" * 78 + "╝\n\n")
        
        f.write(f"Total Operators: {len(operators)}\n")
        f.write("-" * 80 + "\n\n")
        
        # Group operators by category
        operator_groups = {}
        for op in operators:
            category = op.get('category', 'Uncategorized')
            if category not in operator_groups:
                operator_groups[category] = []
            operator_groups[category].append(op)
        
        # Write grouped operators
        for category in sorted(operator_groups.keys()):
            ops_in_category = operator_groups[category]
            f.write(f"【{category.upper()} - {len(ops_in_category)} operators】\n")
            f.write("-" * 80 + "\n")
            
            for i, op in enumerate(sorted(ops_in_category, key=lambda x: x['name']), 1):
                op_name = op['name']
                op_type = op.get('type', 'UNKNOWN')
                definition = op.get('definition', 'No definition')
                desc = op.get('description', 'No description')
                
                f.write(f"{i:3d}. {op_name} ({op_type})\n")
                f.write(f"     Definition: {definition}\n")
                f.write(f"     Description: {desc}\n")
                f.write("\n")
            
            f.write("\n")
        
        # ==================== WRAPPERS ====================
        f.write("\n" + "=" * 80 + "\n")
        f.write("╔" + "=" * 78 + "╗\n")
        f.write("║" + " " * 25 + "WRAPPERS" + " " * 45 + "║\n")
        f.write("╚" + "=" * 78 + "╝\n\n")
        
        f.write(f"Total Wrappers: {len(wrappers)}\n")
        f.write("-" * 80 + "\n\n")
        
        for i, (wrapper_name, wrapper_desc) in enumerate(wrappers, 1):
            f.write(f"{i:3d}. {wrapper_name}\n")
            f.write(f"     Description: {wrapper_desc}\n")
            f.write("\n")
        
        # ==================== STATISTICS ====================
        f.write("\n" + "=" * 80 + "\n")
        f.write("╔" + "=" * 78 + "╗\n")
        f.write("║" + " " * 25 + "STATISTICS" + " " * 43 + "║\n")
        f.write("╚" + "=" * 78 + "╝\n\n")
        
        f.write(f"Total Data Fields:    {len(data_fields):5d}\n")
        f.write(f"Total Operators:      {len(operators):5d}\n")
        f.write(f"Total Wrappers:       {len(wrappers):5d}\n")
        f.write(f"Field Groups:         {len(field_groups):5d}\n")
        f.write(f"Operator Categories:  {len(operator_groups):5d}\n")
        f.write("\n")
        
        # ==================== SUMMARY BY CATEGORY ====================
        f.write("Operator Categories Summary:\n")
        f.write("-" * 80 + "\n")
        for category in sorted(operator_groups.keys()):
            f.write(f"  {category:30s}: {len(operator_groups[category]):3d} operators\n")
        
        f.write("\n")
        f.write("Field Groups Summary:\n")
        f.write("-" * 80 + "\n")
        for group_name in sorted(field_groups.keys()):
            f.write(f"  {group_name:30s}: {len(field_groups[group_name]):3d} fields\n")
        
        f.write("\n" + "=" * 80 + "\n")
        f.write("End of Report\n")
        f.write("=" * 80 + "\n")


def export_to_json(data_fields, operators, wrappers, region='USA', output_file='available_components.json'):
    """Export to JSON format for programmatic use"""
    
    data = {
        'metadata': {
            'region': region,
            'generated_at': datetime.now().isoformat(),
            'total_fields': len(data_fields),
            'total_operators': len(operators),
            'total_wrappers': len(wrappers)
        },
        'data_fields': data_fields,
        'operators': operators,
        'wrappers': [{'name': w[0], 'description': w[1]} for w in wrappers]
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def export_summary(data_fields, operators, wrappers, region, output_file, dataset_groups):
    """Export summary information only"""
    
    # Group operators by category
    operator_groups = {}
    for op in operators:
        category = op.get('category', 'Uncategorized')
        if category not in operator_groups:
            operator_groups[category] = []
        operator_groups[category].append(op)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("WorldQuant Brain - Components Summary\n")
        f.write(f"Region: {region}\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 80 + "\n\n")
        
        f.write(f"Total Data Fields:    {len(data_fields):5d}\n")
        f.write(f"Total Datasets:       {len(dataset_groups):5d}\n")
        f.write(f"Total Operators:      {len(operators):5d}\n\n")
        
        f.write("=" * 80 + "\n")
        f.write("DATASETS\n")
        f.write("=" * 80 + "\n\n")
        
        for dataset_id in sorted(dataset_groups.keys()):
            fields = dataset_groups[dataset_id]
            f.write(f"{dataset_id:30s}: {len(fields):5d} fields\n")
        
        f.write("\n" + "=" * 80 + "\n")
        f.write("OPERATOR CATEGORIES\n")
        f.write("=" * 80 + "\n\n")
        
        for category in sorted(operator_groups.keys()):
            ops = operator_groups[category]
            f.write(f"{category:30s}: {len(ops):3d} operators\n")
        
        f.write("\n" + "=" * 80 + "\n")
        f.write("FILE STRUCTURE\n")
        f.write("=" * 80 + "\n\n")
        f.write("SUMMARY.txt              - This file (overview & statistics)\n")
        f.write("operators.txt            - All operators (some marked as [WRAPPER])\n")
        f.write("\nfields/                  - Directory containing dataset files\n")
        for dataset_id in sorted(dataset_groups.keys()):
            f.write(f"  fields/{dataset_id}.txt\n")
        
        f.write("\n" + "=" * 80 + "\n")
        f.write("COMMONLY USED WRAPPERS\n")
        f.write("=" * 80 + "\n\n")
        f.write("These operators are commonly used to wrap other operators:\n\n")
        for name, desc in wrappers:
            f.write(f"  - {name}: {desc}\n")
        f.write("\nSee operators.txt for full details (marked with [WRAPPER] tag)\n")
        
        f.write("\n" + "=" * 80 + "\n")


def export_by_dataset(data_fields, region, output_dir):
    """Export fields grouped by dataset into separate files"""
    
    # Group fields by dataset
    dataset_groups = {}
    for field in data_fields:
        dataset = field.get('dataset', {})
        dataset_id = dataset.get('id', 'Unknown') if isinstance(dataset, dict) else 'Unknown'
        if dataset_id not in dataset_groups:
            dataset_groups[dataset_id] = []
        dataset_groups[dataset_id].append(field)
    
    # Export each dataset to its own file
    for dataset_id, fields in sorted(dataset_groups.items()):
        output_file = Path(output_dir) / f'{dataset_id}.txt'
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write(f"Dataset: {dataset_id}\n")
            f.write(f"Region: {region}\n")
            f.write(f"Total Fields: {len(fields)}\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 80 + "\n\n")
            
            for i, field in enumerate(sorted(fields, key=lambda x: x['id']), 1):
                field_id = field['id']
                desc = field.get('description', 'No description')
                
                f.write(f"{i:4d}. {field_id}\n")
                f.write(f"      {desc}\n")
                f.write("\n")
        
        print(f"  - {dataset_id}.txt ({len(fields)} fields)")


def export_operators_with_wrappers(operators, output_file, wrapper_names):
    """Export operators to a separate file with wrapper annotations"""
    
    # Group operators by category
    operator_groups = {}
    for op in operators:
        category = op.get('category', 'Uncategorized')
        if category not in operator_groups:
            operator_groups[category] = []
        operator_groups[category].append(op)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("WorldQuant Brain - Operators\n")
        f.write(f"Total Operators: {len(operators)}\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 80 + "\n\n")
        
        f.write("Note: Operators marked with [WRAPPER] are commonly used to wrap other\n")
        f.write("      operators/fields. Example: winsorize(ts_std_dev(close, 60), std=4)\n")
        f.write("\n" + "-" * 80 + "\n\n")
        
        for category in sorted(operator_groups.keys()):
            ops_in_category = operator_groups[category]
            f.write(f"{'='*80}\n")
            f.write(f"{category.upper()} ({len(ops_in_category)} operators)\n")
            f.write(f"{'='*80}\n\n")
            
            for i, op in enumerate(sorted(ops_in_category, key=lambda x: x['name']), 1):
                op_name = op['name']
                op_type = op.get('type', 'UNKNOWN')
                definition = op.get('definition', 'No definition')
                desc = op.get('description', 'No description')
                
                # Mark if it's commonly used as a wrapper
                wrapper_tag = " [WRAPPER]" if op_name in wrapper_names else ""
                
                f.write(f"{i:3d}. {op_name} ({op_type}){wrapper_tag}\n")
                f.write(f"     Definition: {definition}\n")
                f.write(f"     Description: {desc}\n")
                f.write("\n")
            
            f.write("\n")


def export_wrappers_only(wrappers, output_file, operators):
    """Export wrappers to a separate file with details from operators"""
    
    # Wrapper names we're looking for
    wrapper_names = [name for name, _ in wrappers]
    
    # Find wrapper details in operators
    wrapper_details = {}
    for op in operators:
        if op['name'] in wrapper_names:
            wrapper_details[op['name']] = {
                'definition': op.get('definition', 'No definition'),
                'description': op.get('description', 'No description'),
                'type': op.get('type', 'UNKNOWN'),
                'category': op.get('category', 'Unknown')
            }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("WorldQuant Brain - Wrappers\n")
        f.write(f"Total Wrappers: {len(wrappers)}\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 80 + "\n\n")
        
        f.write("Wrappers are operators that can wrap other operators/fields to modify their\n")
        f.write("behavior. They are commonly used to handle data quality issues or transform\n")
        f.write("data before applying other operations.\n\n")
        f.write("Common usage: wrapper(operator(field, lookback), wrapper_parameters)\n")
        f.write("-" * 80 + "\n\n")
        
        for i, (wrapper_name, _) in enumerate(wrappers, 1):
            f.write(f"{i}. {wrapper_name}")
            
            if wrapper_name in wrapper_details:
                details = wrapper_details[wrapper_name]
                f.write(f" ({details['type']})\n")
                f.write(f"   Definition: {details['definition']}\n")
                f.write(f"   Description: {details['description']}\n")
                f.write(f"   Category: {details['category']}\n")
            else:
                f.write("\n")
                f.write(f"   Description: No details available from API\n")
            
            f.write("\n")
        
        f.write("-" * 80 + "\n")
        f.write("\nCommon Usage Examples:\n\n")
        
        f.write("1. winsorize - Trim extreme values\n")
        f.write("   winsorize(ts_std_dev(close, 60), std=4)\n")
        f.write("   - Limits values to within 4 standard deviations\n\n")
        
        f.write("2. ts_backfill - Fill missing values backward\n")
        f.write("   ts_backfill(ts_delta(volume, 5), 20)\n")
        f.write("   - Fills NaN values using previous non-NaN values\n\n")
        
        f.write("3. ts_scale - Scale to range [0, 1]\n")
        f.write("   ts_scale(rank(returns), 60)\n")
        f.write("   - Scales values to [0, 1] range over 60 days\n\n")
        
        f.write("4. Combining multiple wrappers\n")
        f.write("   winsorize(ts_backfill(fundamental_field, 20), std=3)\n")
        f.write("   - First backfill NaNs, then trim outliers\n")
        
        f.write("\n" + "=" * 80 + "\n")
        f.write("\nNote: Wrappers are actually operators from the API.\n")
        f.write("Check operators.txt for complete list of available operators.\n")
        f.write("=" * 80 + "\n")


def get_all_data_fields(generator, region, universe='TOP3000'):
    """Get ALL data fields for a region (not just random samples)"""
    all_fields = []
    
    for delay in [0, 1]:
        if delay == 0 and region in ["ASI", "CHN"]:
            continue  # ASI and CHN only support delay=1
        
        print(f"  Fetching fields with delay={delay}...")
        
        # Get datasets
        datasets_params = {
            'delay': delay,
            'instrumentType': 'EQUITY',
            'region': region,
            'universe': universe,
            'limit': 50  # API limit
        }
        
        datasets_response = generator.sess.get('https://api.worldquantbrain.com/data-sets', params=datasets_params)
        
        if datasets_response.status_code == 200:
            datasets_data = datasets_response.json()
            available_datasets = datasets_data.get('results', [])
            dataset_ids = [ds.get('id') for ds in available_datasets if ds.get('id')]
            print(f"    Found {len(dataset_ids)} datasets: {dataset_ids[:10]}")  # Show first 10
            
            # Get ALL fields from each dataset
            for dataset in dataset_ids:
                params = {
                    'delay': delay,
                    'instrumentType': 'EQUITY',
                    'region': region,
                    'universe': universe,
                    'dataset.id': dataset,
                    'limit': 50,  # Fetch 50 at a time (API limit)
                    'offset': 0
                }
                
                # Get total count first
                count_response = generator.sess.get('https://api.worldquantbrain.com/data-fields', params={**params, 'limit': 1})
                
                if count_response.status_code == 200:
                    total_fields = count_response.json().get('count', 0)
                    print(f"    {dataset}: {total_fields} fields", end='')
                    
                    if total_fields > 0:
                        # Fetch all fields with pagination
                        offset = 0
                        while offset < total_fields:
                            params['offset'] = offset
                            params['limit'] = min(50, total_fields - offset)  # API limit is 50
                            
                            response = generator.sess.get('https://api.worldquantbrain.com/data-fields', params=params)
                            
                            if response.status_code == 200:
                                fields = response.json().get('results', [])
                                all_fields.extend(fields)
                                offset += len(fields)
                            else:
                                print(f" [ERROR: {response.status_code}]")
                                break
                        
                        print(" [OK]")
        else:
            print(f"    ERROR: Failed to get datasets (status {datasets_response.status_code})")
            print(f"    Response: {datasets_response.text[:200]}")
    
    # Remove duplicates
    unique_fields = {field['id']: field for field in all_fields}
    return list(unique_fields.values())


def main():
    """Main function to export all available components"""
    
    print("=" * 80)
    print("Exporting WorldQuant Brain Available Components")
    print("=" * 80)
    print()
    
    # Configuration
    credentials_path = 'credential.txt'
    region = 'USA'
    
    print(f"Region: {region}")
    print()
    
    try:
        print("Authenticating with WorldQuant Brain API...")
        from alpha_generator_ollama import AlphaGenerator
        temp_generator = AlphaGenerator(
            credentials_path=credentials_path,
            ollama_url='http://localhost:11434'
        )
        print("[OK] Authentication successful")
        print()
        
        print("Fetching ALL data fields from WorldQuant API...")
        data_fields = get_all_data_fields(temp_generator, region)
        
        print(f"[OK] Found {len(data_fields)} data fields")
        
        # Get operators
        print("Fetching operators from WorldQuant API...")
        operators = temp_generator.get_operators()
        print(f"[OK] Found {len(operators)} operators")
        
        # Get wrappers (hardcoded list)
        wrappers = [
            ("winsorize", "Winsorizes data to specified standard deviations"),
            ("ts_backfill", "Backfills missing values in time series"),
            ("ts_forward_fill", "Forward fills missing values in time series"),
            ("ts_clean", "Cleans time series data"),
            ("ts_scale", "Scales time series data"),
            ("ts_normalize", "Normalizes time series data")
        ]
        print(f"[OK] Found {len(wrappers)} wrappers")
        
        # Create output directories
        import os
        base_dir = f'available_components_{region}'
        fields_dir = os.path.join(base_dir, 'fields')
        os.makedirs(fields_dir, exist_ok=True)
        print(f"\nCreating directory structure:")
        print(f"  {base_dir}/")
        print(f"  {base_dir}/fields/")
        
        # Group fields by dataset
        dataset_groups = {}
        for field in data_fields:
            dataset = field.get('dataset', {})
            dataset_id = dataset.get('id', 'Unknown') if isinstance(dataset, dict) else 'Unknown'
            if dataset_id not in dataset_groups:
                dataset_groups[dataset_id] = []
            dataset_groups[dataset_id].append(field)
        
        # Export summary
        summary_txt = os.path.join(base_dir, 'SUMMARY.txt')
        print(f"\nExporting summary to {summary_txt}...")
        export_summary(data_fields, operators, wrappers, region, summary_txt, dataset_groups)
        print(f"[OK] Summary export complete")
        
        # Export fields by dataset
        print(f"\nExporting fields to {fields_dir}/...")
        export_by_dataset(data_fields, region, fields_dir)
        print(f"[OK] {len(dataset_groups)} dataset files exported")
        
        # Export operators (with wrapper annotations)
        operators_txt = os.path.join(base_dir, 'operators.txt')
        print(f"\nExporting operators to {operators_txt}...")
        wrapper_names = [name for name, _ in wrappers]
        export_operators_with_wrappers(operators, operators_txt, wrapper_names)
        print(f"[OK] Operators export complete")
        
        print("\n" + "=" * 80)
        print("Export Complete!")
        print("=" * 80)
        print(f"\nGenerated directory: {base_dir}/")
        print(f"\nStructure:")
        print(f"  {base_dir}/")
        print(f"  ├── SUMMARY.txt         (Overview and statistics)")
        print(f"  ├── operators.txt       (All {len(operators)} operators, {len(wrappers)} marked as wrappers)")
        print(f"  └── fields/             ({len(dataset_groups)} dataset files)")
        print()
        
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())

