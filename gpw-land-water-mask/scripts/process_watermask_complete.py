#!/usr/bin/env python3
"""
Complete water mask processing pipeline:
1. Convert multiple water mask ASC tiles to a single global NetCDF
2. Remap to match agroclim grid using CDO
"""

import numpy as np
import xarray as xr
import os
import subprocess
import sys
from pathlib import Path

def read_asc_header(filename):
    """Read the header from an ASC file."""
    header = {}
    with open(filename, 'r') as f:
        for i in range(6):
            line = f.readline().strip()
            if line:
                parts = line.split()
                if len(parts) >= 2:
                    key = parts[0].lower()
                    value = parts[1]
                    try:
                        header[key] = float(value) if '.' in value or 'e' in value.lower() else int(value)
                    except:
                        header[key] = value
    return header

def read_asc_data(filename):
    """Read data from an ASC file."""
    # Read header to get dimensions
    header = read_asc_header(filename)
    
    # Read the data (skip header lines)
    data = np.loadtxt(filename, skiprows=6)
    
    return data, header

def convert_watermask_mosaic_to_netcdf(input_dir, output_nc):
    """
    Convert water mask ASC tiles to a single global NetCDF.
    
    Water mask categories:
    0: Total Water Pixels
    1: Partial Water Pixels  
    2: Total Land Pixels
    3: Ocean Pixels
    -9999: NoData
    
    Tile arrangement (4x2 grid):
    Top row (0 to 90°N): tiles 1,2,3,4 from -180 to 180°E
    Bottom row (-90 to 0°N): tiles 5,6,7,8 from -180 to 180°E
    """
    
    print("=" * 60)
    print("STEP 1: Creating global mosaic from ASC tiles")
    print("=" * 60)
    
    # Define tile arrangement
    tile_arrangement = {
        1: {'row': 0, 'col': 0, 'xll': -180, 'yll': 0},
        2: {'row': 0, 'col': 1, 'xll': -90, 'yll': 0},
        3: {'row': 0, 'col': 2, 'xll': 0, 'yll': 0},
        4: {'row': 0, 'col': 3, 'xll': 90, 'yll': 0},
        5: {'row': 1, 'col': 0, 'xll': -180, 'yll': -90},
        6: {'row': 1, 'col': 1, 'xll': -90, 'yll': -90},
        7: {'row': 1, 'col': 2, 'xll': 0, 'yll': -90},
        8: {'row': 1, 'col': 3, 'xll': 90, 'yll': -90}
    }
    
    # Read first tile to get dimensions
    first_file = os.path.join(input_dir, 'gpw_v4_data_quality_indicators_rev11_watermask_30_sec_1.asc')
    if not os.path.exists(first_file):
        raise FileNotFoundError(f"First tile not found: {first_file}")
        
    first_data, first_header = read_asc_data(first_file)
    
    tile_ncols = first_header['ncols']
    tile_nrows = first_header['nrows']
    cellsize = first_header['cellsize']
    nodata_value = first_header.get('nodata_value', -9999)
    
    # Global dimensions (4 tiles wide, 2 tiles tall)
    global_ncols = tile_ncols * 4  # 43200
    global_nrows = tile_nrows * 2  # 21600
    
    # Create global array
    print(f"Creating global mosaic: {global_ncols} x {global_nrows}")
    global_data = np.full((global_nrows, global_ncols), nodata_value, dtype=np.int16)
    
    # Process each tile
    for tile_num in range(1, 9):
        filename = f'gpw_v4_data_quality_indicators_rev11_watermask_30_sec_{tile_num}.asc'
        filepath = os.path.join(input_dir, filename)
        
        if not os.path.exists(filepath):
            print(f"Warning: {filename} not found, skipping")
            continue
            
        print(f"Processing tile {tile_num}: {filename}")
        
        # Read tile data
        tile_data, tile_header = read_asc_data(filepath)
        
        # Get tile position in mosaic
        tile_info = tile_arrangement[tile_num]
        
        # Calculate position in global array
        if tile_info['row'] == 0:  # Top row
            row_start = 0
            row_end = tile_nrows
        else:  # Bottom row
            row_start = tile_nrows
            row_end = 2 * tile_nrows
            
        col_start = tile_info['col'] * tile_ncols
        col_end = (tile_info['col'] + 1) * tile_ncols
        
        # Insert tile data into global array
        global_data[row_start:row_end, col_start:col_end] = tile_data
    
    # Create coordinates for the global grid
    # Use ascending latitude order to match conventions
    lon_coords = np.arange(-180 + cellsize/2, 180, cellsize)
    lat_coords = np.arange(-90 + cellsize/2, 90, cellsize)
    
    # Create xarray DataArray
    # Flip the data vertically since we're using ascending latitude
    mask = xr.DataArray(
        np.flipud(global_data),
        coords={
            'lat': lat_coords,
            'lon': lon_coords,
        },
        dims=['lat', 'lon'],
        name='land_water_mask'
    )
    
    # Add attributes
    mask.attrs['long_name'] = 'Water Mask Category'
    mask.attrs['units'] = 'category'
    mask.attrs['_FillValue'] = nodata_value
    mask.attrs['missing_value'] = nodata_value
    mask.attrs['valid_range'] = [0, 3]
    mask.attrs['flag_values'] = [0, 1, 2, 3]
    mask.attrs['flag_meanings'] = 'total_water partial_water total_land ocean'
    mask.attrs['category_meanings'] = '0=Total Water Pixels, 1=Partial Water Pixels, 2=Total Land Pixels, 3=Ocean Pixels'
    mask.attrs['grid_mapping'] = 'crs'
    
    # Create dataset
    ds = xr.Dataset({'land_water_mask': mask})
    
    # Add coordinate attributes
    ds.coords['lon'].attrs = {
        'units': 'degrees_east',
        'long_name': 'Longitude',
        'standard_name': 'longitude',
        'axis': 'X'
    }
    
    ds.coords['lat'].attrs = {
        'units': 'degrees_north',
        'long_name': 'Latitude',
        'standard_name': 'latitude',
        'axis': 'Y'
    }
    
    # Add CRS information
    crs_var = xr.DataArray(
        0,
        name='crs',
        attrs={
            'grid_mapping_name': 'latitude_longitude',
            'longitude_of_prime_meridian': 0.0,
            'semi_major_axis': 6378137.0,
            'inverse_flattening': 298.257223563,
            'spatial_ref': 'GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563]],PRIMEM["Greenwich",0],UNIT["degree",0.0174532925199433]]'
        }
    )
    ds['crs'] = crs_var
    
    # Add global attributes
    ds.attrs['Conventions'] = 'CF-1.8'
    ds.attrs['title'] = 'GPW v4 Water Mask Data Quality Indicators - Global Mosaic'
    ds.attrs['source'] = 'Converted from 8 ASC tile files'
    ds.attrs['history'] = 'Mosaicked from geographic tiles and converted to NetCDF'
    ds.attrs['description'] = 'Global water mask with categorical values: 0=Total Water, 1=Partial Water, 2=Total Land, 3=Ocean'
    ds.attrs['nodata_value'] = nodata_value
    
    # Set encoding for compression
    encoding = {
        'land_water_mask': {
            'zlib': True,
            'complevel': 9,
            'dtype': 'int16'
        }
    }
    
    # Save to NetCDF
    ds.to_netcdf(output_nc, encoding=encoding, format='NETCDF4')
    
    print(f"\nSuccessfully created global mosaic: {output_nc}")
    print(f"Global dimensions: {global_ncols} x {global_nrows}")
    print(f"Coordinate range: Longitude [{lon_coords[0]:.2f}, {lon_coords[-1]:.2f}], Latitude [{lat_coords[0]:.2f}, {lat_coords[-1]:.2f}]")
    
    # Print statistics
    unique_values, counts = np.unique(global_data[global_data != nodata_value], return_counts=True)
    print("\nData statistics:")
    category_names = {0: 'Total Water', 1: 'Partial Water', 2: 'Total Land', 3: 'Ocean'}
    for val, count in zip(unique_values, counts):
        if val in category_names:
            print(f"  {category_names[val]} (value={val}): {count:,} pixels")
    
    return output_nc

