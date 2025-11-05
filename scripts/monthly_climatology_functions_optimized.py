"""
Optimized functions for computing monthly climatology from agroclim indicator files.
Uses chunking and lazy loading to minimize memory usage.
"""

import xarray as xr
import numpy as np
import pandas as pd
import glob
import os
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import warnings
import gc  # For garbage collection
warnings.filterwarnings('ignore')


def find_files_for_month(data_dir: str, month: int, pattern: str = "agroclim_indicator-*.nc") -> List[str]:
    """
    Find all files for a specific month across all years.
    
    Args:
        data_dir: Directory containing the monthly indicator files
        month: Month number (1-12)
        pattern: File pattern to match (default: "agroclim_indicator-*.nc")
    
    Returns:
        List of file paths for the specified month
    """
    # Get all files matching the pattern
    all_files = sorted(glob.glob(os.path.join(data_dir, pattern)))
    
    # Filter for the specific month
    month_files = []
    for file in all_files:
        # Extract YYYYMM from filename
        basename = os.path.basename(file)
        # Assuming format: agroclim_indicator-YYYYMM.nc
        try:
            year_month = basename.split('-')[1].split('.')[0]
            file_month = int(year_month[-2:])
            
            if file_month == month:
                month_files.append(file)
        except (IndexError, ValueError):
            continue
    
    return month_files


