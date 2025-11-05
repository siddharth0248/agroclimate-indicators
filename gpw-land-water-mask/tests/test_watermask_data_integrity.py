#!/usr/bin/env python3
"""
Test script for water mask processing pipeline data integrity.
Tests for data loss, value corruption, and spatial accuracy.
"""

import numpy as np
import xarray as xr
import os
import sys
from pathlib import Path
import subprocess
import json

# Get script directory for relative paths
script_dir = Path(__file__).parent
base_dir = script_dir.parent

class WaterMaskDataIntegrityTester:
    """Test suite for validating water mask processing pipeline."""
    
    def __init__(self):
        self.test_results = []
        self.errors = []
        self.warnings = []
        
    def add_result(self, test_name, passed, message="", data=None):
        """Record test result."""
        self.test_results.append({
            'test': test_name,
            'passed': passed,
            'message': message,
            'data': data
        })
        if not passed:
            self.errors.append(f"{test_name}: {message}")
    
    def add_warning(self, message):
        """Add a warning message."""
        self.warnings.append(message)
    
    def test_source_tiles_completeness(self, input_dir=None):
        if input_dir is None:
            input_dir = str(base_dir / "data" / "source")
        """Test 1: Verify all 8 source tiles are present and valid."""
        print("\n" + "="*60)
        print("TEST 1: Source Tiles Completeness")
        print("="*60)
        
        expected_tiles = 8
        found_tiles = []
        tile_sizes = []
        
        for tile_num in range(1, 9):
            filename = f'gpw_v4_data_quality_indicators_rev11_watermask_30_sec_{tile_num}.asc'
            filepath = os.path.join(input_dir, filename)
            
            if os.path.exists(filepath):
                found_tiles.append(tile_num)
                # Get file size
                size_mb = os.path.getsize(filepath) / (1024 * 1024)
                tile_sizes.append(size_mb)
                print(f"  ✓ Tile {tile_num}: Found ({size_mb:.1f} MB)")
            else:
                print(f"  ✗ Tile {tile_num}: Missing")
        
        # Check if all tiles found
        passed = len(found_tiles) == expected_tiles
        
        # Check if tile sizes are consistent (should be similar)
        if tile_sizes:
            size_variance = np.std(tile_sizes) / np.mean(tile_sizes)
            if size_variance > 0.1:  # More than 10% variance
                self.add_warning(f"Tile sizes vary significantly (CV={size_variance:.2%})")
        
        self.add_result(
            "source_tiles_completeness",
            passed,
            f"Found {len(found_tiles)}/{expected_tiles} tiles",
            {'found_tiles': found_tiles, 'sizes_mb': tile_sizes}
        )
        
        return passed
    
    def test_tile_dimensions(self, input_dir=None):
        if input_dir is None:
            input_dir = str(base_dir / "data" / "source")
        """Test 2: Verify all tiles have consistent dimensions."""
        print("\n" + "="*60)
        print("TEST 2: Tile Dimension Consistency")
        print("="*60)
        
        import subprocess
        dimensions = []
        
        for tile_num in range(1, 9):
            filename = f'gpw_v4_data_quality_indicators_rev11_watermask_30_sec_{tile_num}.asc'
            filepath = os.path.join(input_dir, filename)
            
            if os.path.exists(filepath):
                # Read header
                with open(filepath, 'r') as f:
                    header_lines = [f.readline().strip() for _ in range(6)]
                
                ncols = nrows = None
                for line in header_lines:
                    if line.startswith('ncols'):
                        ncols = int(line.split()[1])
                    elif line.startswith('nrows'):
                        nrows = int(line.split()[1])
                
                if ncols and nrows:
                    dimensions.append((ncols, nrows))
                    print(f"  Tile {tile_num}: {ncols} × {nrows}")
        
        # Check consistency
        passed = len(set(dimensions)) == 1 if dimensions else False
        
        if passed:
            expected_dims = (10800, 10800)
            actual_dims = dimensions[0] if dimensions else (0, 0)
            passed = actual_dims == expected_dims
            
            self.add_result(
                "tile_dimensions",
                passed,
                f"All tiles are {actual_dims[0]} × {actual_dims[1]} (expected {expected_dims[0]} × {expected_dims[1]})",
                {'dimensions': dimensions}
            )
        else:
            self.add_result(
                "tile_dimensions",
                False,
                "Inconsistent tile dimensions",
                {'dimensions': dimensions}
            )
        
        return passed
    
    def test_global_mosaic_coverage(self, global_nc=None):
        if global_nc is None:
            global_nc = str(base_dir / "data" / "intermediate" / "gpw_v4_LandWaterMask_global.nc")
        """Test 3: Verify global mosaic has complete coverage."""
        print("\n" + "="*60)
        print("TEST 3: Global Mosaic Coverage")
        print("="*60)
        
        if not os.path.exists(global_nc):
            self.add_result("global_mosaic_coverage", False, f"File not found: {global_nc}")
            return False
        
        try:
            ds = xr.open_dataset(global_nc)
            
            # Check dimensions
            expected_dims = {'lon': 43200, 'lat': 21600}
            actual_dims = dict(ds.dims)
            
            dims_match = all(
                actual_dims.get(k) == v for k, v in expected_dims.items()
            )
            
            print(f"  Expected dimensions: {expected_dims}")
            print(f"  Actual dimensions: {actual_dims}")
            
            # Check coordinate ranges
            lon_range = (ds.lon.min().values, ds.lon.max().values)
            lat_range = (ds.lat.min().values, ds.lat.max().values)
            
            print(f"  Longitude range: {lon_range[0]:.2f} to {lon_range[1]:.2f}")
            print(f"  Latitude range: {lat_range[0]:.2f} to {lat_range[1]:.2f}")
            
            # Check for complete global coverage
            lon_complete = np.isclose(lon_range[0], -180, atol=0.1) and np.isclose(lon_range[1], 180, atol=0.1)
            lat_complete = np.isclose(lat_range[0], -90, atol=0.1) and np.isclose(lat_range[1], 90, atol=0.1)
            
            passed = dims_match and lon_complete and lat_complete
            
            self.add_result(
                "global_mosaic_coverage",
                passed,
                "Global coverage complete" if passed else "Incomplete global coverage",
                {
                    'dimensions': actual_dims,
                    'lon_range': lon_range,
                    'lat_range': lat_range
                }
            )
            
            ds.close()
            return passed
            
        except Exception as e:
            self.add_result("global_mosaic_coverage", False, str(e))
            return False
    
    def test_categorical_value_integrity(self, global_nc=None, remapped_nc=None):
        if global_nc is None:
            global_nc = str(base_dir / "data" / "intermediate" / "gpw_v4_LandWaterMask_global.nc")
        if remapped_nc is None:
            remapped_nc = str(base_dir / "outputs" / "gpw_v4_LandWaterMask_agroclim.nc")
        """Test 4: Verify categorical values are preserved and valid."""
        print("\n" + "="*60)
        print("TEST 4: Categorical Value Integrity")
        print("="*60)
        
        valid_values = {0, 1, 2, 3, -9999}  # Including NoData
        results = {}
        
        for file_path, file_label in [(global_nc, "Global"), (remapped_nc, "Remapped")]:
            if not os.path.exists(file_path):
                print(f"  ⚠ {file_label} file not found: {file_path}")
                continue
            
            try:
                ds = xr.open_dataset(file_path)
                data = ds.land_water_mask.values
                
                # Get unique values
                unique_vals = np.unique(data)
                
                # Check for invalid values
                invalid_vals = set(unique_vals) - valid_values
                
                # Count each category
                value_counts = {}
                for val in [0, 1, 2, 3]:
                    count = np.sum(data == val)
                    value_counts[val] = count
                
                nodata_count = np.sum(data == -9999)
                
                print(f"\n  {file_label} File:")
                print(f"    Unique values: {sorted(unique_vals.astype(int))}")
                print(f"    Value distribution:")
                print(f"      Water (0): {value_counts.get(0, 0):,} pixels")
                print(f"      Partial (1): {value_counts.get(1, 0):,} pixels")
                print(f"      Land (2): {value_counts.get(2, 0):,} pixels")
                print(f"      Ocean (3): {value_counts.get(3, 0):,} pixels")
                print(f"      NoData (-9999): {nodata_count:,} pixels")
                
                if invalid_vals:
                    print(f"    ⚠ Invalid values found: {sorted(invalid_vals)}")
                
                results[file_label] = {
                    'valid': len(invalid_vals) == 0,
                    'unique_values': unique_vals.tolist(),
                    'value_counts': value_counts,
                    'invalid_values': list(invalid_vals)
                }
                
                ds.close()
                
            except Exception as e:
                print(f"  Error reading {file_label} file: {e}")
                results[file_label] = {'valid': False, 'error': str(e)}
        
        # Check if values are preserved between files
        passed = all(r.get('valid', False) for r in results.values())
        
        self.add_result(
            "categorical_value_integrity",
            passed,
            "All categorical values valid" if passed else "Invalid categorical values detected",
            results
        )
        
        return passed
    
    def test_value_distribution_consistency(self, global_nc=None, remapped_nc=None):
        if global_nc is None:
            global_nc = str(base_dir / "data" / "intermediate" / "gpw_v4_LandWaterMask_global.nc")
        if remapped_nc is None:
            remapped_nc = str(base_dir / "outputs" / "gpw_v4_LandWaterMask_agroclim.nc")
        """Test 5: Check if value distributions are reasonable after remapping."""
        print("\n" + "="*60)
        print("TEST 5: Value Distribution Consistency")
        print("="*60)
        
        if not os.path.exists(remapped_nc):
            self.add_result("value_distribution_consistency", False, f"Remapped file not found")
            return False
        
        try:
            # Load remapped data
            ds_remap = xr.open_dataset(remapped_nc)
            data_remap = ds_remap.land_water_mask.values
            
            # Calculate proportions
            total_valid = np.sum(data_remap != -9999)
            
            proportions = {}
            category_names = {0: 'Water', 1: 'Partial', 2: 'Land', 3: 'Ocean'}
            
            for val, name in category_names.items():
                count = np.sum(data_remap == val)
                prop = count / total_valid * 100 if total_valid > 0 else 0
                proportions[name] = prop
                print(f"  {name}: {prop:.2f}%")
            
            # Sanity checks for North America region
            # Ocean should be significant (coastal region)
            # Land should be substantial
            warnings = []
            
            if proportions['Ocean'] < 20:
                warnings.append("Ocean proportion unusually low for North America region")
            if proportions['Land'] < 10:
                warnings.append("Land proportion unusually low")
            if proportions['Water'] + proportions['Partial'] > 50:
                warnings.append("Water categories unusually high")
            
            for warning in warnings:
                self.add_warning(warning)
                print(f"  ⚠ {warning}")
            
            passed = len(warnings) == 0
            
            self.add_result(
                "value_distribution_consistency",
                passed,
                "Value distributions reasonable" if passed else "Unusual value distributions detected",
                {'proportions': proportions, 'warnings': warnings}
            )
            
            ds_remap.close()
            return passed
            
        except Exception as e:
            self.add_result("value_distribution_consistency", False, str(e))
            return False
    
    def test_spatial_coherence(self, remapped_nc=None):
        if remapped_nc is None:
            remapped_nc = str(base_dir / "outputs" / "gpw_v4_LandWaterMask_agroclim.nc")
        """Test 6: Check for spatial coherence (no scattered pixels)."""
        print("\n" + "="*60)
        print("TEST 6: Spatial Coherence")
        print("="*60)
        
        if not os.path.exists(remapped_nc):
            self.add_result("spatial_coherence", False, f"Remapped file not found")
            return False
        
        try:
            ds = xr.open_dataset(remapped_nc)
            data = ds.land_water_mask.values
            
            # Sample a subset for analysis (full analysis would be too slow)
            # Check center region
            h, w = data.shape
            sample = data[h//2-500:h//2+500, w//2-500:w//2+500]
            
            # Count isolated pixels (pixels different from all neighbors)
            isolated_count = 0
            
            for i in range(1, sample.shape[0]-1):
                for j in range(1, sample.shape[1]-1):
                    if sample[i,j] == -9999:
                        continue
                    
                    center = sample[i,j]
                    neighbors = [
                        sample[i-1,j], sample[i+1,j],
                        sample[i,j-1], sample[i,j+1]
                    ]
                    
                    # Filter out NoData neighbors
                    valid_neighbors = [n for n in neighbors if n != -9999]
                    
                    if valid_neighbors and all(n != center for n in valid_neighbors):
                        isolated_count += 1
            
            isolation_rate = isolated_count / (sample.size) * 100
            
            print(f"  Sample region: 1000×1000 pixels from center")
            print(f"  Isolated pixels: {isolated_count}")
            print(f"  Isolation rate: {isolation_rate:.3f}%")
            
            # Threshold for concern (more than 5% isolated pixels might indicate issues)
            passed = isolation_rate < 5.0
            
            if not passed:
                self.add_warning(f"High isolation rate ({isolation_rate:.1f}%) may indicate remapping artifacts")
            
            self.add_result(
                "spatial_coherence",
                passed,
                f"Isolation rate: {isolation_rate:.3f}%" ,
                {'isolated_pixels': isolated_count, 'isolation_rate': isolation_rate}
            )
            
            ds.close()
            return passed
            
        except Exception as e:
            self.add_result("spatial_coherence", False, str(e))
            return False
    
    def test_coordinate_alignment(self, remapped_nc=None, reference_nc=None):
        if remapped_nc is None:
            remapped_nc = str(base_dir / "outputs" / "gpw_v4_LandWaterMask_agroclim.nc")
        if reference_nc is None:
            reference_nc = str(base_dir / "data" / "source" / "agroclim_indicator-202312.nc")
        """Test 7: Verify coordinate alignment with reference grid."""
        print("\n" + "="*60)
        print("TEST 7: Coordinate Alignment")
        print("="*60)
        
        if not os.path.exists(remapped_nc):
            self.add_result("coordinate_alignment", False, f"Remapped file not found")
            return False
        
        if not os.path.exists(reference_nc):
            print(f"  ⚠ Reference file not found, skipping coordinate comparison")
            self.add_warning("Reference file not available for coordinate comparison")
            return True
        
        try:
            ds_remap = xr.open_dataset(remapped_nc)
            ds_ref = xr.open_dataset(reference_nc)
            
            # Compare dimensions
            dims_match = (
                ds_remap.dims.get('lon') == ds_ref.dims.get('lon') and
                ds_remap.dims.get('lat') == ds_ref.dims.get('lat')
            )
            
            print(f"  Dimension match: {'✓' if dims_match else '✗'}")
            print(f"    Remapped: lon={ds_remap.dims.get('lon')}, lat={ds_remap.dims.get('lat')}")
            print(f"    Reference: lon={ds_ref.dims.get('lon')}, lat={ds_ref.dims.get('lat')}")
            
            # Compare coordinate arrays
            lon_match = np.allclose(ds_remap.lon.values, ds_ref.lon.values, atol=1e-6)
            lat_match = np.allclose(ds_remap.lat.values, ds_ref.lat.values, atol=1e-6)
            
            print(f"  Longitude array match: {'✓' if lon_match else '✗'}")
            print(f"  Latitude array match: {'✓' if lat_match else '✗'}")
            
            # Check coordinate spacing
            if len(ds_remap.lon) > 1:
                lon_spacing = np.diff(ds_remap.lon.values).mean()
                lat_spacing = np.diff(ds_remap.lat.values).mean()
                print(f"  Coordinate spacing: lon={lon_spacing:.6f}°, lat={lat_spacing:.6f}°")
            
            passed = dims_match and lon_match and lat_match
            
            self.add_result(
                "coordinate_alignment",
                passed,
                "Coordinates perfectly aligned" if passed else "Coordinate misalignment detected",
                {
                    'dims_match': dims_match,
                    'lon_match': lon_match,
                    'lat_match': lat_match
                }
            )
            
            ds_remap.close()
            ds_ref.close()
            return passed
            
        except Exception as e:
            self.add_result("coordinate_alignment", False, str(e))
            return False
    
    def test_data_loss_boundaries(self, global_nc=None, remapped_nc=None):
        if global_nc is None:
            global_nc = str(base_dir / "data" / "intermediate" / "gpw_v4_LandWaterMask_global.nc")
        if remapped_nc is None:
            remapped_nc = str(base_dir / "outputs" / "gpw_v4_LandWaterMask_agroclim.nc")
        """Test 8: Check for data loss at tile boundaries."""
        print("\n" + "="*60)
        print("TEST 8: Tile Boundary Data Loss")
        print("="*60)
        
        if not os.path.exists(global_nc):
            self.add_result("data_loss_boundaries", False, "Global file not found")
            return False
        
        try:
            ds = xr.open_dataset(global_nc)
            data = ds.land_water_mask.values
            
            # Check for strips of NoData at tile boundaries
            # Tiles are arranged in 4x2 grid, each 10800 pixels
            tile_width = 10800
            tile_height = 10800
            
            boundary_issues = []
            
            # Check vertical boundaries (between columns)
            for col in range(1, 4):  # 3 vertical boundaries
                boundary_x = col * tile_width
                
                # Sample around boundary
                left_strip = data[:, boundary_x-10:boundary_x]
                right_strip = data[:, boundary_x:boundary_x+10]
                
                # Check for excessive NoData
                left_nodata = np.sum(left_strip == -9999) / left_strip.size * 100
                right_nodata = np.sum(right_strip == -9999) / right_strip.size * 100
                
                if left_nodata > 50 or right_nodata > 50:
                    boundary_issues.append(f"Vertical boundary {col}: excessive NoData")
                    print(f"  ⚠ Vertical boundary {col}: {left_nodata:.1f}% / {right_nodata:.1f}% NoData")
            
            # Check horizontal boundary (between rows)
            boundary_y = tile_height
            top_strip = data[boundary_y-10:boundary_y, :]
            bottom_strip = data[boundary_y:boundary_y+10, :]
            
            top_nodata = np.sum(top_strip == -9999) / top_strip.size * 100
            bottom_nodata = np.sum(bottom_strip == -9999) / bottom_strip.size * 100
            
            if top_nodata > 50 or bottom_nodata > 50:
                boundary_issues.append(f"Horizontal boundary: excessive NoData")
                print(f"  ⚠ Horizontal boundary: {top_nodata:.1f}% / {bottom_nodata:.1f}% NoData")
            
            if not boundary_issues:
                print("  ✓ No significant data loss at tile boundaries")
            
            passed = len(boundary_issues) == 0
            
            self.add_result(
                "data_loss_boundaries",
                passed,
                "No boundary data loss" if passed else f"{len(boundary_issues)} boundary issues detected",
                {'issues': boundary_issues}
            )
            
            ds.close()
            return passed
            
        except Exception as e:
            self.add_result("data_loss_boundaries", False, str(e))
            return False
    
    def test_metadata_preservation(self, remapped_nc=None):
        if remapped_nc is None:
            remapped_nc = str(base_dir / "outputs" / "gpw_v4_LandWaterMask_agroclim.nc")
        """Test 9: Verify metadata is properly preserved."""
        print("\n" + "="*60)
        print("TEST 9: Metadata Preservation")
        print("="*60)
        
        if not os.path.exists(remapped_nc):
            self.add_result("metadata_preservation", False, "Remapped file not found")
            return False
        
        try:
            ds = xr.open_dataset(remapped_nc)
            
            required_attrs = {
                'variable': ['long_name', 'units', '_FillValue', 'flag_values', 'flag_meanings'],
                'global': ['Conventions', 'title'],
                'coordinates': ['units', 'standard_name']
            }
            
            missing_attrs = []
            
            # Check variable attributes
            var_attrs = ds.land_water_mask.attrs
            for attr in required_attrs['variable']:
                if attr not in var_attrs:
                    missing_attrs.append(f"Variable: {attr}")
                else:
                    print(f"  ✓ Variable attr '{attr}': {var_attrs[attr]}")
            
            # Check global attributes
            for attr in required_attrs['global']:
                if attr not in ds.attrs:
                    missing_attrs.append(f"Global: {attr}")
                else:
                    print(f"  ✓ Global attr '{attr}': {ds.attrs[attr]}")
            
            # Check coordinate attributes
            for coord in ['lon', 'lat']:
                if coord in ds.coords:
                    coord_attrs = ds.coords[coord].attrs
                    for attr in required_attrs['coordinates']:
                        if attr not in coord_attrs:
                            missing_attrs.append(f"{coord}: {attr}")
            
            passed = len(missing_attrs) == 0
            
            if missing_attrs:
                print(f"\n  Missing attributes: {', '.join(missing_attrs)}")
            
            self.add_result(
                "metadata_preservation",
                passed,
                "All metadata preserved" if passed else f"{len(missing_attrs)} attributes missing",
                {'missing': missing_attrs}
            )
            
            ds.close()
            return passed
            
        except Exception as e:
            self.add_result("metadata_preservation", False, str(e))
            return False
    
    def test_cdo_availability(self):
        """Test 10: Verify CDO is available and working."""
        print("\n" + "="*60)
        print("TEST 10: CDO Availability")
        print("="*60)
        
        try:
            result = subprocess.run(
                ['cdo', '--version'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )
            
            version_line = result.stdout.split('\n')[0]
            print(f"  ✓ CDO found: {version_line}")
            
            self.add_result(
                "cdo_availability",
                True,
                f"CDO available: {version_line}",
                {'version': version_line}
            )
            return True
            
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print(f"  ✗ CDO not found or not working")
            self.add_result(
                "cdo_availability",
                False,
                "CDO not available",
                {'error': str(e)}
            )
            return False
    
    def generate_report(self):
        """Generate final test report."""
        print("\n" + "="*60)
        print("FINAL TEST REPORT")
        print("="*60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for r in self.test_results if r['passed'])
        failed_tests = total_tests - passed_tests
        
        print(f"\nTests Run: {total_tests}")
        print(f"Passed: {passed_tests} ✓")
        print(f"Failed: {failed_tests} ✗")
        
        if self.errors:
            print(f"\nErrors ({len(self.errors)}):")
            for error in self.errors:
                print(f"  • {error}")
        
        if self.warnings:
            print(f"\nWarnings ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"  ⚠ {warning}")
        
        # Summary by test
        print("\nTest Summary:")
        for result in self.test_results:
            status = "✓" if result['passed'] else "✗"
            print(f"  {status} {result['test']}: {result['message']}")
        
        # Overall assessment
        print("\n" + "="*60)
        if failed_tests == 0 and len(self.warnings) == 0:
            print("RESULT: ALL TESTS PASSED - No data integrity issues detected")
        elif failed_tests == 0:
            print(f"RESULT: TESTS PASSED WITH {len(self.warnings)} WARNINGS")
        else:
            print(f"RESULT: {failed_tests} TESTS FAILED - Data integrity issues detected")
        print("="*60)
        
        # Save detailed report to JSON
        report_file = str(base_dir / "tests" / "watermask_test_report.json")
        with open(report_file, 'w') as f:
            json.dump({
                'summary': {
                    'total_tests': total_tests,
                    'passed': passed_tests,
                    'failed': failed_tests,
                    'warnings': len(self.warnings)
                },
                'results': self.test_results,
                'errors': self.errors,
                'warnings': self.warnings
            }, f, indent=2, default=str)
        
        print(f"\nDetailed report saved to: {report_file}")
        
        return failed_tests == 0


def main():
    """Run all data integrity tests."""
    print("WATER MASK DATA INTEGRITY TEST SUITE")
    print("="*60)
    print("This script tests for data loss and integrity issues")
    print("in the water mask processing pipeline.")
    print("="*60)
    
    tester = WaterMaskDataIntegrityTester()
    
    # Run all tests
    tests = [
        tester.test_source_tiles_completeness,
        tester.test_tile_dimensions,
        tester.test_global_mosaic_coverage,
        tester.test_categorical_value_integrity,
        tester.test_value_distribution_consistency,
        tester.test_spatial_coherence,
        tester.test_coordinate_alignment,
        tester.test_data_loss_boundaries,
        tester.test_metadata_preservation,
        tester.test_cdo_availability
    ]
    
    for test in tests:
        try:
            test()
        except Exception as e:
            print(f"  Unexpected error in test: {e}")
            tester.add_result(test.__name__, False, f"Unexpected error: {e}")
    
    # Generate report
    success = tester.generate_report()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()