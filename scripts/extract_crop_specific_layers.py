"""


Description = Extracts specific crop (Apple) data from annual CONUS Cropland Data Layer (CDL) GeoTIFFs. " 
                  "This script processes downloaded 30-meter resolution CDL files to create crop-specific maps.
date = 2025-07-15
author = Chinmay Deval
"""


import rasterio
import numpy as np
import os

def extract_specific_crop_cdl(input_cdl_path, output_path, crop_code, crop_name=None):
    """
    Extracts a specific crop from a Cropland Data Layer (CDL) GeoTIFF.

    Args:
        input_cdl_path (str): Path to the input CONUS CDL GeoTIFF file for a given year.
        output_path (str): Path to save the output GeoTIFF file for the extracted crop.
        crop_code (int): The CDL numerical code for the desired crop (e.g., 68 for Apple).
        crop_name (str, optional): The name of the crop (for output filename/user info).
                                   Defaults to None. If None, uses "Crop with Code [crop_code]".
    """
    if not os.path.exists(input_cdl_path):
        print(f"Error: Input CDL file not found at '{input_cdl_path}'. Skipping this year.")
        return

    # Determine the name to use in print statements
    display_name = crop_name if crop_name is not None else f"Crop with Code {crop_code}"
    print(f"Processing '{display_name}' (Code: {crop_code}) from: {input_cdl_path}")

    try:
        with rasterio.open(input_cdl_path) as src:
            cdl_data = src.read(1)

            extracted_crop_data = np.zeros_like(cdl_data, dtype=src.profile['dtype'])
            extracted_crop_data[cdl_data == crop_code] = crop_code

            profile = src.profile
            profile.update(
                dtype=extracted_crop_data.dtype,
                count=1,
                nodata=0
            )

            with rasterio.open(output_path, 'w', **profile) as dst:
                dst.write(extracted_crop_data, 1)

        print(f"Successfully extracted '{display_name}' data for {os.path.basename(input_cdl_path)} to: '{output_path}'")

    except rasterio.errors.RasterioIOError as e:
        print(f"Rasterio error processing file {input_cdl_path}: {e}")
    except Exception as e:
        print(f"An unexpected error occurred for {input_cdl_path}: {e}")

if __name__ == "__main__":
    # --- Configuration ---
    START_YEAR = 2008
    END_YEAR = 2024

    BASE_CDL_DIR = "./data/CDL/all_conus_cdl_data_parallel"

    CROP_NAME = "Apple"
    CROP_CODE = 68

    OUTPUT_CROP_DIR = os.path.join(BASE_CDL_DIR,"extracted_cdl_crops", CROP_NAME.lower().replace(' ', '_'))
    os.makedirs(OUTPUT_CROP_DIR, exist_ok=True)

    print(f"\nStarting extraction of {CROP_NAME} CDL maps for years {START_YEAR}-{END_YEAR}...")
    print(f"Input CDL data from: {BASE_CDL_DIR}")
    print(f"Output will be saved to: {OUTPUT_CROP_DIR}")

    for year in range(START_YEAR, END_YEAR + 1):
        input_cdl_file = os.path.join(BASE_CDL_DIR, str(year), f"CDL_{year}_30m.tif")
        output_crop_file = os.path.join(OUTPUT_CROP_DIR, f"{CROP_NAME.lower().replace(' ', '_')}_cdl_{year}_{CROP_CODE}.tif")

        # Pass CROP_NAME, which is defined as "Apple" in this case
        extract_specific_crop_cdl(input_cdl_file, output_crop_file, CROP_CODE, CROP_NAME)

    print("\n--- All requested crop extractions attempted. ---")
    print(f"Extracted {CROP_NAME} maps are located in: {OUTPUT_CROP_DIR}")