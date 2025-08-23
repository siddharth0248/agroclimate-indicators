# GPW Land Water Mask Processing Pipeline

A comprehensive pipeline for processing GPW v4 (Gridded Population of the World) water mask data from ESRI ASCII grid tiles into NetCDF format and remapping to match Agroclim grid specifications.

## Project Structure

```
gpw-land-water-mask/
├── data/
│   ├── source/          # Original ASC tiles and reference files
│   └── intermediate/    # Intermediate processing files
├── outputs/             # Final output NetCDF files
├── scripts/             # Processing scripts
├── tests/               # Data integrity test scripts
└── docs/                # Documentation
```

## Requirements

- Python 3.x with packages:
  - numpy
  - xarray
  - pathlib
- CDO (Climate Data Operators)
  ```bash
  conda install -c conda-forge cdo
  ```

## Usage

### 1. Process Water Mask Data

Run the complete processing pipeline:

```bash
cd gpw-land-water-mask
python scripts/process_watermask_complete.py
```

This will:
1. Create a global mosaic from 8 ASC tiles (43200×21600 pixels)
2. Convert to NetCDF format with proper metadata
3. Extract grid definition from reference file
4. Remap to Agroclim grid (11700×6500 pixels, North America)

### 2. Test Data Integrity

Verify processing results:

```bash
python tests/test_watermask_data_integrity.py
```

This runs 10 comprehensive tests:
- Source tile completeness
- Dimension consistency
- Global coverage verification
- Categorical value integrity
- Value distribution analysis
- Spatial coherence checking
- Coordinate alignment
- Tile boundary analysis
- Metadata preservation
- CDO availability

## Input Data

### Source Tiles
- 8 ASCII grid files covering the globe in a 4×2 arrangement
- Resolution: 30 arc-seconds (approximately 1km at equator)
- Each tile: 10800×10800 pixels

### Categorical Values
| Value | Category | Description |
|-------|----------|-------------|
| 0 | Total Water | Pixels completely covered by water |
| 1 | Partial Water | Pixels partially covered by water |
| 2 | Total Land | Pixels completely on land |
| 3 | Ocean | Ocean pixels |
| -9999 | NoData | Missing or invalid data |

## Output Files

### Global Mosaic
- **File**: `data/intermediate/gpw_v4_LandWaterMask_global.nc`
- **Dimensions**: 43200×21600 (lon×lat)
- **Coverage**: Global (-180° to 180°E, -90° to 90°N)

### Remapped to Agroclim Grid
- **File**: `outputs/gpw_v4_LandWaterMask_agroclim.nc`
- **Dimensions**: 11700×6500 (lon×lat)
- **Coverage**: North America (-169° to -52°E, 7° to 72°N)
- **Resolution**: 0.01 degrees

## Documentation

See `docs/WATERMASK_PROCESSING_DOCUMENTATION.md` for detailed technical documentation including:
- Processing pipeline details
- Coordinate system handling
- Memory optimization strategies
- Data integrity considerations
- Troubleshooting guide

## Performance

- Processing time: ~30-60 seconds for complete pipeline
- Memory usage: ~3-4 GB peak
- Output file sizes:
  - Global NetCDF: ~500 MB (compressed)
  - Agroclim NetCDF: ~150 MB (compressed)

## License

GPW v4 data from SEDAC (Socioeconomic Data and Applications Center)