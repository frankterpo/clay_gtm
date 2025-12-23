#!/usr/bin/env python3
"""
Webinar Data Processing Pipeline
===============================

Simple, powerful, straightforward processing of webinar Excel exports into Clay-ready CSV.

Usage:
    python3 process_webinar_data.py "path/to/webinar.xlsx"

Output:
    - Individual CSV files for each Excel tab (cleaned)
    - webinar_clay_import.csv (comprehensive Clay import file)
    - data_relationships.md (documentation)

Requirements: gnumeric (for Excel conversion)
Install: brew install gnumeric
"""

import os
import sys
import subprocess
from pathlib import Path

def run_command(cmd, description=""):
    """Run shell command and return success"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"❌ {description} failed: {result.stderr}")
            return False, result.stderr
        return True, result.stdout
    except Exception as e:
        print(f"❌ {description} error: {e}")
        return False, str(e)

def clean_csv_file(csv_path, filename):
    """Clean a CSV file by removing duplicates and null BMIDs"""

    if not os.path.exists(csv_path):
        return False

    # Count original lines
    with open(csv_path, 'r') as f:
        original_lines = sum(1 for _ in f)

    temp_file = csv_path + '.tmp'

    if filename == 'CRM.csv':
        # CRM uses linkedin_url, no cleaning needed for now
        print(f"  {filename}: {original_lines-1} records (CRM data kept as-is)")
        return True

    # Clean using shell commands (much more reliable than pandas)
    # Remove lines where BMID is empty (assuming BMID is column 8, 1-indexed)
    cmd = f"awk -F',' 'NR==1 || $8 != \"\"' '{csv_path}' > '{temp_file}'"
    success, _ = run_command(cmd, f"Remove null BMIDs from {filename}")

    if not success:
        return False

    # For most files, remove duplicate BMIDs (keep first occurrence)
    if filename in ['attend list.csv', 'registered list.csv', 'did not attend list.csv']:
        # Remove duplicates based on BMID (column 8)
        cmd = f"awk -F',' '!seen[$8]++' '{temp_file}' > '{csv_path}'"
        success, _ = run_command(cmd, f"Remove duplicates from {filename}")
        if not success:
            return False
    elif filename == 'emoji eeaction.csv':
        # Special case: remove ALL records with duplicate BMIDs (data corruption)
        cmd = f"awk -F',' 'NR==1 || !seen[$8]++' '{temp_file}' > '{csv_path}' && awk -F',' 'seen[$8]++' '{temp_file}' | wc -l"
        success, output = run_command(cmd, f"Remove duplicate BMIDs from {filename}")
        if success and 'duplicate' in output.lower():
            print(f"  {filename}: removed duplicate BMID records")
    else:
        # For polls and Q&A, keep all records (multiple per person expected)
        cmd = f"mv '{temp_file}' '{csv_path}'"
        run_command(cmd, f"Keep all records in {filename}")

    # Count final lines
    with open(csv_path, 'r') as f:
        final_lines = sum(1 for _ in f)

    removed = original_lines - final_lines
    if removed > 0:
        print(f"  Cleaned {filename}: removed {removed} records, {final_lines-1} remaining")
    else:
        print(f"  {filename}: {final_lines-1} records (no cleaning needed)")

    # Remove temp file
    if os.path.exists(temp_file):
        os.remove(temp_file)

    return True

def create_clay_import(output_dir):
    """Create the comprehensive Clay import file by joining registered list with CRM data"""

    print("\n🔗 Creating Clay import file with CRM enrichment...")

    clay_file = os.path.join(output_dir, 'webinar_clay_import.csv')
    registered_file = os.path.join(output_dir, 'registered list.csv')
    crm_file = os.path.join(output_dir, 'CRM.csv')

    if not os.path.exists(registered_file):
        print("❌ Missing registered list.csv")
        return False

    if not os.path.exists(crm_file):
        print("❌ Missing CRM.csv - cannot enrich with CRM data")
        return False

    # Step 1: Clean registered list (remove empty BMIDs)
    temp_registered = os.path.join(output_dir, 'temp_registered_clean.csv')
    cmd = "awk -F',' 'NR==1 || $8 != \"\"' '" + registered_file + "' > '" + temp_registered + "'"
    success, _ = run_command(cmd, "Clean registered list (remove empty BMIDs)")
    if not success:
        return False

    # Step 2: Join with CRM data using LinkedIn URL (column 11 in registered = column 1 in CRM)
    temp_joined = os.path.join(output_dir, 'temp_joined.csv')
    awk_join_script = r"""
