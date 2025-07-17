"""
Description: Downloads and unzips CONUS Cropland Data Layer (CDL) GeoTIFFs for specified years in parallel. 
This script fetches 30-meter resolution CDL data from the USDA NASS website.
Date: 2025-07-15
Author: Chinmay Deval & Siddharth Chaudhary

"""

import requests
import os
import zipfile
import io
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

def download_and_unzip_cdl(year, output_dir= None):
    """
    Downloads the zipped CONUS Cropland Data Layer (CDL) for a given year and unzips it.
    Returns the path to the unzipped TIF on success, None on failure.
    """
    download_url = f"https://www.nass.usda.gov/Research_and_Science/Cropland/Release/datasets/{year}_30m_cdls.zip"

    year_output_dir = os.path.join(output_dir, str(year))
    os.makedirs(year_output_dir, exist_ok=True)

    zip_output_path = os.path.join(year_output_dir, f"{year}_30m_cdls.zip")
    tif_output_path = os.path.join(year_output_dir, f"CDL_{year}_30m.tif")

    print(f"Attempting to process CDL for Year: {year}")

    try:
        # Check if the zipped file already exists
        if os.path.exists(zip_output_path):
            print(f"Year {year}: Zip file '{zip_output_path}' already exists. Skipping download.")
        else:
            print(f"Year {year}: Starting download from: {download_url}")
            with requests.get(download_url, stream=True, timeout=300) as r:
                r.raise_for_status() # Raise an HTTPError for bad responses
                total_size_in_bytes = int(r.headers.get('content-length', 0))
                block_size = 8192

                with open(zip_output_path, 'wb') as f:
                    downloaded_size = 0
                    for chunk in r.iter_content(chunk_size=block_size):
                        if chunk:
                            f.write(chunk)
                            downloaded_size += len(chunk)
            print(f"Year {year}: Download of {os.path.basename(zip_output_path)} complete.")

        # Check if the GeoTIFF file already exists
        if os.path.exists(tif_output_path):
            print(f"Year {year}: GeoTIFF file '{tif_output_path}' already exists. Skipping unzip.")
            return tif_output_path # Return path if already processed
        else:
            print(f"Year {year}: Unzipping {zip_output_path}...")
            with zipfile.ZipFile(zip_output_path, 'r') as zip_ref:
                tif_files = [f for f in zip_ref.namelist() if f.lower().endswith('.tif')]
                if tif_files:
                    for tif_file_in_zip in tif_files:
                        source = zip_ref.open(tif_file_in_zip)
                        target = open(tif_output_path, "wb")
                        with source, target:
                            import shutil
                            shutil.copyfileobj(source, target)
                        print(f"Year {year}: Extracted {tif_file_in_zip} to {tif_output_path}")
                        return tif_output_path # Return path on successful extraction
                else:
                    print(f"Year {year}: No .tif file found inside {zip_output_path}")
                    return None # Indicate failure
    except requests.exceptions.RequestException as e:
        print(f"Year {year}: Network error or invalid URL: {e}")
        return None
    except zipfile.BadZipFile:
        print(f"Year {year}: Error: Downloaded file '{zip_output_path}' is not a valid ZIP file. It might be corrupted or incomplete.")
        return None
    except Exception as e:
        print(f"Year {year}: An unexpected error occurred: {e}")
        return None

if __name__ == "__main__":
    # --- Configuration ---
    START_YEAR = 2008
    END_YEAR = 2024
    BASE_DOWNLOAD_DIR = "./data/CDL/all_conus_cdl_data_parallel"
    MAX_WORKERS = 5 

    os.makedirs(BASE_DOWNLOAD_DIR, exist_ok=True)

    print(f"\n--- Starting parallel CDL downloads for years {START_YEAR}-{END_YEAR} ---")
    print(f"Max concurrent downloads: {MAX_WORKERS}")

    downloaded_files = []
    failed_years = []

    # parallel downloads
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Submit download tasks for each year
        future_to_year = {executor.submit(download_and_unzip_cdl, year, BASE_DOWNLOAD_DIR): year
                          for year in range(START_YEAR, END_YEAR + 1)}

        for future in as_completed(future_to_year):
            year = future_to_year[future]
            try:
                result_path = future.result()
                if result_path:
                    downloaded_files.append(result_path)
                    print(f"Completion: Year {year} successfully processed.")
                else:
                    failed_years.append(year)
                    print(f"Completion: Year {year} failed to process.")
            except Exception as exc:
                failed_years.append(year)
                print(f"Year {year} generated an exception: {exc}")

    print("\n--- All parallel CDL downloads and unzips attempted. ---")
    print(f"Successfully processed {len(downloaded_files)} files.")
    print(f"Failed to process {len(failed_years)} years: {failed_years}")
    print(f"CDL files are located in subdirectories within: {BASE_DOWNLOAD_DIR}")