"""


Description = Extracts extents for all fruits in one layer from annual CONUS Cropland Data Layer (CDL) GeoTIFFs. " 
                  "This script processes downloaded 30-meter resolution CDL files to create crop-specific maps.
date = 2025-07-17
author = Chinmay Deval & Siddharth Chaudhary
"""
import rasterio
import numpy as np
import os

# -----------------------

def combine_and_extract_fruits_for_year(year, base_cdl_dir, fruit_crops, output_combined_dir):
    """
    Combines and extracts all specified fruit categories into a single map for a given year.

    Args:
        year (int): The year of the CDL to process.
        base_cdl_dir (str): Base directory where the annual CONUS CDL GeoTIFFs are stored.
        fruit_crops (list): A list of dictionaries, each containing 'name' and 'code' for a fruit.
        output_combined_dir (str): Directory to save the combined fruit maps.
    """
    input_cdl_file = os.path.join(base_cdl_dir, str(year), f"CDL_{year}_30m.tif")
    output_combined_file = os.path.join(output_combined_dir, f"combined_fruits_cdl_{year}.tif")

    if not os.path.exists(input_cdl_file):
        print(f"Error: Input CDL file not found for year {year} at '{input_cdl_file}'. Skipping this year.")
        return

    print(f"\n--- Processing combined fruits for Year: {year} ---")
    print(f"Reading from: {input_cdl_file}")

    try:
        with rasterio.open(input_cdl_file) as src:
            cdl_data = src.read(1)
            combined_fruit_data = np.zeros_like(cdl_data, dtype=src.profile['dtype'])

            processed_fruit_count = 0
            for crop_info in fruit_crops:
                crop_name = crop_info["name"]
                crop_code = crop_info["code"]

                # Add pixels of the current fruit to the combined array
                # Pixels matching a fruit code will be set to that code.
                # If you want a simple binary (fruit/non-fruit) map where all fruit pixels
                # have the same value (e.g., 1), change `crop_code` to `1` below.
                combined_fruit_data[cdl_data == crop_code] = crop_code
                processed_fruit_count += 1
                print(f"  Added '{crop_name}' (Code: {crop_code}) to combined map.")

            if processed_fruit_count == 0:
                print(f"  No fruit types defined or processed for year {year}. Skipping output.")
                return

            profile = src.profile
            profile.update(
                dtype=combined_fruit_data.dtype,
                count=1,
                nodata=0 # 0 will represent non-fruit areas
            )

            with rasterio.open(output_combined_file, 'w', **profile) as dst:
                dst.write(combined_fruit_data, 1)

        print(f"Successfully created combined fruit map for Year {year} at: '{output_combined_file}'")

    except rasterio.errors.RasterioIOError as e:
        print(f"Rasterio error processing file {input_cdl_file} for combined fruits: {e}")
    except Exception as e:
        print(f"An unexpected error occurred for year {year} during combined fruit processing: {e}")


if __name__ == "__main__":
    # --- Configuration ---
    START_YEAR = 2008
    END_YEAR = 2024 

    BASE_CDL_DIR = "./data/CDL/all_conus_cdl_data_parallel" # Path to your downloaded CDL data

    # Define a list of dictionaries for all fruit crops to combine.
    # Following list includes botanical fruits
    # often treated as vegetables.
    FRUIT_CROPS = [
        {"name": "Sweet Corn", "code": 12},
        {"name": "Watermelons", "code": 48},
        {"name": "Cucumbers", "code": 50},
        {"name": "Tomatoes", "code": 54},
        {"name": "Caneberries", "code": 55},
        {"name": "Cherries", "code": 66},
        {"name": "Peaches", "code": 67},
        {"name": "Apples", "code": 68},
        {"name": "Grapes", "code": 69},
        {"name": "Other Tree Crops", "code": 71}, # General category, may include some fruits
        {"name": "Citrus", "code": 72},
        {"name": "Pecans", "code": 74},
        {"name": "Almonds", "code": 75},
        {"name": "Walnuts", "code": 76},
        {"name": "Pears", "code": 77},
        {"name": "Cantaloupes", "code": 209},
        {"name": "Prunes", "code": 210},
        {"name": "Olives", "code": 211},
        {"name": "Oranges", "code": 212}, # Can overlap with Citrus (72) depending on CDL year/detail
        {"name": "Honeydew Melons", "code": 213},
        {"name": "Avocados", "code": 215},
        {"name": "Pomegranates", "code": 217},
        {"name": "Nectarines", "code": 218},
        {"name": "Plums", "code": 220},
        {"name": "Strawberries", "code": 221},
        {"name": "Squash", "code": 222},
        {"name": "Apricots", "code": 223},
        {"name": "Blueberries", "code": 242},
        {"name": "Eggplants", "code": 248},
        {"name": "Gourds", "code": 249},
        {"name": "Cranberries", "code": 250},
    ]

    # Output directory for the combined fruit layers
    OUTPUT_COMBINED_FRUIT_DIR = os.path.join(BASE_CDL_DIR,"extracted_cdl_crops", "all_combined_fruits")
    os.makedirs(OUTPUT_COMBINED_FRUIT_DIR, exist_ok=True)

    # --- Main Extraction Loop ---
    print(f"\nStarting extraction of combined fruit maps for years {START_YEAR}-{END_YEAR}...")
    print(f"Input CDL data from: {BASE_CDL_DIR}")
    print(f"Combined output will be saved to: {OUTPUT_COMBINED_FRUIT_DIR}")

    for year in range(START_YEAR, END_YEAR + 1):
        combine_and_extract_fruits_for_year(year, BASE_CDL_DIR, FRUIT_CROPS, OUTPUT_COMBINED_FRUIT_DIR)

    print("\n--- All requested combined fruit extractions attempted. ---")
    print(f"Combined fruit maps are located in: {OUTPUT_COMBINED_FRUIT_DIR}")