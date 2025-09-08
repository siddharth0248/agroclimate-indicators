#!/usr/bin/env python
"""
Test script to check data types and NaN handling in agroclim indicator files.
"""

import xarray as xr
import numpy as np
import sys
import os

def check_file(file_path):
    """Check data types and NaN patterns in a file."""
    
    print(f"\nChecking file: {os.path.basename(file_path)}")
    print("=" * 60)
    
    with xr.open_dataset(file_path) as ds:
        print(f"Dimensions: {dict(ds.dims)}")
        print(f"Variables: {list(ds.data_vars)}")
        print()
        
        # Check each variable
        for var in ['gdd', 'hsd', 'frost_days']:
            if var not in ds:
                print(f"{var}: NOT FOUND")
                continue
            
            data = ds[var].values
            print(f"{var}:")
            print(f"  Shape: {data.shape}")
            print(f"  Dtype: {data.dtype}")
            
            # Handle different data types
            if data.dtype == np.dtype('timedelta64[ns]'):
                # Convert to days
                data_float = data.astype('float64') / (1e9 * 86400)
                print(f"  Converted to float days")
                
                # Check for zeros
                n_zeros = np.sum(data_float == 0)
                print(f"  Zeros: {n_zeros} ({100.0 * n_zeros / data.size:.1f}%)")
                
                # Use zeros as NaN
                data_float = np.where(data_float == 0, np.nan, data_float)
                data = data_float
            
            elif data.dtype in [np.dtype('int64'), np.dtype('int32')]:
                # Check for zeros
                n_zeros = np.sum(data == 0)
                print(f"  Zeros: {n_zeros} ({100.0 * n_zeros / data.size:.1f}%)")
                data = data.astype('float32')
            
            # Count NaN values
            n_nan = np.sum(np.isnan(data))
            n_valid = np.sum(~np.isnan(data))
            total = data.size
            
            print(f"  NaN values: {n_nan} ({100.0 * n_nan / total:.1f}%)")
            print(f"  Valid values: {n_valid} ({100.0 * n_valid / total:.1f}%)")
            
            # Statistics for valid data
            if n_valid > 0:
                valid_data = data[~np.isnan(data)]
                print(f"  Min: {np.min(valid_data):.2f}")
                print(f"  Max: {np.max(valid_data):.2f}")
                print(f"  Mean: {np.mean(valid_data):.2f}")
                print(f"  Unique values (first 10): {np.unique(valid_data)[:10]}")
            print()
        
        # Check if all variables have the same NaN pattern
        print("Checking NaN pattern consistency:")
        if 'gdd' in ds:
            gdd_nan = np.isnan(ds['gdd'].values)
            
            for var in ['hsd', 'frost_days']:
                if var in ds:
                    var_data = ds[var].values
                    
                    # Convert timedelta to float if needed
                    if var_data.dtype == np.dtype('timedelta64[ns]'):
                        var_data = var_data.astype('float64') / (1e9 * 86400)
                        var_zeros = (var_data == 0)
                        
                        # Check if zeros match GDD NaN pattern
                        match = np.sum(var_zeros == gdd_nan)
                        total = gdd_nan.size
                        print(f"  {var} zeros match GDD NaN: {100.0 * match / total:.1f}%")
                    
                    elif var_data.dtype in [np.dtype('int64'), np.dtype('int32')]:
                        var_zeros = (var_data == 0)
                        match = np.sum(var_zeros == gdd_nan)
                        total = gdd_nan.size
                        print(f"  {var} zeros match GDD NaN: {100.0 * match / total:.1f}%")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_data_types.py <file_path>")
        print("Example: python test_data_types.py /path/to/agroclim_indicator-201806.nc")
        sys.exit(1)
    
    file_path = sys.argv[1]
    
    if not os.path.exists(file_path):
        print(f"Error: File not found: {file_path}")
        sys.exit(1)
    
    check_file(file_path)