def compute_monthly_mean_chunked(
    month_files: List[str],
    variables: List[str],
    chunk_years: int = 5
) -> Dict[str, Dict]:
    """
    Compute climatological mean by processing files in year chunks.
    
    Args:
        month_files: List of file paths for the month
        variables: List of variable names to process
        chunk_years: Number of years to process at once
    
    Returns:
        Dictionary with means and statistics for each variable
    """
    results = {}
    
    # Initialize accumulators for each variable
    for var in variables:
        results[var] = {
            'sum': None,
            'sum_sq': None,
            'count': None,
            'min': None,
            'max': None,
            'years': []
        }
    
    # Adjust chunk_years if it's larger than the number of files
    if chunk_years > len(month_files):
        chunk_years = len(month_files)
        print(f"    Adjusted chunk size to {chunk_years} (total files available)")
    
    # Process files in chunks
    for i in range(0, len(month_files), chunk_years):
        chunk_files = month_files[i:i+chunk_years]
        n_chunks = (len(month_files) + chunk_years - 1) // chunk_years
        print(f"    Processing chunk {i//chunk_years + 1}/{n_chunks} ({len(chunk_files)} files)")
        
        # Load chunk with minimal memory footprint
        try:
            # Open datasets lazily
            datasets = []
            years = []
            
            for file in chunk_files:
                # Extract year
                basename = os.path.basename(file)
                year_month = basename.split('-')[1].split('.')[0]
                year = int(year_month[:4])
                
                # Open dataset with chunks for lazy loading
                ds = xr.open_dataset(file, chunks={'lat': 1000, 'lon': 1000})
                
                # Select only needed variables
                ds_vars = ds[variables] if all(v in ds for v in variables) else ds
                
                datasets.append(ds_vars)
                years.append(year)
            
            # Process each variable
            for var in variables:
                if not all(var in ds for ds in datasets):
                    print(f"      Warning: {var} not found in all files")
                    continue
                
                # Stack data for this chunk
                var_data = []
                for j, ds in enumerate(datasets):
                    if var in ds:
                        # Load data for this variable
                        data = ds[var].values
                        # Debug: Check data shape
                        if j == 0:
                            print(f"      {var} data shape: {data.shape}, dtype: {data.dtype}")
                        var_data.append(data)
                
                if not var_data:
                    continue
                
                # Convert to numpy array and ensure float type
                var_array = np.stack(var_data, axis=0)
                # Convert to float to avoid type errors with square operation
                var_array = var_array.astype(np.float32)
                
                # Create a mask for valid (non-NaN) values
                valid_mask = ~np.isnan(var_array)
                
                # Count valid values per pixel
                chunk_count = np.sum(valid_mask, axis=0)
                
                # Only compute statistics where we have valid data
                # Initialize with NaN and only fill where we have valid counts
                shape = var_array.shape[1:]  # Shape without the year dimension
                chunk_sum = np.full(shape, np.nan, dtype=np.float32)
                chunk_sum_sq = np.full(shape, np.nan, dtype=np.float32)
                chunk_min = np.full(shape, np.nan, dtype=np.float32)
                chunk_max = np.full(shape, np.nan, dtype=np.float32)
                
                # Compute statistics only for pixels with at least one valid value
                has_data = chunk_count > 0
                if np.any(has_data):
                    # Use nansum, nanmin, nanmax which ignore NaN values
                    chunk_sum[has_data] = np.nansum(var_array[:, has_data], axis=0)
                    chunk_sum_sq[has_data] = np.nansum(var_array[:, has_data]**2, axis=0)
                    chunk_min[has_data] = np.nanmin(var_array[:, has_data], axis=0)
                    chunk_max[has_data] = np.nanmax(var_array[:, has_data], axis=0)
                
                print(f"      {var} valid pixels in chunk: {np.sum(has_data)} / {chunk_count.size} "
                      f"({100.0 * np.sum(has_data) / chunk_count.size:.1f}%)")
                
                # Update accumulators (handling NaN properly)
                if results[var]['sum'] is None:
                    results[var]['sum'] = chunk_sum.copy()
                    results[var]['sum_sq'] = chunk_sum_sq.copy()
                    results[var]['count'] = chunk_count.copy()
                    results[var]['min'] = chunk_min.copy()
                    results[var]['max'] = chunk_max.copy()
                else:
                    # For sum and sum_sq, use nansum to combine (NaN + number = number)
                    # First replace NaN with 0 for addition
                    results[var]['sum'] = np.where(np.isnan(results[var]['sum']), 0, results[var]['sum'])
                    results[var]['sum'] += np.where(np.isnan(chunk_sum), 0, chunk_sum)
                    
                    results[var]['sum_sq'] = np.where(np.isnan(results[var]['sum_sq']), 0, results[var]['sum_sq'])
                    results[var]['sum_sq'] += np.where(np.isnan(chunk_sum_sq), 0, chunk_sum_sq)
                    
                    results[var]['count'] += chunk_count
                    
                    # For min/max, use fmin/fmax which handle NaN properly
                    results[var]['min'] = np.fmin(results[var]['min'], chunk_min)
                    results[var]['max'] = np.fmax(results[var]['max'], chunk_max)
                
                results[var]['years'].extend(years)
                
                # Clear array from memory
                del var_array
                gc.collect()
            
            # Close datasets to free memory
            for ds in datasets:
                ds.close()
            
            del datasets
            gc.collect()
            
        except Exception as e:
            print(f"      Error processing chunk: {e}")
            continue
    
    # Calculate final statistics
    final_results = {}
    
    for var in variables:
        if results[var]['sum'] is None:
            continue
        
        # Calculate mean
        with np.errstate(divide='ignore', invalid='ignore'):
            mean = results[var]['sum'] / results[var]['count']
            mean = np.where(results[var]['count'] > 0, mean, np.nan)
        
        # Calculate standard deviation
        with np.errstate(divide='ignore', invalid='ignore'):
            variance = (results[var]['sum_sq'] / results[var]['count']) - mean**2
            variance = np.where(variance < 0, 0, variance)  # Handle numerical errors
            std = np.sqrt(variance)
            std = np.where(results[var]['count'] > 0, std, np.nan)
        
        final_results[var] = {
            'mean': mean,
            'std': std,
            'min': results[var]['min'],
            'max': results[var]['max'],
            'sum': results[var]['sum'],  # Add raw sum
            'year_count': results[var]['count'],  # Rename to year_count
            'years': results[var]['years']
        }
        
        # Print summary
        valid_pixels = np.sum(results[var]['count'] > 0)
        total_pixels = mean.size
        coverage = 100 * valid_pixels / total_pixels
        
        print(f"      {var}: mean={np.nanmean(mean):.2f}, "
              f"std={np.nanmean(std):.2f}, "
              f"coverage={coverage:.1f}%")
    
    return final_results


