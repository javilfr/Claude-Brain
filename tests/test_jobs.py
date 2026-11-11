"""Job search: catalog, ranking, feeds, fit, documents, kit, tracker. Offline:
every network call goes through a fake fetch."""
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from engine import jobfeeds, jobs, mddocx, route

PROFILE = {
    "tags": ["recent_grad", "career_changer", "bilingual_es"],
    "hours_per_week": 8, "min_salary": 80000, "max_years_required": 3, "remote": True,
    "locations": ["Miami", "Coral Gables"],
    "targets": [{"name": "CS", "weight": 1.0, "keywords": ["customer success manager", "implementation specialist"]}],
    "avoid_roles": ["software engineer", "customs"],
    "avoid_keywords": ["data entry"], "bonus_keywords": ["spanish"],
}


def use(i, **kw):
    u = {"id": f"use-{i}", "title": f"Distinct helpful thing number {i} for searching", "category": "networking", "stage": "outreach",
         "how": "Give Claude the posting and ask for a short message with one reason.", "impact": 3, "evidence": "C",
         "lever": "volume", "effort": 20, "repeat": "once", "fits": [], "avoid": [], "surface": "chat"}
    u.update(kw)
    return u


class Catalog(unittest.TestCase):
    def setUp(self):
        self.tax = jobs.taxonomy()

    def test_the_shipped_catalog_is_valid_and_over_a_thousand(self):
        uses = jobs.load_uses()
        errs, warns = jobs.validate(uses, self.tax)
        self.assertEqual(errs, [])
        self.assertEqual(warns, [])
        self.assertGreaterEqual(len(uses), 1000)
        self.assertEqual({u["category"] for u in uses}, set(self.tax["categories"]))

    def test_validation_catches_bad_rows(self):
        bad = [use(1), use(1), use(2, impact=9), use(3, lever="magic"), use(4, fits=["nobody"]), {"id": "x"}]
        errs, _ = jobs.validate(bad, self.tax)
        text = " ".join(errs)
        for want in ("duplicate id", "impact", "lever", "fits", "missing"):
            self.assertIn(want, text)


class Ranking(unittest.TestCase):
    def setUp(self):
        self.tax = jobs.taxonomy()
        self.w, _ = jobs.stage_weights({"applied": 0})

    def test_evidence_and_lever_raise_the_score(self):
        weak = jobs.score_use(use(1), PROFILE, self.tax, self.w)
        strong = jobs.score_use(use(2, evidence="A", lever="referral"), PROFILE, self.tax, self.w)
        self.assertGreater(strong["score"], weak["score"] * 3)

    def test_fit_and_avoid(self):
        fits = jobs.score_use(use(1, fits=["career_changer"]), PROFILE, self.tax, self.w)
        other = jobs.score_use(use(2, fits=["senior"]), PROFILE, self.tax, self.w)
        avoid = jobs.score_use(use(3, avoid=["recent_grad"]), PROFILE, self.tax, self.w)
        self.assertGreater(fits["score"], other["score"])
        self.assertLess(avoid["score"], other["score"])

    def test_the_leaking_step_gets_weight(self):
        w, basis = jobs.stage_weights({"applied": 60, "responded": 0, "interviewed": 0, "offered": 0})
        self.assertGreater(w["materials"], 1.5)
        self.assertIn("responses", basis)
        w2, basis2 = jobs.stage_weights({"applied": 40, "responded": 12, "interviewed": 10, "offered": 0})
        self.assertGreater(w2["interview"], w2["materials"])

    def test_diversity_and_determinism(self):
        uses = [use(i, impact=4) for i in range(10)] + [use(100 + i, category="resume", stage="materials") for i in range(3)]
        a = jobs.rank(uses, PROFILE, self.tax, self.w)
        b = jobs.rank(uses, PROFILE, self.tax, self.w)
        self.assertEqual([r["id"] for r in a], [r["id"] for r in b])
        self.assertIn("resume", [r["category"] for r in a[:8]])


