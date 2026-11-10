"""Tests for engine/mlearn.py: determinism and bounded state of fold, the
invariants I-07, I-08, I-10, I-11, I-13 and I-16, and seeded statistical
checks of every learner (bandit, calibration, drift, credit, flakiness,
forgetting, review stopping, sizing, offline IPS)."""
import argparse
import io
import json
import math
import os
import random
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from engine import common as c
from engine import mlearn as m

ROOT = Path(__file__).resolve().parents[1]
CLS, FAM = "software.feature", "software"


def cfg(**over):
    """A private copy of the real config, with dotted overrides."""
    out = json.loads(json.dumps(m.config()))
    for key, val in over.items():
        group, name = key.split("__")
        out[group][name] = val
    return out


def two_arm_cfg(**over):
    """Lead role (opus/medium baseline) with one cheaper arm, sonnet/medium."""
    out = cfg(**over)
    out["bandit"]["arms"] = [["sonnet", "medium"]]
    return out


class Rec:
    """Outcome record factory with unique ids and increasing 'at'."""
    def __init__(self, prefix="o"):
        self.k, self.prefix = 0, prefix

    def outcome(self, model="opus", passed=True, **kw):
        self.k += 1
        r = {"kind": "outcome", "id": f"{self.prefix}{self.k}", "session": kw.pop("session", "s1"),
             "at": f"2026-01-01T{self.k:07d}", "task_class": CLS, "family": FAM, "tier": 1, "risk": "standard",
             "model": model, "effort": "medium", "has_check": True, "passed": passed, "first_pass": passed,
             "rework": 0, "tokens": 100_000, "explored": False, "propensity": 1.0}
        r.update(kw)
        return r


def seeded_state(c_, p_cheap=0.9, p_base=0.9, n=8, seed=0):
    """n outcomes on each of the two arms, as if from normal operation."""
    r, rec = random.Random(seed), Rec("seed")
    rows = [rec.outcome(mo, r.random() < (p_cheap if mo == "sonnet" else p_base)) for mo in ["opus", "sonnet"] * n]
    return m.fold(m.empty_state(), rows, c_), rec


def simulate(seed, c_, p_cheap, p_base, steps, change_at=None, p_after=None):
    """Closed loop: suggest, observe a Bernoulli outcome, fold. Returns the
    picks [(model, explored)] and the final state."""
    st, rec = seeded_state(c_, p_cheap, p_base, seed=seed)
    r = random.Random(1000 + seed)
    picks = []
    for i in range(steps):
        s = m.suggest_arm(st, c_, CLS, FAM, "lead", "standard", 1, True, r)
        pc = p_after if change_at is not None and i >= change_at else p_cheap
        ok = r.random() < (pc if s["model"] == "sonnet" else p_base)
        st = m.fold(st, [rec.outcome(s["model"], ok, explored=s["explored"], propensity=s["propensity"])], c_)
        picks.append((s["model"], s["explored"]))
    return picks, st


def dump(state):
    return json.dumps(state, sort_keys=True)


