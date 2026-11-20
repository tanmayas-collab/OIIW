import asyncio
import http.server
import socketserver
import threading
import time
import httpx

BASE_URL = "http://127.0.0.1:8011"


class MockSiteHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        html = """<!DOCTYPE html>
        <html>
        <head>
            <title>Acme SaaS — Automated B2B Workflow Platform</title>
            <meta name="description" content="Acme SaaS helps Indian B2B teams automate operations." />
        </head>
        <body>
            <h1>Acme Workflow Automation</h1>
            <h2>How does Acme reduce manual ops?</h2>
            <p>Acme automates repetitive B2B workflows with auditable precision.</p>
            <img src="/hero.png" />
            <a href="/pricing">Pricing</a>
        </body>
        </html>"""
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def log_message(self, format, *args):
        return


def start_mock_site():
    httpd = socketserver.TCPServer(("127.0.0.1", 0), MockSiteHandler)
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd, port


async def run_all_tests():
    httpd, mock_port = start_mock_site()
    target_url = f"http://127.0.0.1:{mock_port}/"

    try:
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=15.0) as client:
            # 1. Health & SQLite WAL verification
            r = await client.get("/health")
            assert r.status_code == 200, f"Health failed: {r.text}"
            health = r.json()
            assert health["status"] == "healthy"
            assert health["sqlite_journal_mode"] == "wal", f"Expected WAL mode, got {health}"
            print("[PASS] 1. Health check & SQLite WAL mode verified:", health)

            # 2. Dashboard HTML & collapsed-by-default sections
            r = await client.get("/")
            assert r.status_code == 200
            assert '<details class="collapsible">' in r.text
            assert '<details class="collapsible" open>' not in r.text
            print("[PASS] 2. Dashboard HTML served with collapsible sections collapsed by default.")

            # 3. User Registration & Per-User Isolation
            ts = int(time.time())
            r_a = await client.post("/api/v1/auth/register", json={
                "email": f"founder_{ts}@pulserank.in",
                "password": "StrongPassword123",
                "full_name": "Tanmay Test",
                "gstin": "27AABCU9603R1ZM"
            })
            assert r_a.status_code == 201, r_a.text
            token_a = r_a.json()["access_token"]
            headers_a = {"Authorization": f"Bearer {token_a}"}

            r_b = await client.post("/api/v1/auth/register", json={
                "email": f"other_{ts}@pulserank.in",
                "password": "StrongPassword123",
                "full_name": "Other User"
            })
            assert r_b.status_code == 201
            headers_b = {"Authorization": f"Bearer {r_b.json()['access_token']}"}
            print("[PASS] 3. Auth registration & Bearer token issuance verified.")

            # 4. Interactive Onboarding Chatbot -> ClientBrief
            turns = [
                "B2B SEO automation, AEO readiness",
                "Indian SaaS founders and digital agencies",
                "authoritative and consultative",
                "qualified demo bookings"
            ]
            for msg in turns:
                rc = await client.post("/api/v1/onboarding/chat", json={"message": msg}, headers=headers_a)
                assert rc.status_code == 200, rc.text
            assert rc.json()["completed"] is True
            print("[PASS] 4. Interactive onboarding chatbot completed ClientBrief.")

            # 5. Single-URL Audit (202 Accepted + BackgroundTasks + Real HTML Crawl)
            ra = await client.post("/api/v1/audits", json={"url": target_url}, headers=headers_a)
            assert ra.status_code == 202, ra.text
            audit_id = ra.json()["audit_id"]

            audit_data = None
            for _ in range(25):
                rg = await client.get(f"/api/v1/audits/{audit_id}", headers=headers_a)
                assert rg.status_code == 200
                if rg.json()["status"] == "completed":
                    audit_data = rg.json()
                    break
                await asyncio.sleep(0.2)
            assert audit_data is not None, "Audit did not complete in time"
            assert audit_data["crawl_result"]["reachable"] is True
            assert audit_data["overall_score"] > 0
            assert len(audit_data["critical_errors"]) > 0
            print(f"[PASS] 5. Single-URL Audit #{audit_id} completed (Score: {audit_data['overall_score']}/100, Errors: {len(audit_data['critical_errors'])}).")

            # Verify User B cannot access User A's audit
            r_iso = await client.get(f"/api/v1/audits/{audit_id}", headers=headers_b)
            assert r_iso.status_code == 404, f"Isolation breach! {r_iso.status_code}"
            print("[PASS] 6. Per-user audit isolation verified (User B received 404).")

            # 6. On-Demand Optimization Trigger (202 Accepted, hydrated from snapshot)
            ro = await client.post(f"/api/v1/audits/{audit_id}/optimize", headers=headers_a)
            assert ro.status_code == 202, ro.text

            opt_done = None
            for _ in range(25):
                rg = await client.get(f"/api/v1/audits/{audit_id}", headers=headers_a)
                opts = rg.json().get("optimizations", [])
                if opts and opts[0]["status"] == "completed":
                    opt_done = opts[0]
                    break
                await asyncio.sleep(0.2)
            assert opt_done is not None, "Optimization did not complete in time"
            assert "recommended_json_ld" in opt_done["onpage_output"]
            assert "digital_pr_pitch_draft" in opt_done["offpage_output"]
            print("[PASS] 7. On-Demand On-Page & Off-Page Crew optimization completed from snapshot.")

            # 7. Continuous Monitors (Backlink, Content Decay, SERP Feature)
            for m_type in ["backlink", "content_decay", "serp_feature"]:
                rm = await client.post("/api/v1/monitors", json={"url": target_url, "monitor_type": m_type}, headers=headers_a)
                assert rm.status_code == 201, rm.text
                m_id = rm.json()["id"]
                rc = await client.post(f"/api/v1/monitors/{m_id}/check", headers=headers_a)
                assert rc.status_code == 200
                assert len(rc.json()["alerts"]) >= 1
            print("[PASS] 8. Continuous Monitors (backlink, content_decay, serp_feature) & alerts verified.")

            # 8. SMO Campaign (LinkedIn, IG, FB, YT, DraftPilot, Reddit, Quora)
            rs = await client.post("/api/v1/smo/campaigns", json={
                "source_url": target_url,
                "audit_id": audit_id,
                "topic": "AEO & Workflow Automation"
            }, headers=headers_a)
            assert rs.status_code == 202, rs.text

            smo_done = None
            for _ in range(25):
                rl = await client.get("/api/v1/smo/campaigns", headers=headers_a)
                assert rl.status_code == 200
                if rl.json() and rl.json()[0]["status"] == "completed":
                    smo_done = rl.json()[0]
                    break
                await asyncio.sleep(0.2)
            assert smo_done is not None
            assert len(smo_done["platform_assets"]) == 4  # linkedin, instagram, facebook, youtube
            assert len(smo_done["community_engagements"]) == 2  # reddit, quora
            assert len(smo_done["draftpilot_queue"]) == 6

            # Approve first DraftPilot item
            r_app = await client.patch(f"/api/v1/smo/campaigns/{smo_done['id']}/draftpilot/0", headers=headers_a)
            assert r_app.status_code == 200
            assert r_app.json()["item"]["status"] == "approved_and_scheduled"
            print("[PASS] 9. SMO (LI/IG/FB/YT), Community (Reddit/Quora) & DraftPilot approval verified.")

            # 9. INR Pricing (+18% GST), Subscription & Monthly ROI Report
            rp = await client.get("/api/v1/billing/plans")
            assert rp.status_code == 200
            plans = {p["tier"]: p for p in rp.json()}
            assert plans["starter"]["base_inr"] == 4999
            assert plans["growth"]["base_inr"] == 12999
            assert plans["agency_partner"]["base_inr"] == 29999

            rsub = await client.post("/api/v1/billing/subscribe", json={"tier": "growth", "gstin": "27AABCU9603R1ZM"}, headers=headers_a)
            assert rsub.status_code == 200
            assert rsub.json()["total_inr"] == 12999 + round(12999 * 0.18)

            rroi = await client.get("/api/v1/billing/roi-report", headers=headers_a)
            assert rroi.status_code == 200
            assert rroi.json()["metrics"]["audits_completed"] >= 1
            print("[PASS] 10. Indian INR pricing (+18% GST), subscription & Monthly ROI report verified.")

        print("\nALL 10 END-TO-END SYSTEM CHECKS PASSED SUCCESSFULLY.")
    finally:
        httpd.shutdown()


if __name__ == "__main__":
    asyncio.run(run_all_tests())