class Feeds(unittest.TestCase):
    def fake(self, routes):
        def fetch(url, data=None, headers=None):
            for key, body in routes.items():
                if key in url:
                    return 200, json.dumps(body).encode() if not isinstance(body, bytes) else body
            return 404, b""
        return fetch

    def test_detect_every_system(self):
        text = ("boards.greenhouse.io/acme jobs.lever.co/beta jobs.ashbyhq.com/gamma apply.workable.com/delta "
                "jobs.smartrecruiters.com/Eps zeta.recruitee.com eta.wd5.myworkdayjobs.com/en-US/Ext theta.bamboohr.com/careers "
                "iota.breezy.hr kappa.jobs.personio.de")
        found = {b["ats"] for b in jobfeeds.detect(text)}
        self.assertEqual(found, set(jobfeeds.READERS))

    def test_greenhouse_lever_ashby_readers(self):
        f = self.fake({
            "boards-api.greenhouse.io/v1/boards/acme/jobs": {"jobs": [{"id": 1, "title": "Customer Success Manager", "location": {"name": "Miami, FL"},
                                                                       "absolute_url": "https://x/1", "updated_at": "2026-11-01", "content": "&lt;p&gt;Spanish a plus. $85,000 - $100,000&lt;/p&gt;"}]},
            "api.lever.co/v0/postings/beta": [{"id": "b1", "text": "Implementation Specialist", "categories": {"location": "Remote - US"},
                                               "hostedUrl": "https://y", "createdAt": 1793000000000, "descriptionPlain": "2+ years", "workplaceType": "remote"}],
            "api.ashbyhq.com/posting-api/job-board/gamma": {"jobs": [{"id": "g", "title": "Senior Software Engineer", "location": "Miami", "jobUrl": "https://z"}]},
        })
        gh = jobfeeds.read_board({"ats": "greenhouse", "slug": "acme"}, f)[0]
        self.assertEqual((gh["salary_min"], gh["salary_max"]), (85000, 100000))
        self.assertIn("Spanish", gh["description"])
        lv = jobfeeds.read_board({"ats": "lever", "slug": "beta"}, f)[0]
        self.assertTrue(lv["remote"])
        ab = jobfeeds.read_board({"ats": "ashby", "slug": "gamma"}, f)
        self.assertEqual(len(ab), 1)

    def test_workday_pages_with_the_first_total(self):
        calls = []

        def f(url, data=None, headers=None):
            body = json.loads(data)
            calls.append(body["offset"])
            n = 45
            rows = [{"title": f"Account Manager {i}", "externalPath": f"/job/{i}", "locationsText": "Miami, FL", "postedOn": "Posted 3 Days Ago"}
                    for i in range(body["offset"], min(n, body["offset"] + 20))]
            return 200, json.dumps({"total": n if body["offset"] == 0 else 0, "jobPostings": rows}).encode()
        rows = jobfeeds.read_board({"ats": "workday", "slug": "t", "host": "t.wd5.myworkdayjobs.com", "site": "Ext"}, f)
        self.assertEqual(len(rows), 45)
        self.assertEqual(calls, [0, 20, 40])
        self.assertTrue(rows[0]["posted"])

    def test_jsonld_and_robots(self):
        page = ('<script type="application/ld+json">{"@type": "JobPosting", "title": "Account Manager", "datePosted": "2026-11-01",'
                '"hiringOrganization": {"name": "Acme"}, "jobLocation": {"address": {"addressLocality": "Miami", "addressRegion": "FL"}},'
                '"baseSalary": {"value": {"minValue": 90000, "maxValue": 110000, "unitText": "YEAR"}}}</script>'
                '<a href="https://boards.greenhouse.io/acme">jobs</a>').encode()
        jobfeeds._robots.clear()
        f = self.fake({"robots.txt": b"User-agent: *\nDisallow: /private\n", "acme.example/careers": page})
        posts, boards, note = jobfeeds.read_page("https://acme.example/careers", "Acme", f)
        self.assertEqual(posts[0]["salary_min"], 90000)
        self.assertEqual(boards[0]["slug"], "acme")
        _, _, note = jobfeeds.read_page("https://acme.example/private/jobs", "Acme", f)
        self.assertIn("robots.txt", note)

    def test_probe_finds_a_board_by_name(self):
        f = self.fake({"boards-api.greenhouse.io/v1/boards/acmecorp": {"name": "Acme Corp"}})
        hits = jobfeeds.probe("Acme Corp Inc.", f)
        self.assertEqual(hits, [{"ats": "greenhouse", "slug": "acmecorp", "company": "Acme Corp Inc."}])


