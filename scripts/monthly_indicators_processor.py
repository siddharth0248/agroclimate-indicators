#!/usr/bin/env python3
"""
Monthly Climate Indicators Processor for NLDAS-3 Data

This script processes daily NLDAS-3 data to calculate monthly Growing Degree Days (GDD),
Heat Stress Days (HSD), and Frost Days, then saves them as monthly NetCDF files.

Each monthly file contains all three indicators as variables:
- gdd: Growing Degree Days (base 10°C)
- hsd: Heat Stress Days (max temp > 30°C)
- frost_days: Frost Days (min temp < 0°C)

Output files are named: GDD-YYYYMM.nc (e.g., GDD-200001.nc for January 2000)
"""

import xarray as xr
import os
import glob
import numpy as np
from datetime import datetime
import pandas as pd

def process_monthly_indicators(data_dir="/Volumes/Chinmay_2TB/NLDAS3_AgroClimatic_vars/NLDAS3/", output_dir="/Volumes/Chinmay_2TB/NLDAS3_AgroClimatic_vars/NLDAS3/monthly_indicators"):
    """
    Process daily NLDAS-3 data to calculate and save monthly climate indicators.
    
    Parameters:
    -----------
    data_dir : str
        Directory containing daily NLDAS-3 files
    output_dir : str  
        Directory to save monthly indicator files
    """
    
    # Configuration
    files = sorted(glob.glob(os.path.join(data_dir, "NLDAS_FOR0010_D.A*.nc")))
    
    # Define thresholds for calculations
    GDD_BASE_TEMP_C = 10    # Growing Degree Days base temperature in Celsius
    HSD_THRESHOLD_C = 30    # Heat Stress Days threshold in Celsius
    FROST_THRESHOLD_C = 0   # Frost Days threshold in Celsius
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    if not files:
        print(f"Error: No NLDAS files found in {data_dir} with pattern NLDAS_FOR0010_D.A*.nc")
        return
    
    print(f"Found {len(files)} NLDAS files")
    print("Opening NLDAS files and processing...")
    
    # Open all files as a single dataset
    ds = xr.open_mfdataset(files, combine='by_coords', chunks={'time': 30})
    
    # Convert temperatures to Celsius
    print("Converting temperatures to Celsius...")
    ds['tasmin_C'] = ds['Tair_min'] - 273.15
    ds['tasmin_C'].attrs['units'] = 'degC'
    ds['tasmin_C'].attrs['long_name'] = 'Daily minimum air temperature in Celsius'
    
    ds['tasmax_C'] = ds['Tair_max'] - 273.15
    ds['tasmax_C'].attrs['units'] = 'degC'
    ds['tasmax_C'].attrs['long_name'] = 'Daily maximum air temperature in Celsius'
    
    ds['tas_C'] = (ds['tasmin_C'] + ds['tasmax_C']) / 2
    ds['tas_C'].attrs['units'] = 'degC'
    ds['tas_C'].attrs['long_name'] = 'Daily mean air temperature in Celsius'
    
    print("Calculating monthly indicators...")
    
    # 1. Growing Degree Days (GDD)
    print("  - Growing Degree Days...")
    gdd_daily_contribution = np.maximum(0, ds['tas_C'] - GDD_BASE_TEMP_C)
    gdd_monthly = gdd_daily_contribution.resample(time='MS').sum(dim='time', skipna=True)
    gdd_monthly.name = 'gdd'
    gdd_monthly.attrs['units'] = 'degC.days'
    gdd_monthly.attrs['long_name'] = f'Monthly Growing Degree Days (base {GDD_BASE_TEMP_C}°C)'
    gdd_monthly.attrs['description'] = f'Sum of daily mean temperature minus {GDD_BASE_TEMP_C}°C for temperatures above base'
    
    # 2. Heat Stress Days (HSD)
    print("  - Heat Stress Days...")
    hsd_daily_flag = (ds['tasmax_C'] > HSD_THRESHOLD_C).astype(int)
    hsd_monthly = hsd_daily_flag.resample(time='MS').sum(dim='time', skipna=True)
    hsd_monthly.name = 'hsd'
    hsd_monthly.attrs['units'] = 'days'
    hsd_monthly.attrs['long_name'] = f'Monthly Heat Stress Days (max temp > {HSD_THRESHOLD_C}°C)'
    hsd_monthly.attrs['description'] = f'Number of days with maximum temperature above {HSD_THRESHOLD_C}°C'
    
    # 3. Frost Days
    print("  - Frost Days...")
    frost_daily_flag = (ds['tasmin_C'] < FROST_THRESHOLD_C).astype(int)
    frost_monthly = frost_daily_flag.resample(time='MS').sum(dim='time', skipna=True)
    frost_monthly.name = 'frost_days'
    frost_monthly.attrs['units'] = 'days'
    frost_monthly.attrs['long_name'] = f'Monthly Frost Days (min temp < {FROST_THRESHOLD_C}°C)'
    frost_monthly.attrs['description'] = f'Number of days with minimum temperature below {FROST_THRESHOLD_C}°C'
    
    print("Saving monthly files...")
    
    # Get unique year-month combinations
    time_index = pd.to_datetime(gdd_monthly.time.values)
    
    # Process each month
    for i, time_val in enumerate(time_index):
        year_month = time_val.strftime('%Y%m')
        output_filename = f"agroclim_indicator-{year_month}.nc"
        output_path = os.path.join(output_dir, output_filename)
        
        print(f"  Processing {time_val.strftime('%Y-%m')} -> {output_filename}")
        
        # Select data for this month
        month_gdd = gdd_monthly.isel(time=i)
        month_hsd = hsd_monthly.isel(time=i)
        month_frost = frost_monthly.isel(time=i)
        
        # Create combined dataset for this month
        monthly_ds = xr.Dataset({
            'gdd': month_gdd,
            'hsd': month_hsd,
            'frost_days': month_frost
        })
        
        # Add global attributes
        monthly_ds.attrs['title'] = f'Monthly Climate Indicators for {time_val.strftime("%B %Y")}'
        monthly_ds.attrs['description'] = 'Monthly Growing Degree Days, Heat Stress Days, and Frost Days calculated from NLDAS-3 daily data'
        monthly_ds.attrs['source'] = 'NLDAS-3 daily meteorological data'
        monthly_ds.attrs['created'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        monthly_ds.attrs['gdd_base_temperature'] = f'{GDD_BASE_TEMP_C}°C'
        monthly_ds.attrs['hsd_threshold'] = f'{HSD_THRESHOLD_C}°C'
        monthly_ds.attrs['frost_threshold'] = f'{FROST_THRESHOLD_C}°C'
        monthly_ds.attrs['conventions'] = 'CF-1.6'
        
        # Save to NetCDF file
        monthly_ds.to_netcdf(output_path, 
                           encoding={
                               'gdd': {'zlib': True, 'complevel': 4},
                               'hsd': {'zlib': True, 'complevel': 4},
                               'frost_days': {'zlib': True, 'complevel': 4}
                           })
        
        print(f"    Saved: {output_path}")
    
    print(f"\nProcessing complete! Monthly files saved to: {output_dir}")
    print(f"Total months processed: {len(time_index)}")
    
    # Close the dataset
    ds.close()

if __name__ == "__main__":
    # You can modify these paths as needed
    data_directory = "/Volumes/Chinmay_2TB/NLDAS3_AgroClimatic_vars/NLDAS3/"
    output_directory = "/Volumes/Chinmay_2TB/NLDAS3_AgroClimatic_vars/NLDAS3/monthly_indicators"
    
    print("Monthly Climate Indicators Processor")
    print("=" * 50)
    print(f"Input directory: {data_directory}")
    print(f"Output directory: {output_directory}")
    print()
    
    process_monthly_indicators(data_directory, output_directory)