import os
import sys
import unittest

# Add src to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.n8n.registry import build_schedule_params


class TestScheduleRegistry(unittest.TestCase):
    def test_build_schedule_params_cron_object_to_expression(self):
        params = {
            "cron": {
                "minute": "0",
                "hour": "9",
                "dayOfMonth": "*",
                "month": "*",
                "dayOfWeek": "*",
            }
        }

        result = build_schedule_params(params)

        self.assertEqual(result, {
            "rule": {
                "interval": [
                    {
                        "field": "cronExpression",
                        "expression": "0 9 * * *",
                    }
                ]
            }
        })

    def test_build_schedule_params_daily_at_nine(self):
        params = {
            "interval": 1,
            "unit": "days",
            "hour": 9,
            "minute": 0,
        }

        result = build_schedule_params(params)

        self.assertEqual(result, {
            "rule": {
                "interval": [
                    {
                        "field": "days",
                        "daysInterval": 1,
                        "triggerAtHour": 9,
                        "triggerAtMinute": 0,
                    }
                ]
            }
        })
