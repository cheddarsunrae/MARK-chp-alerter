import unittest
from unittest.mock import Mock

import chp_detail_alert as detail


LISTING = '''<html><body><div>Border Communications Center</div><div>Number of Incidents: 2</div><div>Updated as of 7/22/2026 9:59:46 AM</div><form><input name="__VIEWSTATE" value="abc"><table>
<tr><th>Details</th><th>No.</th><th>Time</th><th>Type</th><th>Location</th><th>Location Desc.</th><th>Area</th></tr>
<tr><td><a href="javascript:__doPostBack('gvIncidents','Select$8')">Details</a></td><td>0123</td><td>9:50 AM</td><td>Traffic Hazard</td><td>SR94</td><td>Jamul</td><td>El Cajon</td></tr>
<tr><td><a href="javascript:__doPostBack('gvIncidents','Select$9')">Details</a></td><td>0124</td><td>9:51 AM</td><td>Report of Fire</td><td>I5</td><td>Oceanside</td><td>Oceanside</td></tr>
</table></form></body></html>'''

DETAIL = '''<html><body><table><tr><th>Time</th><th>Details</th></tr><tr><td>9:50 AM</td><td>RP REPORTS 11-78 VEH OVER SIDE</td></tr></table></body></html>'''


class DetailAlertTests(unittest.TestCase):
    def test_parse_postback_and_area_discard(self):
        items = detail.parse_incidents(LISTING)
        self.assertEqual("Select$8", items[0].detail_postback)
        self.assertTrue(detail.is_discarded_area(items[1].area))

    def test_alert_code_promotes_non_target_type(self):
        lines = detail.parse_detail_lines(DETAIL)
        self.assertEqual(frozenset({"11-78"}), detail.detail_codes(lines))
        incident = detail.DetailedIncident(
            "0123", "9:50 AM", "Traffic Hazard", "SR94", "Jamul", "El Cajon",
            "7/22/2026 9:59:46 AM", details=lines,
        )
        result = detail.match_incident(
            incident,
            geocoder="none",
            session=Mock(),
            geocode_cache=Mock(),
            geocode_contact=None,
            timeout=20,
        )
        self.assertTrue(result.relevant)
        title, message = detail.build_alert_message(incident, result)
        self.assertIn("11-78", title)
        self.assertIn("RP REPORTS", message)

    def test_1182_is_log_only(self):
        incident = detail.DetailedIncident(
            "0125", "9:50 AM", "Traffic Hazard", "SR94", "Jamul", "El Cajon",
            "7/22/2026 9:59:46 AM", details=("9:50 AM | UNIT REPORTS 11 82",),
        )
        result = detail.match_incident(
            incident,
            geocoder="none",
            session=Mock(),
            geocode_cache=Mock(),
            geocode_contact=None,
            timeout=20,
        )
        self.assertFalse(result.relevant)
        self.assertIn("logged only", result.reason)


if __name__ == "__main__":
    unittest.main()
