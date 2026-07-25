from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from geometry_utils import simplify_closed_polygon
from mark_detail_runtime import area_matches, parse_detail_lines, type_matches


class DetailParserTests(unittest.TestCase):
    def test_rejects_all_incidents_rows_and_keeps_coordinate_header(self) -> None:
        html = """
        <html><body><table>
          <tr><td>Latitude: 32.650000</td><td>Longitude: -116.930000</td></tr>
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
        self.assertTrue(any("32.650000" in line and "-116.930000" in line for line in lines))
        self.assertTrue(any("ARRIVED ON SCENE" in line for line in lines))
        self.assertFalse(any("Otay Lakes Rd" in line for line in lines))
        self.assertFalse(any("Camino De La Plaza" in line for line in lines))


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