class Fit(unittest.TestCase):
    def p(self, **kw):
        base = jobfeeds.posting("x", "Acme", "Customer Success Manager", "Miami, FL", "https://x", "2026-11-05",
                                "Spanish preferred. 2+ years of experience.")
        base.update(kw)
        return base

    def test_good_match_and_reasons(self):
        s, why = jobfeeds.fit(self.p(), PROFILE)
        self.assertGreater(s, 80)
        self.assertTrue(any("spanish" in w for w in why))

    def test_hard_rejections(self):
        self.assertEqual(jobfeeds.fit(self.p(title="Senior Software Engineer"), PROFILE)[0], 0)
        self.assertEqual(jobfeeds.fit(self.p(title="Customs Specialist"), PROFILE)[0], 0)
        self.assertEqual(jobfeeds.fit(self.p(location="Berlin, Germany"), PROFILE)[0], 0)

    def test_soft_penalties(self):
        good = jobfeeds.fit(self.p(), PROFILE)[0]
        self.assertLess(jobfeeds.fit(self.p(title="Senior Customer Success Manager"), PROFILE)[0], good / 2)
        self.assertLess(jobfeeds.fit(self.p(description="Requires 7+ years of experience in SaaS."), PROFILE)[0], good)
        self.assertLess(jobfeeds.fit(self.p(salary_min=50000, salary_max=60000), PROFILE)[0], good)
        self.assertLess(jobfeeds.fit(self.p(posted="2026-03-01"), PROFILE)[0], good)

    def test_foreign_remote_and_lookalike_places_do_not_count(self):
        for loc in ("Remote - Mexico", "Canada - Ontario - Remote", "France > Rungis : Miami Building", "SPAIN, SP (Remote)"):
            self.assertEqual(jobfeeds.fit(self.p(location=loc, remote=True), PROFILE)[0], 0, loc)
        self.assertGreater(jobfeeds.fit(self.p(location="Remote (US); Toronto, ON; Miami, FL"), PROFILE)[0], 0)

    def test_workday_tenant_from_robots(self):
        def f(url, data=None, headers=None):
            if url == "https://acme.wd5.myworkdayjobs.com/robots.txt":
                return 200, b"Sitemap: https://acme.wd5.myworkdayjobs.com/Acme_Careers/siteMap.xml\nSitemap: https://acme.wd5.myworkdayjobs.com/Agency/siteMap.xml\n"
            return 422, b"{}"
        self.assertEqual(jobfeeds.probe_workday(["acme"], f), [{"ats": "workday", "slug": "acme", "host": "acme.wd5.myworkdayjobs.com", "site": "Acme_Careers"}])

    def test_remote_us_counts_and_salary_parse(self):
        s, _ = jobfeeds.fit(self.p(location="Remote - US", remote=True), PROFILE)
        self.assertGreater(s, 0)
        self.assertEqual(jobfeeds.salary_range("Pay: $90k to $110k"), (90000, 110000))
        self.assertEqual(jobfeeds.salary_range("$25 per hour"), (None, None))


class Documents(unittest.TestCase):
    def test_markdown_to_docx(self):
        md = "<!-- a note\nover two lines -->\n# Ana Ruiz\n^ Miami, FL · ana@example.com\n\n## Experience\n### Analyst, Acme | [add start date] – Present\n- Cut **errors** by 40% ([link](https://x.example))\n\nA paragraph."
        with tempfile.TemporaryDirectory() as d:
            out = mddocx.convert(md, Path(d) / "r.docx", "Ana")
            with zipfile.ZipFile(out) as z:
                self.assertIn("word/document.xml", z.namelist())
                xml = z.read("word/document.xml").decode()
        self.assertNotIn("two lines", xml)
        for want in ("Ana Ruiz", "Heading1", "Heading2", "<w:tab/>", "errors", "by 40%", "w:jc w:val=\"center\""):
            self.assertIn(want, xml)


class Kit(unittest.TestCase):
    def test_init_track_and_gate(self):
        import subprocess
        import sys
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            made = jobs.init_project(p, "Search")
            self.assertIn("tools/jobfeeds.py", made)
            m = json.loads((p / ".brain" / "project.json").read_text())
            self.assertEqual((m["family"], m["kit"]), ("knowledge", "jobsearch"))
            self.assertEqual(jobs.init_project(p, "Search"), [])  # idempotent
            self.assertEqual(route.classify("write the summary section", m)["family"], "career")
            jobs.track(p, "Acme", "CSM", "applied", channel="referral")
            jobs.track(p, "Acme", "CSM", "interview")
            jobs.track(p, "Acme", "CSM", "rejected")
            jobs.track(p, "Beta", "AM", "applied", channel="cold")
            f = jobs.funnel_of({}, jobs.funnel_rows(json.loads("[" + ",".join((p / "tracker.jsonl").read_text().split("\n")[:-1]) + "]")))
            self.assertEqual(f, {"applied": 2, "responded": 1, "interviewed": 1, "offered": 0})
            self.assertIn("| referral | 1 | 1 | 100% |", jobs.tracker_md(p))
            r = subprocess.run([sys.executable, "tools/check.py"], cwd=p, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout)  # the example profile is valid; template documents are skipped
            (p / "documents" / "resume-acme.md").write_text("# Ana Ruiz\n## Experience\n- Did things\n")
            r = subprocess.run([sys.executable, "tools/check.py"], cwd=p, capture_output=True, text=True)
            self.assertTrue((p / "out" / "resume-acme.docx").is_file(), r.stdout)

    def test_never_in_the_brain(self):
        from engine import common as c

        class A:
            path, title, update = str(c.BRAIN_ROOT), "x", False
        self.assertEqual(jobs.cmd_init(A()), 1)


class Routing(unittest.TestCase):
    def test_career_requests(self):
        for text, cls in (("Tailor my resume for this posting", "career.document"), ("Find me jobs in Miami", "career.search"),
                          ("Prepare me for my interview at Visa", "career.interview"), ("Write a cover letter", "career.document")):
            r = route.classify(text)
            self.assertEqual((r["family"], r["task_class"]), ("career", cls), text)
        self.assertEqual(route.classify("Write a letter to my landlord")["family"], "knowledge")


if __name__ == "__main__":
    unittest.main()
