from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import chp_jamul_alert as core
from geometry_utils import simplify_closed_polygon
from mark_detail_runtime import (
    area_matches,
    extract_detail_coordinates,
    match_incident,
    parse_detail_lines,
    type_matches,
)


class DetailParserTests(unittest.TestCase):
    def test_rejects_all_incidents_rows_and_keeps_chp_lat_lon_header(self) -> None:
        html = """
        <html><body><table>
          <tr><td>Location: SR94 / Otay Lakes Rd</td>
              <td>Lat/Lon: 32.650000 / -116.930000</td></tr>
          <tr><td>12:53 AM</td><td>UNIT ARRIVED ON SCENE</td></tr>
          <tr><td>Details</td><td>0047</td><td>12:53 AM</td>
              <td>Trfc Collision-1141 Enrt</td><td>Sr94 / Otay Lakes Rd</td>
              <td>JSO</td><td>El Cajon</td></tr>
          <tr><td>Details</td><td>0031</td><td>12:29 AM</td>
              <td>Trfc Collision-1141 Enrt</td><td>I805 S / Camino De La Plaza No</td>
              <td></td><td>San Diego</td></tr>
        </table></body></html>
        """
        lines = parse_detail_lines(html, "0047")
        self.assertTrue(any("Lat/Lon:" in line for line in lines))
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
        self.assertIn("address geocoding disabled", result.reason)

    def test_lat_lon_is_checked_against_polygon(self) -> None:
        incident = SimpleNamespace(
            number="0047",
            incident_type="Trfc Collision-1141 Enrt",
            details=("Lat/Lon: 32.650000 / -116.930000",),
        )
        expected = core.MatchResult(True, "inside configured polygon", "high", 32.65, -116.93, None)
        with patch("mark_detail_runtime.core.coordinate_match", return_value=expected) as coordinate_match:
            result = match_incident(incident)
        coordinate_match.assert_called_once_with((32.65, -116.93))
        self.assertTrue(result.relevant)
        self.assertIn("CHP detail Lat/Lon", result.reason)


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


if __name__ == "__main__":
    unittest.main()
