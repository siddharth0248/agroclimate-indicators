#!/usr/bin/env python3
"""
Simple script to run the monthly indicators processing.
This is a streamlined version that you can run directly.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from monthly_indicators_processor import process_monthly_indicators

if __name__ == "__main__":
    print("Starting Monthly Climate Indicators Processing")
    print("=" * 60)
    
    # Set your data paths here
    data_dir = "/Volumes/Chinmay_2TB/NLDAS3_AgroClimatic_vars/NLDAS3/"  # Adjust this path to your NLDAS data
    output_dir = "/Volumes/Chinmay_2TB/NLDAS3_AgroClimatic_vars/NLDAS3/monthly_indicators"  # Output directory for monthly files
    
    # Check if data directory exists
    if not os.path.exists(data_dir):
        print(f"Error: Data directory '{data_dir}' does not exist.")
        print("Please update the data_dir path in this script to point to your NLDAS-3 data.")
        sys.exit(1)
    
    try:
        # Run the processing
        process_monthly_indicators(data_dir, output_dir)
        print("\n" + "=" * 60)
        print("SUCCESS: Monthly processing completed!")
        print(f"Check the output directory: {output_dir}")
        
    except Exception as e:
        print(f"\nERROR: Processing failed with error: {e}")
        print("Please check your data paths and file formats.")
        sys.exit(1)