def save_monthly_climatology_optimized(
    results: Dict[str, Dict],
    month: int,
    year_range: Tuple[int, int],
    output_dir: str,
    lat_lon_source: str,
    compress: bool = True
) -> Dict[str, str]:
    """
    Save monthly climatology to NetCDF files with proper coordinates.
    
    Output variables for each input variable:
        - {var}_mean: Climatological mean across years
        - {var}_std: Interannual standard deviation
        - {var}_min: Minimum value across years
        - {var}_max: Maximum value across years
        - {var}_sum: Total sum across all years
        - {var}_year_count: Number of years with valid data
    
    Args:
        results: Dictionary of statistics for each variable
        month: Month number (1-12)
        year_range: Tuple of (start_year, end_year)
        output_dir: Output directory path
        lat_lon_source: Path to a source file to get lat/lon coordinates
        compress: Whether to compress the output files
    
    Returns:
        Dictionary mapping variable names to output file paths
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # Get lat/lon coordinates from a source file
    with xr.open_dataset(lat_lon_source) as ds_source:
        lat = ds_source.lat.values
        lon = ds_source.lon.values
    
    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                   'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    month_name = month_names[month - 1]
    
    output_files = {}
    
    for var_name, stats in results.items():
        # Create output dataset
        ds_out = xr.Dataset()
        
        # Create DataArrays with proper coordinates
        coords = {'lat': lat, 'lon': lon}
        
        # Ensure all arrays are 2D (lat, lon) by squeezing out any extra dimensions
        mean_data = np.squeeze(stats['mean'])
        std_data = np.squeeze(stats['std'])
        min_data = np.squeeze(stats['min'])
        max_data = np.squeeze(stats['max'])
        count_data = np.squeeze(stats['year_count'])
        
        # Verify dimensions
        if mean_data.ndim != 2:
            print(f"      Warning: {var_name}_mean has {mean_data.ndim} dimensions, expected 2")
            print(f"      Shape: {mean_data.shape}, lat: {len(lat)}, lon: {len(lon)}")
            # Try to reshape if possible
            if mean_data.size == len(lat) * len(lon):
                mean_data = mean_data.reshape(len(lat), len(lon))
            else:
                raise ValueError(f"Cannot reshape {var_name}_mean to (lat, lon) dimensions")
        
        # Add the mean as the main variable
        mean_da = xr.DataArray(
            mean_data,
            coords=coords,
            dims=['lat', 'lon']
        )
        mean_da.attrs['long_name'] = f'Mean {var_name} across years'
        mean_da.attrs['description'] = f'Climatological mean of {var_name} for month {month}'
        ds_out[f'{var_name}_mean'] = mean_da
        
        # Add statistics as separate variables
        std_da = xr.DataArray(
            std_data,
            coords=coords,
            dims=['lat', 'lon']
        )
        std_da.attrs['long_name'] = f'Standard deviation of {var_name}'
        std_da.attrs['description'] = f'Interannual standard deviation of {var_name} for month {month}'
        ds_out[f'{var_name}_std'] = std_da
        
        min_da = xr.DataArray(
            min_data,
            coords=coords,
            dims=['lat', 'lon']
        )
        min_da.attrs['long_name'] = f'Minimum {var_name} across years'
        min_da.attrs['description'] = f'Minimum value of {var_name} for month {month} across all years'
        ds_out[f'{var_name}_min'] = min_da
        
        max_da = xr.DataArray(
            max_data,
            coords=coords,
            dims=['lat', 'lon']
        )
        max_da.attrs['long_name'] = f'Maximum {var_name} across years'
        max_da.attrs['description'] = f'Maximum value of {var_name} for month {month} across all years'
        ds_out[f'{var_name}_max'] = max_da
        
        # Add sum and year_count
        if 'sum' in stats:
            sum_data = np.squeeze(stats['sum'])
            if sum_data.ndim != 2:
                if sum_data.size == len(lat) * len(lon):
                    sum_data = sum_data.reshape(len(lat), len(lon))
            sum_da = xr.DataArray(
                sum_data,
                coords=coords,
                dims=['lat', 'lon']
            )
            sum_da.attrs['long_name'] = f'Sum of {var_name} across years'
            sum_da.attrs['description'] = f'Total sum of {var_name} for month {month} across all years'
            sum_da.attrs['note'] = 'This is the raw sum, not the mean. Divide by year_count to get mean.'
            ds_out[f'{var_name}_sum'] = sum_da
        
        # Rename count to year_count for clarity
        year_count_da = xr.DataArray(
            count_data,
            coords=coords,
            dims=['lat', 'lon']
        )
        year_count_da.attrs['long_name'] = f'Number of years with valid {var_name} data'
        year_count_da.attrs['description'] = f'Count of years with valid (non-NaN) {var_name} values for month {month}'
        year_count_da.attrs['units'] = 'count'
        ds_out[f'{var_name}_year_count'] = year_count_da
        
        # Add metadata
        ds_out.attrs['title'] = f'Monthly Climatology for {var_name} - {month_name}'
        ds_out.attrs['month'] = month
        ds_out.attrs['month_name'] = month_name
        ds_out.attrs['year_range'] = f'{year_range[0]}-{year_range[1]}'
        ds_out.attrs['created'] = pd.Timestamp.now().isoformat()
        ds_out.attrs['description'] = (f'Climatological statistics for {var_name} '
                                       f'calculated from {year_range[0]} to {year_range[1]}. '
                                       f'Includes mean, std, min, max, sum, and year_count.')
        ds_out.attrs['years_included'] = str(stats['years'])
        ds_out.attrs['n_years'] = len(stats['years'])
        
        # Define output filename
        filename = f'{var_name}_climatology_month{month:02d}_{year_range[0]}-{year_range[1]}.nc'
        output_path = os.path.join(output_dir, filename)
        
        # Save with compression if requested
        if compress:
            encoding = {var: {'zlib': True, 'complevel': 4} for var in ds_out.data_vars}
            ds_out.to_netcdf(output_path, encoding=encoding)
        else:
            ds_out.to_netcdf(output_path)
        
        output_files[var_name] = output_path
        print(f"      Saved: {output_path}")
        
        # Clean up
        ds_out.close()
        del ds_out
        gc.collect()
    
    return output_files


def process_single_month_optimized(
    data_dir: str,
    month: int,
    output_dir: str,
    variables: Optional[List[str]] = None,
    pattern: str = "agroclim_indicator-*.nc",
    chunk_years: int = 5
) -> Dict[str, str]:
    """
    Complete processing pipeline for a single month with memory optimization.
    
    Args:
        data_dir: Directory containing the monthly indicator files
        month: Month number (1-12)
        output_dir: Output directory for climatology files
        variables: Optional list of variables to process
        pattern: File pattern to match
        chunk_years: Number of years to process at once (reduce if memory errors)
    
    Returns:
        Dictionary mapping variable names to output file paths
    """
    month_names = ['January', 'February', 'March', 'April', 'May', 'June',
                   'July', 'August', 'September', 'October', 'November', 'December']
    
    print(f"\nProcessing {month_names[month-1]} (month {month:02d})...")
    
    # Default variables if not specified
    if variables is None:
        variables = ['gdd', 'hsd', 'frost_days']
    
    # Find files for this month
    print(f"  Finding files for month {month:02d}...")
    month_files = find_files_for_month(data_dir, month, pattern)
    
    if not month_files:
        print(f"  WARNING: No files found for month {month:02d}")
        return {}
    
    print(f"  Found {len(month_files)} files")
    
    # Get year range
    years = []
    for file in month_files:
        basename = os.path.basename(file)
        year_month = basename.split('-')[1].split('.')[0]
        year = int(year_month[:4])
        years.append(year)
    
    year_range = (min(years), max(years))
    print(f"  Year range: {year_range[0]}-{year_range[1]}")
    
    # Compute climatological statistics using chunked processing
    print(f"  Computing climatological statistics (processing {chunk_years} years at a time)...")
    results = compute_monthly_mean_chunked(month_files, variables, chunk_years)
    
    if not results:
        print(f"  ERROR: No valid data computed for month {month:02d}")
        return {}
    
    # Save results
    print(f"  Saving results...")
    output_files = save_monthly_climatology_optimized(
        results, month, year_range, output_dir, 
        lat_lon_source=month_files[0],  # Use first file for coordinates
        compress=True
    )
    
    # Force garbage collection
    gc.collect()
    
    print(f"  Completed {month_names[month-1]}")
    
    return output_files


def process_all_months_optimized(
    data_dir: str,
    output_dir: str,
    variables: Optional[List[str]] = None,
    months: Optional[List[int]] = None,
    pattern: str = "agroclim_indicator-*.nc",
    chunk_years: int = 5
) -> Dict[int, Dict[str, str]]:
    """
    Process climatology for all or specified months with memory optimization.
    
    Args:
        data_dir: Directory containing the monthly indicator files
        output_dir: Output directory for climatology files
        variables: Optional list of variables to process
        months: Optional list of months to process (default: all 12 months)
        pattern: File pattern to match
        chunk_years: Number of years to process at once (reduce if memory errors)
    
    Returns:
        Nested dictionary: {month: {variable: output_file_path}}
    """
    if months is None:
        months = list(range(1, 13))
    
    results = {}
    
    print(f"Processing {len(months)} months...")
    print(f"Input directory: {data_dir}")
    print(f"Output directory: {output_dir}")
    print(f"Chunk size: {chunk_years} years")
    
    for month in months:
        try:
            # Force garbage collection before each month
            gc.collect()
            
            output_files = process_single_month_optimized(
                data_dir, month, output_dir, variables, pattern, chunk_years
            )
            results[month] = output_files
            
        except Exception as e:
            print(f"  ERROR processing month {month:02d}: {e}")
            results[month] = {}
            
            # Try to recover by forcing garbage collection
            gc.collect()
    
    # Summary
    successful_months = sum(1 for m in results.values() if m)
    print(f"\n{'='*60}")
    print(f"Processing complete!")
    print(f"Successfully processed: {successful_months}/{len(months)} months")
    
    if successful_months > 0:
        # Get list of all output files
        all_files = []
        for month_files in results.values():
            all_files.extend(month_files.values())
        
        print(f"Total files created: {len(all_files)}")
        print(f"Output directory: {output_dir}")
    
    return results