# ---------------------------------------------------------------- state and fold
class StateAndFold(unittest.TestCase):
    def test_config_every_group_has_help(self):
        raw = json.loads((ROOT / "memory" / "ml_config.json").read_text())
        groups = [k for k, v in raw.items() if isinstance(v, dict)]
        self.assertGreaterEqual(len(groups), 10)
        for g in groups:
            self.assertIn("_help", raw[g], g)

    def test_missing_file_is_empty_state(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(m.load(d), m.empty_state())
            (Path(d) / "stats").mkdir()
            (Path(d) / "stats" / "ml.json").write_text("{broken")
            self.assertEqual(m.load(d), m.empty_state())

    def records(self):
        rec = Rec()
        rows = [rec.outcome("opus", i % 3 != 0, est_tokens=80_000, minutes=30, est_minutes=20, gate="unit",
                            commit=f"c{i // 2}") for i in range(40)]
        rows += [{"kind": "used", "id": "u1", "session": "s1", "at": "2026-01-01T0000001", "item": "rule-a", "followed": True},
                 {"kind": "used", "id": "u2", "session": "s1", "at": "2026-01-01T0000002", "item": "rule-b", "followed": False},
                 {"kind": "review", "id": "r1", "at": "2026-01-02", "found_a": 4, "found_b": 3, "both": 2},
                 {"kind": "correction", "id": "k1", "at": "2026-01-03", "item": "rule-c"},
                 {"kind": "promotion", "id": "p1", "at": "2026-01-01T0000005", "item": "rule-a"},
                 {"kind": "ledger", "id": "l1", "at": "2026-01-01"}]
        return rows

    def test_fold_deterministic_order_free_and_pure(self):
        c_ = cfg()
        rows = self.records()
        start = m.empty_state()
        before = dump(start)
        a = m.fold(start, rows, c_)
        self.assertEqual(dump(start), before, "fold changed its input")
        shuffled = list(rows)
        random.Random(3).shuffle(shuffled)
        b = m.fold(m.empty_state(), shuffled, c_)
        self.assertEqual(dump(a), dump(b))

    def test_fold_ignores_the_clock(self):
        c_ = cfg()
        rows = self.records()
        with mock.patch.dict(os.environ, {"BRAIN_NOW": "2026-01-01T00:00:00Z"}):
            a = m.fold(m.empty_state(), rows, c_)
        with mock.patch.dict(os.environ, {"BRAIN_NOW": "2031-07-09T12:00:00Z"}):
            b = m.fold(m.empty_state(), rows, c_)
        self.assertEqual(dump(a), dump(b))

    def test_fold_idempotent_per_record_id(self):
        c_ = cfg()
        rows = self.records()
        once = m.fold(m.empty_state(), rows, c_)
        self.assertEqual(dump(m.fold(once, rows, c_)), dump(once))
        self.assertEqual(dump(m.fold(m.empty_state(), rows + rows, c_)), dump(once))
        self.assertEqual(once["n"], len(rows) - 1)  # the ledger kind is not folded

    def test_state_stays_bounded(self):
        c_ = cfg()
        rec = Rec()
        rows = [rec.outcome("opus" if i % 2 else "sonnet", i % 5 != 0, est_tokens=90_000, minutes=10, est_minutes=12,
                            session=f"s{i}") for i in range(2600)]
        st = m.fold(m.empty_state(), rows, c_)
        self.assertEqual(len(st["seen"]), c_["state"]["seen_cap"])
        self.assertLessEqual(len(st["log"]), c_["state"]["outcome_log_cap"])
        self.assertLessEqual(len(st["window"]), c_["explore"]["window"])
        self.assertLessEqual(len(st["calib"]["c"][CLS]["tok"]["r"]), c_["state"]["ratio_cap"])
        self.assertLessEqual(len(st["pending"]), c_["state"]["pending_session_cap"])
        self.assertLess(len(json.dumps(st)), 200_000)
        for cell in st["bandit"]["c"][CLS].values():
            self.assertLessEqual(cell[1], c_["bandit"]["n_cap"] + 1e-9)

    def test_missing_optional_fields_tolerated(self):
        c_ = cfg()
        rows = [{"kind": "outcome", "id": "a"}, {"kind": "outcome", "id": "b", "task_class": CLS, "model": "opus"},
                {"kind": "used", "id": "c"}, {"kind": "review", "id": "d", "found_a": 2},
                {"kind": "correction", "id": "e"}, {"kind": "promotion", "id": "f"}, "not a dict", None]
        st = m.fold(m.empty_state(), rows, c_)
        self.assertEqual(st["n"], 6)
        self.assertEqual(st["bandit"]["raw_g"], {})
        self.assertTrue(m.report(st, c_))

    def test_records_without_id_get_a_content_hash(self):
        c_ = cfg()
        r = {"kind": "outcome", "at": "2026-01-01", "task_class": CLS, "model": "opus", "effort": "medium",
             "has_check": True, "passed": True}
        once = m.fold(m.empty_state(), [r], c_)
        self.assertEqual(dump(m.fold(once, [dict(r)], c_)), dump(once))


# ---------------------------------------------------------------- bandit
class Bandit(unittest.TestCase):
    def test_I10_safe_arms_only_baseline_when_unsafe(self):
        c_ = cfg()
        base = m.baseline(c_, "lead")
        self.assertGreater(len(m.safe_arms(c_, "lead", "standard", 2, True)), 1)
        for risk, tier, check in (("standard", 1, False), ("high", 1, True), ("standard", 3, True),
                                  (None, 1, True), ("standard", None, True)):
            with self.subTest(risk=risk, tier=tier, check=check):
                self.assertEqual(m.safe_arms(c_, "lead", risk, tier, check), [base])
        for arm in m.safe_arms(c_, "lead", "trivial", 0, True)[1:]:
            self.assertLess(m._unit_price(arm, c_), m._unit_price(base, c_), "only cheaper arms are explored")

    def test_I10_suggest_never_leaves_baseline_when_unsafe(self):
        """Even with a state that strongly favours the cheap arm."""
        c_ = two_arm_cfg()
        st, _ = seeded_state(c_, p_cheap=1.0, p_base=0.5, n=30)
        r = random.Random(5)
        self.assertIn("sonnet", {m.suggest_arm(st, c_, CLS, FAM, "lead", "standard", 1, True, r)["model"]
                                 for _ in range(30)})
        for risk, tier, check in (("standard", 1, False), ("high", 1, True), ("standard", 3, True)):
            for _ in range(40):
                s = m.suggest_arm(st, c_, CLS, FAM, "lead", risk, tier, check, r)
                self.assertEqual((s["model"], s["effort"]), ("opus", "medium"))
                self.assertFalse(s["explored"])
                self.assertEqual(s["propensity"], 1.0)

    def test_I10_exploration_at_most_one_in_four(self):
        """Over a closed loop where the cheap arm is never exploitable, the
        explored share of eligible tasks in the window stays at or under 25%."""
        c_ = two_arm_cfg()
        picks, st = simulate(2, c_, p_cheap=0.5, p_base=0.95, steps=120)
        win = st["window"]
        elig = sum(w[0] for w in win)
        expl = sum(1 for w in win if w[0] and w[1])
        self.assertLessEqual(expl, 0.25 * elig)
        self.assertLessEqual(sum(e for _, e in picks), 0.25 * len(picks) + 2)

    def test_I10_waste_cap_stops_exploration(self):
        c_ = two_arm_cfg()
        st, rec = seeded_state(c_, p_cheap=0.5, p_base=0.95)
        st = m.fold(st, [rec.outcome("sonnet", False, explored=True, tokens=5_000_000)], c_)
        self.assertFalse(m._budget_ok(st, c_))
        r = random.Random(1)
        self.assertFalse(any(m.suggest_arm(st, c_, CLS, FAM, "lead", "standard", 1, True, r)["explored"]
                             for _ in range(50)))

    def test_I16_fewer_than_8_outcomes_on_two_arms_returns_default(self):
        c_ = two_arm_cfg()
        st, _ = seeded_state(c_, p_cheap=1.0, p_base=0.2, n=7)
        for seed in range(30):
            s = m.suggest_arm(st, c_, CLS, FAM, "lead", "standard", 1, True, random.Random(seed))
            self.assertEqual((s["model"], s["effort"], s["explored"]), ("opus", "medium", False))
        self.assertIn("role default", s["basis"])
        self.assertIn("0 of 2 safe arms have 8+ outcomes", s["basis"])
        rec = Rec("extra")
        one_ready = m.fold(st, [rec.outcome("opus", False) for _ in range(20)], c_)
        s = m.suggest_arm(one_ready, c_, CLS, FAM, "lead", "standard", 1, True, random.Random(0))
        self.assertIn("1 of 2 safe arms", s["basis"])
        self.assertEqual(s["model"], "opus")
        st8, _ = seeded_state(c_, p_cheap=1.0, p_base=0.2, n=8)
        s = m.suggest_arm(st8, c_, CLS, FAM, "lead", "standard", 1, True, random.Random(0))
        self.assertIn("Thompson on 16 outcomes over 2 arms", s["basis"])

    def test_I13_same_seed_same_choice(self):
        c_ = two_arm_cfg()
        st, _ = seeded_state(c_)
        a = [m.suggest_arm(st, c_, CLS, FAM, "lead", "standard", 1, True, random.Random(k)) for k in range(20)]
        b = [m.suggest_arm(st, c_, CLS, FAM, "lead", "standard", 1, True, random.Random(k)) for k in range(20)]
        self.assertEqual(a, b)

    def test_converges_to_cheaper_arm_when_pass_rates_equal(self):
        """Both arms pass 95%: the cheaper arm takes most of the last 100 of
        300 picks. Measured over 16 seeds: mean share 0.82, lowest 0.53 (it
        was 0.72 after 200 picks: the conservative exploitation rule makes
        convergence gradual, which is the price of I-10)."""
        c_ = two_arm_cfg()
        shares = sorted(sum(mo == "sonnet" for mo, _ in simulate(s, c_, 0.95, 0.95, 300)[0][-100:]) / 100
                        for s in range(8))
        self.assertGreater(sum(shares) / len(shares), 0.65, shares)
        self.assertGreater(shares[len(shares) // 2], 0.6, shares)

    def test_converges_to_reliable_arm_when_cheap_fails(self):
        c_ = two_arm_cfg()
        shares = [sum(mo == "sonnet" for mo, _ in simulate(s, c_, 0.4, 0.9, 150)[0][-50:]) / 50 for s in range(8)]
        self.assertLess(sum(shares) / len(shares), 0.08, shares)

    def test_discounting_recovers_faster_after_a_change(self):
        """The cheap arm's pass rate drops from 0.95 to 0.3 at step 200 with no
        model-id change. Measured: about 8 cheap picks in the next 60 with
        gamma 0.97 and n_cap 40, about 26 without discounting."""
        disc, flat = two_arm_cfg(), two_arm_cfg(bandit__gamma=1.0, bandit__n_cap=1e9)
        after = lambda c_, s: sum(mo == "sonnet" for mo, _ in simulate(s, c_, 0.95, 0.95, 260, 200, 0.3)[0][200:])
        d = sum(after(disc, s) for s in range(6))
        f = sum(after(flat, s) for s in range(6))
        self.assertLess(d * 1.5, f, (d, f))

    def test_model_id_change_shrinks_counts(self):
        c_ = two_arm_cfg()
        rec = Rec()
        st = m.fold(m.empty_state(), [rec.outcome("claude-sonnet-5-5") for _ in range(30)], c_)
        self.assertGreater(st["bandit"]["g"]["sonnet/medium"][1], 15)
        self.assertEqual(st["bandit"]["ids"]["sonnet/medium"], "claude-sonnet-5-5")
        st = m.fold(st, [rec.outcome("claude-sonnet-5-6", passed=False)], c_)
        n0 = c_["bandit"]["model_change_n"]
        for level in ("g", "raw_g"):
            self.assertLessEqual(st["bandit"][level]["sonnet/medium"][1], n0 + 1 + 1e-9)
        self.assertLessEqual(st["bandit"]["c"][CLS]["sonnet/medium"][1], n0 + 1 + 1e-9)
        self.assertEqual(st["bandit"]["ids"]["sonnet/medium"], "claude-sonnet-5-6")
        # The prior mean survives the shrink: 30 passes then 1 fail stays high.
        a, b, _ = m.posterior(st, c_, "sonnet/medium", CLS, FAM)
        self.assertGreater(a / (a + b), 0.7)

    def test_hierarchy_new_class_borrows_from_family(self):
        c_ = two_arm_cfg()
        rec = Rec()
        st = m.fold(m.empty_state(), [rec.outcome("sonnet", False) for _ in range(30)], c_)
        a, b, _ = m.posterior(st, c_, "sonnet/medium", "software.brand-new", FAM)
        self.assertLess(a / (a + b), 0.3)
        a, b, _ = m.posterior(st, c_, "sonnet/medium", "data.other", "data")
        self.assertLess(a / (a + b), 0.5)  # global pulls a new family too, more weakly

    def test_propensities_sum_to_one(self):
        c_ = two_arm_cfg()
        st, _ = seeded_state(c_, p_cheap=0.9, p_base=0.9, n=12)
        probs = m.arm_probabilities(st, c_, CLS, FAM, "lead", "standard", 1, True, random.Random(4), draws=300)
        self.assertAlmostEqual(sum(probs.values()), 1.0, places=9)
        s = m.suggest_arm(st, c_, CLS, FAM, "lead", "standard", 1, True, random.Random(9))
        self.assertAlmostEqual(s["propensity"], probs[f"{s['model']}/{s['effort']}"], delta=0.15)
        self.assertGreater(s["propensity"], 0)


# ---------------------------------------------------------------- offline check
class Offline(unittest.TestCase):
    def test_ips_hand_example_with_clipping_and_ess(self):
        c_ = cfg()
        rows = [{"arm": "a", "reward": 1.0, "propensity": 0.5}, {"arm": "b", "reward": 0.0, "propensity": 0.5},
                {"arm": "a", "reward": 0.0, "propensity": 0.05}]
        out = m.ips(rows, lambda r: 1.0 if r["arm"] == "a" else 0.0, c_)
        # weights 2, 0, min(10, 20) = 10 -> value (2*1 + 10*0) / 12; ESS 144 / 104
        self.assertAlmostEqual(out["value"], 2 / 12)
        self.assertAlmostEqual(out["ess"], round(144 / 104, 3))
        self.assertFalse(out["trusted"])
        many = [{"arm": a, "reward": 1.0, "propensity": 1.0} for a in ("a", "b") for _ in range(40)]
        self.assertTrue(m.ips(many, lambda r: 0.5, c_)["trusted"])
        few = [{"arm": "a", "reward": 1.0, "propensity": 1.0}] * 60 + [{"arm": "b", "reward": 1.0, "propensity": 1.0}] * 5
        self.assertFalse(m.ips(few, lambda r: 0.5, c_)["trusted"], "needs 10 runs per arm")

    def test_offline_check_on_a_logged_state(self):
        c_ = two_arm_cfg()
        _, st = simulate(1, c_, 0.9, 0.9, 40)
        out = m.offline_check(st, c_)
        self.assertEqual(out["n"], len(st["log"]))
        self.assertGreater(out["ess"], 0)
        self.assertIsNotNone(out["logged"])


# ---------------------------------------------------------------- calibration
class Calibration(unittest.TestCase):
    def test_prior_below_min_n(self):
        c_ = cfg()
        rec = Rec()
        st = m.fold(m.empty_state(), [rec.outcome(tokens=200_000, est_tokens=100_000) for _ in range(4)], c_)
        got = m.calibrate(st, "other.class", "other", 1000, 10, cfg=c_)
        self.assertEqual((got["n"], got["level"], got["tokens_p50"], got["tokens_p80"]), (0, "prior", 1000.0, 1500.0))

    def test_quantiles_cover_the_right_fraction(self):
        """Synthetic lognormal ratios (median 1.5x, sigma 0.4): about half of
        new tasks fall under p50 and about 80% under p80."""
        c_ = cfg()
        r, rec = random.Random(7), Rec()
        rows = [rec.outcome(tokens=int(100_000 * math.exp(r.gauss(math.log(1.5), 0.4))), est_tokens=100_000,
                            minutes=20 * math.exp(r.gauss(math.log(1.5), 0.4)), est_minutes=20) for _ in range(120)]
        st = m.fold(m.empty_state(), rows, c_)
        cal = m.calibrate(st, CLS, FAM, 100_000, 20, cfg=c_)
        self.assertEqual(cal["level"], "class")
        new = [100_000 * math.exp(r.gauss(math.log(1.5), 0.4)) for _ in range(4000)]
        under50 = sum(x <= cal["tokens_p50"] for x in new) / len(new)
        under80 = sum(x <= cal["tokens_p80"] for x in new) / len(new)
        self.assertAlmostEqual(under50, 0.5, delta=0.15)
        self.assertAlmostEqual(under80, 0.8, delta=0.12)
        self.assertGreater(cal["minutes_p50"], 20)

    def test_new_class_uses_family_level(self):
        c_ = cfg()
        rec = Rec()
        st = m.fold(m.empty_state(), [rec.outcome(tokens=200_000, est_tokens=100_000) for _ in range(10)], c_)
        got = m.calibrate(st, "software.unseen", FAM, 1000, None, cfg=c_)
        self.assertEqual(got["level"], "family")
        self.assertAlmostEqual(got["tokens_p50"], 2000.0, delta=1)
        self.assertIsNone(got["minutes_p50"])


# ---------------------------------------------------------------- drift
def drift_run(seed, n, shift_at=None, mult=1.4, fail_after=None, sigma=0.25, pfail=0.2, c_=None):
    """Index of the first alarm (None if quiet) on a seeded class stream."""
    c_ = c_ or cfg()
    r, rec = random.Random(seed), Rec()
    rows = []
    for i in range(n):
        x = r.gauss(math.log(100_000), sigma)
        pf = pfail
        if shift_at is not None and i >= shift_at:
            x += math.log(mult)
            pf = pfail if fail_after is None else fail_after
        ok = r.random() >= pf
        rows.append(rec.outcome(tokens=int(math.exp(x)), passed=ok, first_pass=ok))
    st = m.fold(m.empty_state(), rows, c_)
    return (st["alarms"][0]["n"] - 1 if st["alarms"] else None), st


class Drift(unittest.TestCase):
    def test_quiet_on_stationary_noise(self):
        """False alarms: 100 seeded stationary runs of 200 tasks (log tokens
        sigma 0.25, 20% first-pass failures). Measured with the shipped
        constants: 7.0% of 300 runs raised any alarm (about one per 2,600
        charted tasks). Bound asserted: at most 12%."""
        hits = sum(drift_run(seed, 200)[0] is not None for seed in range(100))
        self.assertLessEqual(hits, 12)

    def test_alarm_on_injected_token_shift(self):
        """+40% tokens per task from task 60. Measured: 86% of 300 runs alarm
        within 40 tasks of the shift, median delay 10 tasks."""
        delays = []
        for seed in range(40):
            first, _ = drift_run(1000 + seed, 100, shift_at=60)
            if first is not None and first >= 60:
                delays.append(first - 60)
        self.assertGreaterEqual(len(delays), 30)
        self.assertLessEqual(sorted(delays)[len(delays) // 2], 14)

    def test_alarm_on_failure_rate_shift(self):
        """First-pass failures 20% -> 60% at task 60, tokens unchanged.
        Measured: 78% of 300 runs alarm, median delay 16 tasks."""
        hits = sum(1 for seed in range(30) if (drift_run(2000 + seed, 100, 60, 1.0, 0.6)[0] or -1) >= 60)
        self.assertGreaterEqual(hits, 18)

    def test_alarm_line_names_last_promotion_and_has_effects(self):
        c_ = cfg()
        r, rec = random.Random(1), Rec()
        rows = [rec.outcome(tokens=int(math.exp(r.gauss(11.5, 0.2))), est_tokens=100_000) for _ in range(40)]
        rows.append({"kind": "promotion", "id": "p1", "at": rows[30]["at"], "item": "rule-new-habit"})
        rows += [rec.outcome(tokens=int(math.exp(r.gauss(12.5, 0.2))), est_tokens=100_000) for _ in range(12)]
        st = m.fold(m.empty_state(), rows, c_)
        self.assertTrue(st["alarms"])
        lines = m.alarms(st, c_)
        self.assertLessEqual(len(lines), 3)
        self.assertIn("rule-new-habit", lines[0])
        self.assertIn("software.feature", lines[0])
        self.assertIn("nothing was reverted", lines[0])
        # calibration n was capped at the alarm, then grew again by at most the tasks since
        since = 52 - st["alarms"][0]["n"]
        self.assertLessEqual(st["calib"]["c"][CLS]["tok"]["n"], c_["calibration"]["drift_cap"] + since)


# ---------------------------------------------------------------- memory credit
class Credit(unittest.TestCase):
    def session(self, rec, sid, items, passed):
        rows = [{"kind": "used", "id": f"u-{sid}-{i}", "session": sid, "at": "2026-01-01", "item": it, "followed": True}
                for i, it in enumerate(items)]
        rows.append(rec.outcome(passed=passed, session=sid))
        return rows

    def test_I07_no_credit_from_self_report_or_without_a_check(self):
        c_ = cfg()
        rec = Rec()
        rows = [{"kind": "used", "id": "u1", "session": "s9", "at": "2026-01-01", "item": "rule-x", "followed": True,
                 "helped": True}]
        st = m.fold(m.empty_state(), rows, c_)
        self.assertNotIn("rule-x", st["credit"])
        st = m.fold(st, [rec.outcome(passed=True, session="s9", has_check=False)], c_)
        self.assertNotIn("rule-x", st["credit"], "an outcome without a verifying check gives no credit")
        st = m.fold(st, [rec.outcome(passed=True, session="s9")], c_)
        self.assertGreater(st["credit"]["rule-x"][0], 0)

    def test_only_followed_items_get_credit_split_equally(self):
        c_ = cfg()
        rec = Rec()
        rows = self.session(rec, "s1", ["rule-a", "rule-b"], True)
        rows.append({"kind": "used", "id": "u-ign", "session": "s1", "at": "2026-01-01", "item": "rule-c", "followed": False})
        st = m.fold(m.empty_state(), rows, c_)
        adv = 1.0 - c_["credit"]["baseline_prior"]
        self.assertAlmostEqual(st["credit"]["rule-a"][0], adv / 2, places=5)
        self.assertEqual(st["credit"]["rule-c"], [0.0, 0.0, 0, 1])

    def test_item_score_ranks_helpful_above_harmful(self):
        c_ = cfg()
        r, rec = random.Random(2), Rec()
        rows = []
        for k in range(40):
            good = r.random() < 0.5
            item = "rule-good" if good else "rule-bad"
            rows += self.session(rec, f"s{k}", [item], r.random() < (0.9 if good else 0.2))
        st = m.fold(m.empty_state(), rows, c_)
        good = m.item_score(st, {"id": "rule-good", "trust": "observed"}, c_)
        bad = m.item_score(st, {"id": "rule-bad", "trust": "observed"}, c_)
        self.assertGreater(good, bad)
        for v in (good, bad):
            self.assertTrue(0.7 <= v <= 1.3)
        self.assertEqual(m.item_score(st, {"id": "rule-unseen", "trust": "observed"}, c_), 1.0)

    def test_I08_owner_stated_always_top_multiplier(self):
        c_ = cfg()
        rec = Rec()
        rows = []
        for k in range(20):
            rows += self.session(rec, f"s{k}", ["own-rule"], False)
            rows.append({"kind": "correction", "id": f"k{k}", "at": "2026-01-02", "item": "own-rule"})
        st = m.fold(m.empty_state(), rows, c_)
        self.assertGreater(st["credit"]["own-rule"][1], 10)
        owner = {"id": "own-rule", "trust": "owner-stated", "type": "standing", "last_used": "2020-01-01"}
        self.assertEqual(m.item_score(st, owner, c_), c_["credit"]["high"])
        observed = dict(owner, trust="observed", type="rule")
        self.assertLessEqual(m.item_score(st, observed, c_), 0.75, "the same evidence sinks an observed item")
        self.assertEqual(m.retention(owner, "2030-01-01", c_), 1.0, "owner-stated items never decay")


# ---------------------------------------------------------------- small learners
class SmallLearners(unittest.TestCase):
    def test_chapman_hand_example(self):
        c_ = cfg()
        got = m.review_stop(10, 8, 5, cfg=c_)
        # N = 11 * 9 / 6 - 1 = 15.5; seen = 10 + 8 - 5 = 13; remaining 2.5
        self.assertEqual(got, {"estimated_remaining": 2.5, "another_round": True})
        self.assertFalse(m.review_stop(6, 6, 6, cfg=c_)["another_round"])  # N = 6: nothing left
        self.assertTrue(m.review_stop(3, 4, 0, cfg=c_)["another_round"])  # no overlap: many unseen
        self.assertFalse(m.review_stop(10, 8, 5, rounds=3, cfg=c_)["another_round"])  # never past 3 rounds
        self.assertFalse(m.review_stop(0, 0, 0, cfg=c_)["another_round"])
        with self.assertRaises(ValueError):
            m.review_stop(2, 2, 3, cfg=c_)

    def test_flaky_gate(self):
        c_ = cfg()
        rec = Rec()
        flaky_runs = [rec.outcome(gate_runs=[{"gate": "e2e", "commit": f"c{k}", "exit": 1},
                                             {"gate": "e2e", "commit": f"c{k}", "exit": 0}]) for k in range(4)]
        real = [rec.outcome(gate_runs=[{"gate": "unit", "commit": f"c{k}", "exit": 1},
                                       {"gate": "unit", "commit": f"d{k}", "exit": 0}]) for k in range(4)]
        st = m.fold(m.empty_state(), flaky_runs + real, c_)
        self.assertGreaterEqual(m.flaky(st, "e2e", c_), c_["flaky"]["rerun"])
        self.assertLess(m.flaky(st, "unit", c_), c_["flaky"]["rerun"])
        self.assertLess(m.flaky(st, "never-seen", c_), c_["flaky"]["rerun"])

    def test_retention_curve(self):
        c_ = cfg()
        item = {"id": "rule-a", "type": "rule", "trust": "observed", "last_used": "2026-01-01", "uses": 0}
        r0 = m.retention(item, "2026-01-01", c_)
        r45 = m.retention(item, "2026-02-15", c_)
        self.assertEqual(r0, 1.0)
        self.assertAlmostEqual(r45, math.exp(-1), places=4)
        self.assertGreater(m.retention(dict(item, uses=3), "2026-02-15", c_), r45, "followed uses slow forgetting")
        self.assertGreater(m.retention(dict(item, importance=3), "2026-02-15", c_), r45)
        self.assertEqual(m.retention(dict(item, last_used="garbage", created=None), "2026-02-15", c_), 1.0)

    def sizing_rows(self, n, label, rule, words, kind="correction"):
        return [{"kind": kind, "id": f"z{label}{rule}{i}{kind}", "at": "2026-01-01", "words": words,
                 "rule_tier": rule, "tier": label} for i in range(n)]

    def test_sizing_shadow_below_min_strong(self):
        c_ = cfg()
        st = m.fold(m.empty_state(), self.sizing_rows(10, 1, 2, ["h1", "h2"]), c_)
        got = m.sizing_hint(st, c_, ["h1", "h2"], 2)
        self.assertEqual((got["tier"], got["acted"]), (2, False))
        self.assertIn("10 of 30", got["reason"])
        self.assertEqual(st["sizing"]["shadow"]["n"], 10)

    def test_I11_tier0_never_raised(self):
        c_ = cfg(sizing__act=True)
        st = m.fold(m.empty_state(), self.sizing_rows(80, 1, 0, ["hq", "hz"]) + self.sizing_rows(80, 2, 0, ["hq"])
                    + self.sizing_rows(40, 0, 0, ["hx"]) + self.sizing_rows(40, 3, 3, ["hy"]), c_)
        self.assertGreater(m._nb_posterior(st, c_, ["hq", "hz"], 0)[1], c_["sizing"]["min_conf"],
                           "the learner is confident the answer is tier 1, so only the guard keeps it at 0")
        for words in (["hq", "hz"], ["hq"], ["hq"] * 30):
            got = m.sizing_hint(st, c_, words, 0)
            self.assertEqual(got["tier"], 0)
            self.assertFalse(got["acted"])

    def test_sizing_acts_only_to_lower(self):
        c_ = cfg(sizing__act=True)
        st = m.fold(m.empty_state(), self.sizing_rows(60, 1, 2, ["ha", "hb"]) + self.sizing_rows(60, 2, 1, ["hc", "hd"])
                    + self.sizing_rows(20, 0, 0, ["hx"]) + self.sizing_rows(20, 3, 3, ["hy"]), c_)
        down = m.sizing_hint(st, c_, ["ha", "hb"], 2)
        self.assertEqual((down["tier"], down["acted"]), (1, True))
        up = m.sizing_hint(st, c_, ["hc", "hd"], 1)
        self.assertEqual((up["tier"], up["acted"]), (2, False), "a raise is only ever a hint")
        off = m.sizing_hint(st, cfg(), ["ha", "hb"], 2)
        self.assertFalse(off["acted"], "shadow unless sizing.act")


# ---------------------------------------------------------------- report and cli
class ReportAndCli(unittest.TestCase):
    def full_state(self):
        c_ = two_arm_cfg()
        _, st = simulate(3, c_, 0.9, 0.9, 30)
        rec = Rec("x")
        st = m.fold(st, [rec.outcome(est_tokens=80_000, gate="unit", commit="a") for _ in range(6)] +
                    [{"kind": "used", "id": "uu", "session": "s1", "at": "2026-02-01", "item": "rule-a", "followed": True},
                     {"kind": "review", "id": "rv", "at": "2026-02-01", "found_a": 3, "found_b": 3, "both": 1}] +
                    TestHelpers.sizing(), c_)
        return st, c_

    def test_report_short_and_every_claim_has_n(self):
        st, c_ = self.full_state()
        lines = m.report(st, c_)
        self.assertLessEqual(len(lines), 12)
        self.assertGreaterEqual(len(lines), 6)
        for line in lines:
            self.assertRegex(line, r"\d", line)
        self.assertEqual(m.report(m.empty_state(), c_), ["Nothing learned yet: every choice uses the safe defaults (n=0 records)."])

    def test_cli_report_and_alarms(self):
        st, _ = self.full_state()
        with tempfile.TemporaryDirectory() as d:
            for rel in ("memory/ml_config.json", "memory/models.json"):
                (Path(d) / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(ROOT / rel, Path(d) / rel)
            c.write_json(Path(d) / "stats" / "ml.json", st)
            parser = argparse.ArgumentParser()
            m.register(parser.add_subparsers())
            for argv, most in ((["ml", "report"], 12), (["ml", "alarms"], 3), (["ml", "report", "--json"], 1)):
                buf = io.StringIO()
                with mock.patch.object(c, "BRAIN_ROOT", Path(d)), redirect_stdout(buf):
                    args = parser.parse_args(argv)
                    self.assertEqual(args.func(args), 0)
                out = buf.getvalue().strip().splitlines()
                self.assertTrue(1 <= len(out) <= most, (argv, out))


class TestHelpers:
    @staticmethod
    def sizing():
        return [{"kind": "correction", "id": f"zz{i}", "at": "2026-02-02", "words": ["w1"], "rule_tier": 1, "tier": 1}
                for i in range(3)]


if __name__ == "__main__":
    unittest.main()