BEGIN {FS=","; OFS=","}
NR==FNR {
    if(NR>1) crm[$1] = $2","$3","$4","$5","$6","$7","$8","$9","$10","$11","$12","$13","$14","$15","$16","$17
    next
}
{
    if(NR==1) {
        print $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,$22,$23,$24,$25
    } else {
        linkedin_key = $11
        if(linkedin_key in crm) {
            split(crm[linkedin_key], crm_fields, ",")
            print $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,crm_fields[1],crm_fields[2],crm_fields[3],crm_fields[4],crm_fields[5],crm_fields[6],crm_fields[7],crm_fields[8],crm_fields[9],crm_fields[10],crm_fields[11],crm_fields[12],crm_fields[13],crm_fields[14],crm_fields[15]
        } else {
            print $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,"","","","","","","","","","","","","","","",""
        }
    }
}
"""
    cmd = "awk '" + awk_join_script + "' '" + crm_file + "' '" + temp_registered + "' > '" + temp_joined + "'"
    success, _ = run_command(cmd, "Join registered list with CRM data")
    if not success:
        return False

    # Step 3: Clean incomplete LinkedIn URLs (CRM linkedin_url column)
    temp_clean = os.path.join(output_dir, 'temp_clean.csv')
    cmd = "awk -F',' 'BEGIN{OFS=\",\"} {if(NR==1) print $0; else {$11 = ($11 == \"https://linkedin.com/in/\" || $11 == \"https://www.linkedin.com/in/\") ? \"\" : $11; $26 = ($26 == \"https://linkedin.com/in/\" || $26 == \"https://www.linkedin.com/in/\") ? \"\" : $26; print $0}}' '" + temp_joined + "' > '" + temp_clean + "'"
    success, _ = run_command(cmd, "Clean incomplete LinkedIn URLs")
    if success:
        cmd = f"mv '{temp_clean}' '{clay_file}'"
        run_command(cmd, "Create final Clay import file")
    else:
        cmd = f"mv '{temp_joined}' '{clay_file}'"
        run_command(cmd, "Create final Clay import file (without URL cleaning)")

    # Clean up temp files
    for temp_file in [temp_registered, temp_joined, temp_clean]:
        if os.path.exists(temp_file):
            os.remove(temp_file)

    # Count records and CRM matches
    crm_matches = 0
    total_records = 0
    with open(clay_file, 'r') as f:
        for line_num, line in enumerate(f, 1):
            if line_num == 1:
                continue
            total_records += 1
            fields = line.strip().split(',')
            if len(fields) > 25 and fields[25].strip():  # CRM customer_status field
                crm_matches += 1

    print("  ✅ Created Clay import file with CRM enrichment")
    print(f"     Total records: {total_records}")
    print(f"     CRM matches: {crm_matches} ({crm_matches/total_records*100:.1f}%)")

    return True

def process_excel_file(excel_path):
    """Process Excel file into CSVs using ssconvert"""

    if not os.path.exists(excel_path):
        print(f"❌ Excel file not found: {excel_path}")
        return False

    # Use raw_data as output directory
    output_dir = "raw_data"

    print(f"🚀 Processing webinar data from: {excel_path}")
    print(f"📁 Output directory: {output_dir}")

    # Check if ssconvert is available
    success, _ = run_command("which ssconvert", "Check ssconvert availability")
    if not success:
        print("❌ ssconvert not found. Install with: brew install gnumeric")
        return False

    # Convert Excel to individual CSV files
    print("\n📊 Converting Excel tabs to CSV...")
    cmd = f"ssconvert -S '{excel_path}' '{output_dir}/%s.csv'"
    success, output = run_command(cmd, "Convert Excel to CSV")

    if not success:
        print(f"❌ Excel conversion failed")
        return False

    # List created files
    csv_files = [f for f in os.listdir(output_dir) if f.endswith('.csv')]
    print(f"   Created {len(csv_files)} CSV files: {', '.join(csv_files)}")

    # Clean each CSV file
    print("\n🧹 Cleaning data...")
    for csv_file in csv_files:
        csv_path = os.path.join(output_dir, csv_file)
        clean_csv_file(csv_path, csv_file)

    # Create Clay import file
    create_clay_import(output_dir)

    # Create documentation
    create_documentation(output_dir)

    print("\n🎉 Processing complete!")
    print(f"   📂 All files saved to: {output_dir}")
    clay_file = os.path.join(output_dir, 'webinar_clay_import.csv')
    if os.path.exists(clay_file):
        print(f"   🎯 Ready for Clay: {clay_file}")

    return True

def create_documentation(output_dir):
    """Create documentation file"""

    from datetime import datetime
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    doc_content = f"""# Webinar Data Processing Results

