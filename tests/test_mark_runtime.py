from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import address_box_runtime
import chp_jamul_alert as core
import mark_backend
from geometry_utils import remove_shorter_path_between, simplify_closed_polygon
from mark_detail_runtime import (
    area_matches,
    extract_detail_coordinates,
    match_incident,
    matched_area_prefixes,
    matched_type_fragments,
    parse_detail_lines,
    type_matches,
)


class DetailParserTests(unittest.TestCase):
    def test_rejects_all_incidents_rows_and_keeps_chp_lat_lon_header(self) -> None:
        html = """
        <html><body>
          <div class="detail-header">Location: SR94 / Otay Lakes Rd</div>
          <span>Lat/Lon: 32.650000 / -116.930000</span>
          <table>
            <tr><td>12:53 AM</td><td>UNIT ARRIVED ON SCENE</td></tr>
            <tr><td>Details</td><td>0047</td><td>12:53 AM</td>
                <td>Trfc Collision-1141 Enrt</td><td>Sr94 / Otay Lakes Rd</td>
                <td>JSO</td><td>El Cajon</td></tr>
            <tr><td>Details</td><td>0031</td><td>12:29 AM</td>
                <td>Trfc Collision-1141 Enrt</td><td>I805 S / Camino De La Plaza No</td>
                <td></td><td>San Diego</td></tr>
          </table>
        </body></html>
        """
        lines = parse_detail_lines(html, "0047")
        self.assertIn("Lat/Lon: 32.650000 / -116.930000", lines)
        self.assertTrue(any("ARRIVED ON SCENE" in line for line in lines))
        self.assertFalse(any("Details | 0047" in line for line in lines))
        self.assertFalse(any("Camino De La Plaza" in line for line in lines))

    def test_extracts_slash_separated_chp_lat_lon(self) -> None:
        self.assertEqual(
            extract_detail_coordinates("Lat/Lon: 32.650000 / -116.930000"),
            (32.65, -116.93),
        )

    def test_extracts_comma_separated_chp_lat_lon(self) -> None:
        self.assertEqual(
            extract_detail_coordinates("Lat/Lon: 32.650000, -116.930000"),
            (32.65, -116.93),
        )

    def test_extracts_lat_lon_split_by_html_markup(self) -> None:
        html = "<div>Lat/Lon:</div><span>32.650000</span><span>-116.930000</span>"
        self.assertEqual(extract_detail_coordinates(html), (32.65, -116.93))

    def test_extracts_cardinal_direction_coordinates(self) -> None:
        self.assertEqual(
            extract_detail_coordinates("Lat/Lon: 32.650000 N / 116.930000 W"),
            (32.65, -116.93),
        )

    def test_missing_lat_lon_does_not_fall_back_to_geocoder(self) -> None:
        incident = SimpleNamespace(
            number="0047",
            incident_type="Trfc Collision-1141 Enrt",
            details=("12:53 AM | UNIT ARRIVED ON SCENE",),
        )
        with patch("mark_detail_runtime.core.coordinate_match") as coordinate_match:
            result = match_incident(incident)
        coordinate_match.assert_not_called()
        self.assertFalse(result.relevant)
        self.assertIn("missing or unparseable CHP Lat/Lon", result.reason)

    def test_lat_lon_is_checked_against_polygon(self) -> None:
        incident = SimpleNamespace(
            number="0047",
            incident_type="Trfc Collision-1141 Enrt",
            details=("Lat/Lon: 32.650000 / -116.930000",),
        )
        expected = core.MatchResult(
            True,
            "inside configured polygon",
            "high",
            32.65,
            -116.93,
            None,
        )
        with patch(
            "mark_detail_runtime.core.coordinate_match",
            return_value=expected,
        ) as coordinate_match:
            result = match_incident(incident)
        coordinate_match.assert_called_once_with((32.65, -116.93))
        self.assertTrue(result.relevant)
        self.assertIn("type fragment match 1141", result.reason)
        self.assertIn("CHP detail Lat/Lon", result.reason)

    def test_non_alertable_type_is_tracked_but_not_alerted_inside_polygon(self) -> None:
        incident = SimpleNamespace(
            number="0048",
            incident_type="Traffic Hazard",
            details=("Lat/Lon: 32.650000 / -116.930000",),
        )
        expected = core.MatchResult(
            True,
            "inside configured polygon",
            "high",
            32.65,
            -116.93,
            None,
        )
        with patch.dict(os.environ, {"CHP_ALERT_TYPE_FRAGMENTS": "1141"}), patch(
            "mark_detail_runtime.core.coordinate_match",
            return_value=expected,
        ):
            result = match_incident(incident)
        self.assertFalse(result.relevant)
        self.assertIn("tracked non-alertable type: Traffic Hazard", result.reason)
        self.assertIn("inside configured polygon", result.reason)


