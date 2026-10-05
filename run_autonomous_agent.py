#!/usr/bin/env python3
"""
Autonomous AI Sales Agent — UAE Luxury Real Estate
Fully automated client discovery, personalized demo creation, multi-step messaging, and follow-up engine.

Usage:
  python run_autonomous_agent.py --status             # View live pipeline & follow-up status
  python run_autonomous_agent.py --discover           # Autonomously hunt fresh UAE brokers with Gemini
  python run_autonomous_agent.py --followups          # Check and flag 24h / 48h overdue follow-ups
  python run_autonomous_agent.py --dispatch-browser   # Automatically open WhatsApp Web for next lead
  python run_autonomous_agent.py --daemon             # Run continuous autonomous background loop
"""

import os
import sys
import time
import json
import argparse
import webbrowser
import urllib.parse
from pathlib import Path
from datetime import datetime, timedelta

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT_DIR = Path(__file__).resolve().parent
CRM_FILE_ENG = ROOT_DIR / "outputs" / "outreach_crm.json"
CRM_FILE_CLONE = ROOT_DIR.parent / "dental_ai_bot_clone" / "outreach_crm.json"

def get_crm_path() -> Path:
    if CRM_FILE_ENG.exists():
        return CRM_FILE_ENG
    if CRM_FILE_CLONE.exists():
        return CRM_FILE_CLONE
    return CRM_FILE_ENG

def load_crm():
    path = get_crm_path()
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []

def save_crm(leads):
    content = json.dumps(leads, indent=2, ensure_ascii=False)
    for p in [CRM_FILE_ENG, CRM_FILE_CLONE]:
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
        except Exception:
            pass

def print_banner():
    print("=" * 75)
    print(" 🤖 AUTONOMOUS AI SALES AGENT — UAE REAL ESTATE ACQUISITION & FOLLOW-UPS")
    print(" Target: Dubai & Abu Dhabi Luxury Property Brokers | Deal Size: 1,500 AED")
    print("=" * 75)

def show_status():
    leads = load_crm()
    total = len(leads)
    discovered = len([l for l in leads if l.get("status") == "DISCOVERED"])
    contacted = len([l for l in leads if l.get("status") in ["CONTACTED", "FOLLOWUP_1_SENT", "FOLLOWUP_2_SENT"]])
    f1_due = len([l for l in leads if l.get("status") == "FOLLOWUP_1_DUE"])
    f2_due = len([l for l in leads if l.get("status") == "FOLLOWUP_2_DUE"])
    replied = len([l for l in leads if l.get("status") == "REPLIED"])
    won = len([l for l in leads if l.get("status") == "WON"])
    pipeline_val = (total - won) * 1500
    won_val = won * 1500

    print_banner()
    print(f"📊 PIPELINE EXECUTIVE SUMMARY:")
    print(f"  • Total Prospects in Database:   {total}")
    print(f"  • Ready for Initial Pitch:       {discovered}")
    print(f"  • In Active Conversation:        {contacted}")
    print(f"  • 24h Follow-Ups Due:            {f1_due}")
    print(f"  • 48h Breakup Follow-Ups Due:    {f2_due}")
    print(f"  • Positive Replies Received:     {replied}")
    print(f"  • Closed Deals Won:              {won} ({won_val:,} AED Closed)")
    print(f"  • Active Pipeline Value:         {pipeline_val:,} AED")
    print("-" * 75)
    print(f"{'#':<3} {'AGENCY':<32} {'BROKER':<20} {'PHONE':<17} {'STATUS':<15}")
    print("-" * 75)
    for i, l in enumerate(leads, 1):
        ag = l.get("agency_name", "")[:30]
        br = l.get("broker_name", "")[:18]
        ph = l.get("phone", "")[:15]
        st = l.get("status", "DISCOVERED")
        print(f"{i:<3} {ag:<32} {br:<20} {ph:<17} {st:<15}")
    print("=" * 75)
    print("💡 Command Center Web URL: https://apex-luxury-ai.onrender.com/crm")

def discover_more_brokers():
    print_banner()
    print("🔍 Hunting for new luxury UAE real estate brokers and boutique agencies...")
    try:
        from agents.auto_sales_agent import AutoSalesAgent
        agent = AutoSalesAgent()
        new_leads = agent.discover_uae_brokers()
        print(f"✅ Discovery Complete! Added {len(new_leads)} new verified broker leads.")
        for l in new_leads:
            print(f"   + {l.get('agency_name')} ({l.get('broker_name')}) -> {l.get('phone')}")
    except Exception as e:
        print(f"❌ Error during discovery: {e}")