def extract_grid_definition(reference_nc, grid_file):
    """Extract grid definition from reference NetCDF using CDO."""
    print("\n" + "=" * 60)
    print("STEP 2: Extracting grid definition from reference file")
    print("=" * 60)
    
    cmd = ['cdo', 'griddes', reference_nc]
    
    print(f"Running: {' '.join(cmd)} > {grid_file}")
    
    try:
        with open(grid_file, 'w') as f:
            result = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, text=True, check=True)
        
        # Print grid info
        with open(grid_file, 'r') as f:
            lines = f.readlines()[:20]
            print("\nGrid definition (first 20 lines):")
            print(''.join(lines))
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"Error extracting grid: {e}")
        if e.stderr:
            print(f"Error details: {e.stderr}")
        return False

def remap_to_reference_grid(input_nc, grid_file, output_nc):
    """Remap NetCDF to reference grid using CDO nearest neighbor."""
    print("\n" + "=" * 60)
    print("STEP 3: Remapping to reference grid using CDO")
    print("=" * 60)
    
    # Use nearest neighbor for categorical data
    cmd = ['cdo', f'remapnn,{grid_file}', input_nc, output_nc]
    
    print(f"Running: {' '.join(cmd)}")
    print("Using nearest neighbor remapping to preserve categorical values")
    
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=True)
        print(result.stdout)
        
        # Verify the output
        info_cmd = ['cdo', 'info', output_nc]
        info_result = subprocess.run(info_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        print("\nRemapped file info:")
        print(info_result.stdout.split('\n')[0])  # First line of info
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"Error remapping: {e}")
        if e.stdout:
            print(f"Error details: {e.stdout}")
        return False

