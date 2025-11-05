# Water Mask Processing Pipeline Documentation

## Overview
This document details the complete water mask processing pipeline implemented in `process_watermask_complete.py`. The pipeline converts GPW v4 (Gridded Population of the World) water mask data from multiple ASCII grid tiles into a single NetCDF file, then remaps it to match the Agroclim indicator grid.

## Table of Contents
1. [Input Data Structure](#input-data-structure)
2. [Processing Pipeline](#processing-pipeline)
3. [Technical Implementation Details](#technical-implementation-details)
4. [Output Specifications](#output-specifications)
5. [Data Integrity Considerations](#data-integrity-considerations)

---

## Input Data Structure

### Source Files
- **Format**: ESRI ASCII Grid (.asc)
- **Number of tiles**: 8 files covering the globe
- **Naming convention**: `gpw_v4_data_quality_indicators_rev11_watermask_30_sec_[1-8].asc`
- **Resolution**: 30 arc-seconds (approximately 1km at equator)
- **Dimensions per tile**: 10800 × 10800 pixels

### Tile Geographic Coverage
```
┌─────────────┬─────────────┬─────────────┬─────────────┐
│   Tile 1    │   Tile 2    │   Tile 3    │   Tile 4    │  90°N
│ -180° to    │  -90° to    │   0° to     │  90° to     │
│  -90°       │   0°        │  90°        │  180°       │
├─────────────┼─────────────┼─────────────┼─────────────┤  0°
│   Tile 5    │   Tile 6    │   Tile 7    │   Tile 8    │
│ -180° to    │  -90° to    │   0° to     │  90° to     │
│  -90°       │   0°        │  90°        │  180°       │
└─────────────┴─────────────┴─────────────┴─────────────┘ -90°N
```

### Categorical Values
| Value | Category | Description |
|-------|----------|-------------|
| 0 | Total Water | Pixels completely covered by water |
| 1 | Partial Water | Pixels partially covered by water |
| 2 | Total Land | Pixels completely on land |
| 3 | Ocean | Ocean pixels |
| -9999 | NoData | Missing or invalid data |

---

## Processing Pipeline

### Step 1: ASCII to NetCDF Mosaic Creation

#### 1.1 Header Reading (`read_asc_header`)
- **Purpose**: Extract metadata from ASCII grid headers
- **Process**:
  1. Read first 6 lines of each .asc file
  2. Parse key-value pairs (ncols, nrows, xllcorner, yllcorner, cellsize, NODATA_value)
  3. Convert to appropriate data types (int/float)

#### 1.2 Data Loading (`read_asc_data`)
- **Purpose**: Load raster data from ASCII files
- **Process**:
  1. Skip 6 header lines
  2. Load numeric grid using NumPy's `loadtxt`
  3. Return both data array and header metadata

#### 1.3 Global Mosaic Assembly (`convert_watermask_mosaic_to_netcdf`)
- **Purpose**: Combine 8 tiles into single global dataset
- **Process**:
  1. Initialize global array (43200 × 21600 pixels)
  2. For each tile (1-8):
     - Read tile data
     - Calculate position in global array based on tile arrangement
     - Insert tile data at correct position
  3. Handle coordinate system:
     - Create longitude coordinates: -180° to 180° (ascending)
     - Create latitude coordinates: -90° to 90° (ascending)
     - **Critical**: Flip data vertically (`np.flipud`) to match ascending latitude convention

#### 1.4 NetCDF Creation
- **Variable Structure**:
  ```python
  Dataset:
    Dimensions: lat(21600) × lon(43200)
    Variables:
      - land_water_mask: int16, categorical water mask data
      - crs: coordinate reference system metadata
    Coordinates:
      - lat: latitude in degrees_north
      - lon: longitude in degrees_east
  ```

- **Attributes Added**:
  - CF-1.8 conventions compliance
  - Categorical value meanings
  - NoData value (-9999)
  - Grid mapping information
  - WGS84 spatial reference

- **Compression**: zlib level 9 for efficient storage

---

### Step 2: Grid Definition Extraction

#### 2.1 CDO Grid Description (`extract_grid_definition`)
- **Purpose**: Extract target grid specifications from reference file
- **Command**: `cdo griddes agroclim_indicator-202312.nc > agroclim_grid.txt`
- **Output Format**:
  ```
  gridtype  = lonlat
  gridsize  = 76050000
  xsize     = 11700
  ysize     = 6500
  xfirst    = -168.995
  xinc      = 0.01
  yfirst    = 7.005
  yinc      = 0.009999999
  ```

---

### Step 3: Grid Remapping

#### 3.1 Nearest Neighbor Remapping (`remap_to_reference_grid`)
- **Purpose**: Resample data to match Agroclim grid
- **Method**: Nearest neighbor (critical for categorical data)
- **Command**: `cdo remapnn,agroclim_grid.txt input.nc output.nc`
- **Why Nearest Neighbor**:
  1. Preserves exact categorical values (0, 1, 2, 3)
  2. No interpolation artifacts
  3. Maintains data integrity for discrete classifications

#### 3.2 Transformation Details
- **From**: 43200 × 21600 global grid (30 arc-second)
- **To**: 11700 × 6500 regional grid (0.01 degree)
- **Coverage**: North America (-169° to -52°E, 7° to 72°N)

---

### Step 4: Verification

#### 4.1 Dimension Checking (`verify_remapped_file`)
- Verify output dimensions match reference (11700 × 6500)
- Confirm coordinate arrays are identical using `np.allclose`

#### 4.2 Data Integrity Validation
- Check all categorical values preserved (0, 1, 2, 3)
- Calculate value distribution statistics
- Ensure no interpolation artifacts

---

## Technical Implementation Details

### Coordinate System Handling

#### Latitude Ordering Convention
- **ASC files**: Store data from north to south (descending)
- **NetCDF convention**: Use south to north (ascending)
- **Solution**: Apply `np.flipud()` to reverse row order

#### Dimension Ordering
- **Standard**: (lat, lon) for climate data
- **Implementation**: Consistent ordering throughout pipeline

### Error Handling

1. **File Existence Checks**
   - Verify input directory exists
   - Check for reference file availability
   - Validate each tile file presence

2. **CDO Availability**
   - Test CDO installation before processing
   - Provide installation instructions if missing

3. **Process Validation**
   - Check subprocess return codes
   - Capture and display error messages
   - Verify each step before proceeding

### Memory Optimization

- **Chunked Processing**: Tiles processed sequentially, not all loaded at once
- **Data Type Selection**: int16 for categorical data (saves 50% vs float32)
- **Compression**: zlib level 9 reduces file size by ~70%

---

## Output Specifications

### Final NetCDF File Structure

```
Filename: gpw_v4_watermask_agroclim.nc
Dimensions:
  lon: 11700
  lat: 6500
Variables:
  land_water_mask(lat, lon): int16
    - long_name: "Water Mask Category"
    - units: "category"
    - _FillValue: -9999
    - flag_values: [0, 1, 2, 3]
    - flag_meanings: "total_water partial_water total_land ocean"
Coordinates:
  lon: -168.995 to -52.005 (0.01° spacing)
  lat: 7.005 to 71.995 (0.01° spacing)
Global Attributes:
  - Conventions: "CF-1.8"
  - title: "GPW v4 Water Mask - Agroclim Grid"
```

### Data Distribution (Typical North America)
| Category | Pixel Count | Percentage |
|----------|------------|------------|
| Total Water | ~905,000 | 1.2% |
| Partial Water | ~3,248,000 | 4.3% |
| Total Land | ~24,932,000 | 32.8% |
| Ocean | ~46,964,000 | 61.8% |

---

## Data Integrity Considerations

### Potential Issues and Mitigations

1. **Coordinate Misalignment**
   - Risk: Tiles placed in wrong positions
   - Mitigation: Explicit tile arrangement dictionary with verification

2. **Value Interpolation**
   - Risk: Categorical values averaged during remapping
   - Mitigation: Strict use of nearest neighbor method

3. **NoData Handling**
   - Risk: -9999 values interpreted as valid data
   - Mitigation: Explicit _FillValue and missing_value attributes

4. **Precision Loss**
   - Risk: Float conversion altering categorical values
   - Mitigation: Maintain int16 dtype throughout

### Quality Assurance Checks

1. **Pre-processing**:
   - Verify all 8 tiles present
   - Check tile dimensions consistency
   - Validate coordinate ranges

2. **Post-processing**:
   - Confirm only values 0-3 and -9999 present
   - Check spatial extent matches reference
   - Verify no data gaps at tile boundaries

3. **Statistical Validation**:
   - Compare pixel count ratios with expected distributions
   - Check for anomalous value clusters
   - Validate against known geographic features

---

## Usage Examples

### Basic Pipeline Execution
```bash
python process_watermask_complete.py
```

### Custom Configuration
```python
# Modify these values in main() function:
input_directory = "custom_tiles/"
reference_file = "different_grid.nc"
final_output = "custom_watermask.nc"
```

### Intermediate File Retention
```python
# Comment out these lines to keep intermediate files:
# os.remove(global_output)
# os.remove(grid_definition)
```

---

## Troubleshooting

### Common Issues

1. **CDO Not Found**
   - Solution: `conda install -c conda-forge cdo`

2. **Memory Error with Large Grids**
   - Solution: Process tiles in smaller batches
   - Alternative: Use dask for lazy loading

3. **Coordinate Mismatch**
   - Check latitude ordering (ascending vs descending)
   - Verify dimension order (lat,lon vs lon,lat)

4. **Missing Tiles**
   - Script continues with available tiles
   - Check console warnings for skipped files

---

## Performance Metrics

- **Processing Time**: ~30-60 seconds for complete pipeline
- **Memory Usage**: ~3-4 GB peak for global mosaic
- **Disk Space**:
  - Input tiles: ~1.5 GB total
  - Global NetCDF: ~500 MB (compressed)
  - Final output: ~150 MB (compressed)

---

## References

- GPW v4 Documentation: https://sedac.ciesin.columbia.edu/data/collection/gpw-v4
- CF Conventions: http://cfconventions.org/
- CDO Documentation: https://code.mpimet.mpg.de/projects/cdo/
- NetCDF Best Practices: https://www.unidata.ucar.edu/software/netcdf/docs/BestPractices.html