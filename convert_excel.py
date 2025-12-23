#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, '/Users/franciscoterpolilli/Library/Python/3.9/lib/python/site-packages')

import pandas as pd

def convert_excel_to_csv(excel_file, output_dir):
    """Convert each sheet in an Excel file to a separate CSV file."""
    try:
        # Read all sheets from the Excel file
        xls = pd.ExcelFile(excel_file)

        print(f"Found {len(xls.sheet_names)} sheets: {', '.join(xls.sheet_names)}")

        # Convert each sheet to CSV
        for sheet_name in xls.sheet_names:
            df = pd.read_excel(excel_file, sheet_name=sheet_name)
            csv_filename = os.path.join(output_dir, f"{sheet_name}.csv")
            df.to_csv(csv_filename, index=False)
            print(f"Converted '{sheet_name}' to '{csv_filename}' ({len(df)} rows)")

        print(f"\nSuccessfully converted {len(xls.sheet_names)} sheets to CSV files in {output_dir}")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    excel_file = "raw_data/GTM ENG – Challenge version.xlsx"
    output_dir = "raw_data"

    convert_excel_to_csv(excel_file, output_dir)