def verify_remapped_file(original_ref, remapped_file):
    """Verify the remapped file matches the reference grid."""
    print("\n" + "=" * 60)
    print("STEP 4: Verifying remapped file")
    print("=" * 60)
    
    try:
        # Load both files
        ref_ds = xr.open_dataset(original_ref)
        remap_ds = xr.open_dataset(remapped_file)
        
        # Check dimensions
        print(f"Reference dimensions: {dict(ref_ds.dims)}")
        print(f"Remapped dimensions: {dict(remap_ds.dims)}")
        
        # Check if coordinates match
        lon_match = np.allclose(ref_ds.lon.values, remap_ds.lon.values)
        lat_match = np.allclose(ref_ds.lat.values, remap_ds.lat.values)
        
        print(f"\nCoordinate match:")
        print(f"  Longitude: {'✓' if lon_match else '✗'}")
        print(f"  Latitude: {'✓' if lat_match else '✗'}")
        
        # Check categorical values
        unique_values = np.unique(remap_ds.land_water_mask.values)
        print(f"\nUnique categorical values in remapped data: {unique_values.astype(int)}")
        
        # Value statistics
        print("\nValue distribution in remapped data:")
        unique, counts = np.unique(remap_ds.land_water_mask.values, return_counts=True)
        total_pixels = len(remap_ds.land_water_mask.values.flatten())
        
        category_names = {0: 'Total Water', 1: 'Partial Water', 2: 'Total Land', 3: 'Ocean'}
        for val, count in zip(unique.astype(int), counts):
            if val in category_names:
                pct = count/total_pixels*100
                print(f"  {category_names[val]}: {count:,} pixels ({pct:.1f}%)")
        
        ref_ds.close()
        remap_ds.close()
        
        return lon_match and lat_match
        
    except Exception as e:
        print(f"Error verifying file: {e}")
        return False

def main():
    """Main processing pipeline."""
    # Get script directory for relative paths
    script_dir = Path(__file__).parent
    base_dir = script_dir.parent
    
    # Create output directories if they don't exist
    (base_dir / "data" / "source").mkdir(parents=True, exist_ok=True)
    (base_dir / "data" / "intermediate").mkdir(parents=True, exist_ok=True)
    (base_dir / "outputs").mkdir(parents=True, exist_ok=True)
    
    # Configuration with proper paths
    input_directory = str(base_dir / "data" / "source")
    global_output = str(base_dir / "data" / "intermediate" / "gpw_v4_LandWaterMask_global.nc")
    reference_file = str(base_dir / "data" / "source" / "agroclim_indicator-202312.nc")
    grid_definition = str(base_dir / "data" / "intermediate" / "agroclim_grid.txt")
    final_output = str(base_dir / "outputs" / "gpw_v4_LandWaterMask_agroclim.nc")
    
    print("WATER MASK PROCESSING PIPELINE")
    print("=" * 60)
    print(f"Input directory: {input_directory}")
    print(f"Reference file: {reference_file}")
    print(f"Final output: {final_output}")
    
    # Check prerequisites
    if not os.path.exists(input_directory):
        print(f"Error: Input directory '{input_directory}' not found")
        sys.exit(1)
    
    if not os.path.exists(reference_file):
        print(f"Error: Reference file '{reference_file}' not found")
        sys.exit(1)
    
    # Check for CDO
    try:
        subprocess.run(['cdo', '--version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Error: CDO is not installed or not in PATH")
        print("Please install CDO: conda install -c conda-forge cdo")
        sys.exit(1)
    
    # Step 1: Create global mosaic
    try:
        global_nc = convert_watermask_mosaic_to_netcdf(input_directory, global_output)
    except Exception as e:
        print(f"Error creating mosaic: {e}")
        sys.exit(1)
    
    # Step 2: Extract grid definition
    if not extract_grid_definition(reference_file, grid_definition):
        print("Failed to extract grid definition")
        sys.exit(1)
    
    # Step 3: Remap to reference grid
    if not remap_to_reference_grid(global_output, grid_definition, final_output):
        print("Failed to remap to reference grid")
        sys.exit(1)
    
    # Step 4: Verify results
    if verify_remapped_file(reference_file, final_output):
        print("\n" + "=" * 60)
        print("SUCCESS: Processing complete!")
        print(f"Final output: {final_output}")
        print("The water mask has been successfully remapped to match the agroclim grid.")
        print("=" * 60)
    else:
        print("\nWarning: Verification detected issues. Please check the output manually.")
    
    # Clean up intermediate files if desired
    # os.remove(global_output)  # Uncomment to remove intermediate global file
    # os.remove(grid_definition)  # Uncomment to remove grid definition file

if __name__ == "__main__":
    main()