class FastFilterTests(unittest.TestCase):
    def test_station_36_area_prefix_defaults(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CHP_ALERT_AREA_PREFIXES", None)
            self.assertTrue(area_matches("BC"))
            self.assertTrue(area_matches("El Cajon"))
            self.assertFalse(area_matches("San Diego"))
            self.assertFalse(area_matches("Temecula"))
            self.assertFalse(area_matches("Oceanside"))

    def test_area_prefixes_use_first_two_characters(self) -> None:
        with patch.dict(os.environ, {"CHP_ALERT_AREA_PREFIXES": "Sa,Oc"}):
            self.assertTrue(area_matches("San Diego"))
            self.assertTrue(area_matches("Oceanside"))
            self.assertFalse(area_matches("El Cajon"))

    def test_type_fragments_are_case_insensitive_substrings(self) -> None:
        with patch.dict(
            os.environ,
            {"CHP_ALERT_TYPE_FRAGMENTS": "Unk,1140,1141,Min,Maj,1179,1180,1178,un w,Repo"},
        ):
            self.assertTrue(type_matches("Trfc Collision-Unkn Inj"))
            self.assertTrue(type_matches("Trfc Collision-1141 Enrt"))
            self.assertTrue(type_matches("Report of Fire"))
            self.assertTrue(type_matches("MINOR INJURY COLLISION"))
            self.assertFalse(type_matches("Traffic Hazard"))

    def test_wildcards_match_any_area_or_type(self) -> None:
        with patch.dict(
            os.environ,
            {"CHP_ALERT_AREA_PREFIXES": "*", "CHP_ALERT_TYPE_FRAGMENTS": "*"},
        ):
            self.assertTrue(area_matches("Anything"))
            self.assertTrue(type_matches("Anything"))
            self.assertEqual(matched_area_prefixes("Anything"), ("*",))
            self.assertEqual(matched_type_fragments("Anything"), ("*",))


class BoundaryBufferTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_polygon = core.SERVICE_AREA_POLYGON
        self.original_coordinate_match = core.coordinate_match
        core.SERVICE_AREA_POLYGON = (
            (0.0, 0.0),
            (0.0, 0.01),
            (0.01, 0.01),
            (0.01, 0.0),
        )

    def tearDown(self) -> None:
        core.SERVICE_AREA_POLYGON = self.original_polygon
        core.coordinate_match = self.original_coordinate_match

    def test_boundary_buffer_disabled_keeps_outside_coordinates_irrelevant(self) -> None:
        mark_backend.install_generic_coordinate_match(
            "active service-area polygon",
            boundary_buffer_meters=0,
        )
        result = core.coordinate_match((0.005, 0.011))
        self.assertFalse(result.relevant)
        self.assertIn("outside active service-area polygon", result.reason)

    def test_boundary_buffer_alerts_nearby_outside_coordinates(self) -> None:
        mark_backend.install_generic_coordinate_match(
            "active service-area polygon",
            boundary_buffer_meters=250,
        )
        result = core.coordinate_match((0.005, 0.011))
        self.assertTrue(result.relevant)
        self.assertIn("outside active service-area polygon", result.reason)
        self.assertIn("within boundary buffer", result.reason)
        self.assertGreater(result.distance_km or 0, 0)


class AddressBoxTests(unittest.TestCase):
    def test_builds_closed_square_geojson_around_address(self) -> None:
        payload = address_box_runtime.build_address_box_geojson(
            address="1600 Pacific Hwy, San Diego, CA",
            latitude=32.7157,
            longitude=-117.1611,
            half_size_meters=1000,
            display_name="San Diego County Administration Center",
        )
        feature = payload["features"][0]
        ring = feature["geometry"]["coordinates"][0]
        self.assertEqual(payload["type"], "FeatureCollection")
        self.assertEqual(feature["geometry"]["type"], "Polygon")
        self.assertEqual(len(ring), 5)
        self.assertEqual(ring[0], ring[-1])
        self.assertAlmostEqual(feature["properties"]["half_size_meters"], 1000.0)
        self.assertAlmostEqual(feature["properties"]["box_width_meters"], 2000.0)
        west, south = ring[0]
        east, north = ring[2]
        self.assertLess(west, -117.1611)
        self.assertGreater(east, -117.1611)
        self.assertLess(south, 32.7157)
        self.assertGreater(north, 32.7157)

    def test_rejects_unreasonable_box_half_sizes(self) -> None:
        with self.assertRaises(address_box_runtime.AddressBoxError):
            address_box_runtime.parse_half_size_meters("10")
        with self.assertRaises(address_box_runtime.AddressBoxError):
            address_box_runtime.parse_half_size_meters("150000")


class GeometryTests(unittest.TestCase):
    def test_removes_near_collinear_points(self) -> None:
        points = [
            (32.0000, -117.0000),
            (32.0000, -116.9997),
            (32.0000, -116.9994),
            (32.0000, -116.9991),
            (32.0010, -116.9991),
        ]
        simplified = simplify_closed_polygon(points, tolerance_metres=2.0)
        self.assertLess(len(simplified), len(points))
        self.assertGreaterEqual(len(simplified), 3)

    def test_never_reduces_below_three_vertices(self) -> None:
        triangle = [
            (32.0, -117.0),
            (32.0, -116.99),
            (32.01, -116.99),
        ]
        self.assertEqual(simplify_closed_polygon(triangle, 1000), triangle)

    def test_remove_shorter_path_between_two_waypoints(self) -> None:
        points = [
            (0.0, 0.0),
            (0.0, 1.0),
            (0.0, 2.0),
            (1.0, 2.0),
            (1.0, 1.0),
            (1.0, 0.0),
        ]
        revised, removed, selected = remove_shorter_path_between(points, 0, 3)
        self.assertEqual(removed, 2)
        self.assertEqual(selected, 1)
        self.assertEqual(revised[0], points[0])
        self.assertEqual(revised[1], points[3])
        self.assertNotIn(points[1], revised)
        self.assertNotIn(points[2], revised)
        self.assertGreaterEqual(len(revised), 3)

    def test_remove_shorter_path_refuses_adjacent_waypoints(self) -> None:
        points = [
            (0.0, 0.0),
            (0.0, 1.0),
            (1.0, 1.0),
            (1.0, 0.0),
        ]
        with self.assertRaises(ValueError):
            remove_shorter_path_between(points, 0, 1)


if __name__ == "__main__":
    unittest.main()
