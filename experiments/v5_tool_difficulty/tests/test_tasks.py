import importlib.util
import random
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
spec = importlib.util.spec_from_file_location("v5_tasks_under_test", SRC / "tasks.py")
tasks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tasks)


class TasksTest(unittest.TestCase):
    def test_reset_and_global_rng_isolation(self):
        random.seed(11)
        before = random.getstate()
        a = tasks.make_task(3, 17)
        self.assertEqual(before, random.getstate())
        self.assertEqual(a, tasks.make_task(3, 17))
        self.assertNotEqual(a["case_sha256"], tasks.make_task(3, 18)["case_sha256"])

    def test_reference_is_displayed_data_and_ladder_fixed(self):
        for level, n in enumerate((6, 40, 120, 400), 1):
            task = tasks.make_task(level, 1900)
            t, v = map(lambda k: list(map(float, task["case"][k])), ("t_s", "v_m_per_s"))
            self.assertEqual(len(t), n)
            self.assertTrue(all(y > x for x, y in zip(t, t[1:])))
            self.assertEqual(task["key"]["a_ref"], tasks.ls_slope(t, v))
            self.assertEqual(task["key"]["tolerance"], 10 ** (-level - 1))

    def test_calibration_not_computational_difficulty(self):
        task = tasks.make_necessary_task(3)
        self.assertEqual(task["family"], "hidden_input")
        self.assertEqual(task["level"], "calibration")
        self.assertNotEqual(task["case_sha256"], tasks.make_task(1, 3)["case_sha256"])

    def test_bad_parameters(self):
        for level, seed in [(True, 1), (5, 1), (1, -1), (1, True)]:
            with self.assertRaises(ValueError):
                tasks.make_task(level, seed)