def check_followups():
    print_banner()
    print("⏱️ Checking for overdue 24h and 48h follow-ups across CRM pipeline...")
    leads = load_crm()
    now = datetime.now()
    flagged_count = 0

    for l in leads:
        status = l.get("status")
        last_dt_str = l.get("last_contacted_at")
        if not last_dt_str:
            continue

        try:
            last_dt = datetime.strptime(last_dt_str, "%Y-%m-%d %H:%M:%S")
            hours_elapsed = (now - last_dt).total_seconds() / 3600

            if status == "CONTACTED" and hours_elapsed >= 24:
                l["status"] = "FOLLOWUP_1_DUE"
                flagged_count += 1
                print(f"   ⚠️ 24h Follow-up Due for {l.get('agency_name')} ({l.get('broker_name')}) — Elapsed: {hours_elapsed:.1f} hrs")
            elif status == "FOLLOWUP_1_SENT" and hours_elapsed >= 48:
                l["status"] = "FOLLOWUP_2_DUE"
                flagged_count += 1
                print(f"   ⚠️ 48h Breakup Due for {l.get('agency_name')} ({l.get('broker_name')}) — Elapsed: {hours_elapsed:.1f} hrs")
        except Exception:
            pass

    if flagged_count > 0:
        save_crm(leads)
        print(f"\n✅ Updated CRM! {flagged_count} lead(s) flagged for immediate follow-up.")
    else:
        print("✅ All follow-ups are up to date! Zero overdue leads.")

def dispatch_next_lead(auto_open=True):
    print_banner()
    leads = load_crm()
    
    # Prioritize: 1) Follow-up 1 due, 2) Follow-up 2 due, 3) Initial discovery
    target = None
    msg_type = "initial"
    
    for l in leads:
        if l.get("status") == "FOLLOWUP_1_DUE":
            target = l
            msg_type = "followup1"
            break

    if not target:
        for l in leads:
            if l.get("status") == "FOLLOWUP_2_DUE":
                target = l
                msg_type = "followup2"
                break

    if not target:
        for l in leads:
            if l.get("status") == "DISCOVERED":
                target = l
                msg_type = "initial"
                break

    if not target:
        print("🎉 No pending outreach leads found in CRM queue!")
        return

    agency = target.get("agency_name")
    broker = target.get("broker_name")
    phone = target.get("phone")
    clean_p = target.get("phone_clean") or "".join(filter(str.isdigit, phone))
    msg = target.get("messages", {}).get(msg_type, "")

    print(f"🎯 Target Selected: {agency} — {broker}")
    print(f"📱 Phone/WhatsApp:  {phone}")
    print(f"📩 Outreach Stage:   {msg_type.upper()}")
    print("-" * 75)
    print("PROPOSED MESSAGE:")
    print(msg)
    print("-" * 75)

    wa_url = f"https://wa.me/{clean_p}?text={urllib.parse.quote(msg)}"
    print(f"🔗 Direct WhatsApp Link: {wa_url}\n")

    if auto_open:
        print("🚀 Opening WhatsApp Web directly in your browser...")
        try:
            webbrowser.open(wa_url)
            # Update state
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if msg_type == "initial":
                target["status"] = "CONTACTED"
                target["last_contacted_at"] = now_str
                target["next_followup_at"] = (datetime.now() + timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
            elif msg_type == "followup1":
                target["status"] = "FOLLOWUP_1_SENT"
                target["last_contacted_at"] = now_str
                target["next_followup_at"] = (datetime.now() + timedelta(hours=48)).strftime("%Y-%m-%d %H:%M:%S")
            elif msg_type == "followup2":
                target["status"] = "FOLLOWUP_2_SENT"
                target["last_contacted_at"] = now_str

            save_crm(leads)
            print(f"✅ Lead status updated to {target['status']} and next follow-up timer scheduled!")
        except Exception as e:
            print(f"Could not open browser: {e}")

def run_daemon(poll_interval_seconds=1800):
    print_banner()
    print(f"🛡️ AUTONOMOUS DAEMON ACTIVE — Checking pipeline every {poll_interval_seconds//60} minutes.")
    print("Press Ctrl+C to stop.\n")
    try:
        while True:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Running autonomous cycle...")
            check_followups()
            leads = load_crm()
            discovered = [l for l in leads if l.get("status") == "DISCOVERED"]
            if len(discovered) < 3:
                print("⚠️ Low uncontacted pipeline! Triggering autonomous broker hunter...")
                discover_more_brokers()
            print(f"Sleeping for {poll_interval_seconds//60} minutes...\n")
            time.sleep(poll_interval_seconds)
    except KeyboardInterrupt:
        print("\n🛑 Daemon stopped gracefully.")

def main():
    parser = argparse.ArgumentParser(description="Autonomous Sales Agent for UAE Real Estate")
    parser.add_argument("--status", action="store_true", help="Show pipeline and lead stages")
    parser.add_argument("--discover", action="store_true", help="Hunt fresh UAE brokers using Gemini")
    parser.add_argument("--followups", action="store_true", help="Check and flag overdue 24h/48h follow-ups")
    parser.add_argument("--dispatch-browser", action="store_true", help="Open WhatsApp Web for next lead in queue")
    parser.add_argument("--daemon", action="store_true", help="Run background monitor loop")

    args = parser.parse_args()

    if args.status:
        show_status()
    elif args.discover:
        discover_more_brokers()
    elif args.followups:
        check_followups()
    elif args.dispatch_browser:
        dispatch_next_lead(auto_open=True)
    elif args.daemon:
        run_daemon()
    else:
        show_status()

if __name__ == "__main__":
    main()