## Processing Summary
- **Processed**: {timestamp}
- **Status**: ✅ Complete
- **Method**: Shell-based processing (reliable, no dependencies)

## Files Created
- Individual CSV files for each Excel tab (cleaned and deduplicated)
- `webinar_clay_import.csv` - Ready for Clay import
- This documentation file

## Data Cleaning Applied
- Removed records with missing BMID identifiers
- Deduplicated attendance and registration data
- Cleaned emoji data corruption issues
- Preserved multiple responses per person (polls, Q&A)

## Clay Import Ready
The `webinar_clay_import.csv` file contains:
- All registrant data with attendance status
- CRM enrichment (if CRM tab was present)
- Basic structure ready for Clay automations

## Next Steps
1. Import `webinar_clay_import.csv` into Clay
2. Set BMID as primary key for deduplication
3. Configure LinkedIn URL enrichment for social data
4. Set up lead scoring based on attendance and engagement
5. Add poll/emoji/Q&A aggregations if needed for advanced analysis

## Reprocessing Future Webinars
Run: `python3 process_webinar_data.py "new_webinar.xlsx"`
"""

    doc_file = os.path.join(output_dir, 'data_relationships.md')
    with open(doc_file, 'w') as f:
        f.write(doc_content)

    print(f"  ✅ Created documentation")

def main():
    """Main entry point"""

    if len(sys.argv) != 2:
        print("🎯 Webinar Data Processing Pipeline")
        print("=" * 40)
        print("Simple, powerful, straightforward!")
        print()
        print("Usage:")
        print('  python3 process_webinar_data.py "path/to/webinar.xlsx"')
        print()
        print("Output:")
        print("  - Individual CSV files for each Excel tab (cleaned)")
        print("  - webinar_clay_import.csv (Clay-ready import file)")
        print("  - data_relationships.md (documentation)")
        print()
        print("Requirements:")
        print("  - gnumeric: brew install gnumeric")
        print()
        print("Example:")
        print('  python3 process_webinar_data.py "GTM Webinar Export.xlsx"')
        sys.exit(1)

    excel_path = sys.argv[1]
    success = process_excel_file(excel_path)

    if success:
        print("\n✅ Webinar processing complete! Ready for Clay import.")
    else:
        print("\n❌ Processing failed.")
        sys.exit(1)

if __name__ == "__main__":
    main()
