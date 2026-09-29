import os
from pathlib import Path
from typing import List, Dict, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse, HTMLResponse
from pydantic import BaseModel
from dotenv import load_dotenv

# Load root .env
ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

app = FastAPI(title="Free AI Clinic Chatbot Service")

# Allow any website to embed the widget (CORS enabled)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

class MessageItem(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    history: Optional[List[MessageItem]] = []
    clinic_name: Optional[str] = "Al Dhabi Dental Centre"
    clinic_location: Optional[str] = "Abu Dhabi, UAE"
    whatsapp_number: Optional[str] = "+971547400174"

import json
from datetime import datetime

class AppointmentBooking(BaseModel):
    patient_name: str
    phone_number: str
    treatment: str
    date_time: str
    clinic_name: Optional[str] = "Al Dhabi Dental Centre"

APPOINTMENTS_FILE = Path(__file__).resolve().parent / "clinic_appointments.json"

DEFAULT_CLINIC_CONTEXT = """
You are 'Aura', a polite, empathetic, and professional AI Medical Receptionist for {clinic_name} in {clinic_location}.

Clinic Knowledge:
- Working Hours: Saturday to Thursday: 9:00 AM - 9:00 PM. Friday: 2:00 PM - 8:00 PM.
- Emergency Care: 24/7 emergency dental hotline available.
- Services Offered:
  * Teeth Whitening & Cleaning (from 350 AED)
  * Orthodontics & Invisible Aligners (Invisalign certified)
  * Dental Implants & Oral Surgery
  * Cosmetic Veneers & Smile Makeovers
  * Pediatric (Children) Dentistry
- Accepted Insurances: Daman, Thiqa, NextCare, AXA, MetLife, Oman Insurance.
- WhatsApp Direct Booking: {whatsapp_number}

CURRENTLY RESERVED SCHEDULE (SLOTS ALREADY TAKEN):
{existing_booked_slots}

CRITICAL ANTI-DOUBLE-BOOKING RULES:
1. Examine the CURRENTLY RESERVED SCHEDULE above before confirming ANY appointment.
2. If the patient requests a date/time that is already booked or overlaps with an existing appointment (for example, if another patient already has 10:00 AM):
   - You MUST NOT book the conflicting slot!
   - Inform the patient politely: "I see that [Requested Time] is already reserved for another patient."
   - Suggest 2 alternative open times (for example: "Would 10:30 AM or 11:30 AM work for you instead?").
   - DO NOT output the [BOOKING_SUCCESS: ...] tag for a conflicting slot!
3. Only when the patient agrees to an OPEN, non-conflicting time AND you have all 4 details (Full Name, Phone Number, Treatment, and Date/Time), output:
   [BOOKING_SUCCESS: PatientName | PhoneNumber | Treatment | DateTime]

Appointment Booking Protocol:
1. Politely ask for any missing details (Name, Phone, Treatment, Preferred Date and Time).
2. Check for slot conflicts.
3. Lock in only available slots.
"""

@app.get("/")
def home():
    return {
        "status": "online",
        "service": "AI Chatbot Backend",
        "model": GEMINI_MODEL,
        "ready": bool(GEMINI_API_KEY)
    }

@app.get("/widget.js")
def get_widget():
    """Serves the embeddable JavaScript chat bubble."""
    widget_path = Path(__file__).parent / "static" / "widget.js"
    if not widget_path.exists():
        raise HTTPException(status_code=404, detail="Widget script not found")
    return FileResponse(widget_path, media_type="application/javascript")

@app.get("/demo", response_class=HTMLResponse)
def get_demo_page():
    """Serves the live interactive clinic demo website for client preview."""
    demo_html_content = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Al Dhabi Dental & Orthodontic Centre | Live AI Preview</title>
<style>
  * { box-sizing: border-box; }
  body {
    margin: 0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    color: #1e293b;
    background: #f8fafc;
  }
  header {
    background: #ffffff;
    padding: 16px 24px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid #e2e8f0;
    flex-wrap: wrap;
    gap: 12px;
  }
  .logo {
    font-size: 20px;
    font-weight: 800;
    color: #0284c7;
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .badge-demo {
    background: #e0f2fe;
    color: #0369a1;
    font-size: 11px;
    font-weight: 700;
    padding: 4px 8px;
    border-radius: 12px;
  }
  .nav-btn {
    background: #0284c7;
    color: #ffffff;
    padding: 8px 16px;
    border-radius: 8px;
    text-decoration: none;
    font-size: 13px;
    font-weight: 600;
  }
  .hero {
    padding: 48px 20px;
    max-width: 900px;
    margin: 0 auto;
    text-align: center;
  }
  .hero h1 {
    font-size: 32px;
    color: #0f172a;
    margin-bottom: 14px;
  }
  .hero p {
    font-size: 16px;
    color: #64748b;
    max-width: 650px;
    margin: 0 auto 24px;
    line-height: 1.6;
  }
  .cta-bubble-hint {
    display: inline-block;
    background: #f0fdf4;
    border: 1px solid #bbf7d0;
    color: #166534;
    padding: 10px 18px;
    border-radius: 30px;
    font-size: 14px;
    font-weight: 600;
    box-shadow: 0 2px 6px rgba(22, 101, 52, 0.1);
  }
  .services {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
    gap: 20px;
    max-width: 1000px;
    margin: 20px auto 60px;
    padding: 0 20px;
  }
  .service-card {
    background: #ffffff;
    padding: 24px;
    border-radius: 12px;
    border: 1px solid #e2e8f0;
    box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);
  }
  .service-card h3 {
    margin-top: 0;
    color: #0369a1;
    font-size: 18px;
  }
  .service-card p {
    color: #64748b;
    font-size: 14px;
    line-height: 1.5;
  }
</style>
</head>
<body>

<header>
  <div class="logo">
    &#129463; Al Dhabi Dental Centre
    <span class="badge-demo">24/7 AI Reception Preview</span>
  </div>
  <a href="/appointments" class="nav-btn" target="_blank">&#128203; View Reception Dashboard</a>
</header>

<div class="hero">
  <h1>World-Class Dental Care in Mussafah, Abu Dhabi</h1>
  <p>Providing advanced cosmetic dentistry, orthodontic care, and emergency dental solutions with over 35 years of clinical excellence.</p>
  <div class="cta-bubble-hint">
    &#128071; Tap the blue chat bubble at the bottom-right to test your 24/7 AI Receptionist!
  </div>
</div>

<div class="services">
  <div class="service-card">
    <h3>&#129463; Orthodontics & Invisalign</h3>
    <p>Straighten your smile discreetly with certified clear aligners and gentle specialist treatments.</p>
  </div>
  <div class="service-card">
    <h3>&#10024; Laser Teeth Whitening</h3>
    <p>In-clinic laser whitening sessions that brighten your smile up to 8 shades in just 45 minutes.</p>
  </div>
  <div class="service-card">
    <h3>&#128297; Dental Implants & Surgery</h3>
    <p>Permanent, natural-looking tooth replacements utilizing 3D digital imaging guidance.</p>
  </div>
</div>

<!-- LIVE EMBEDDABLE SCRIPT -->
<script 
  src="/widget.js" 
  data-clinic="Al Dhabi Dental Centre" 
  data-whatsapp="+971588360378">
</script>

</body>
</html>"""
    return HTMLResponse(content=demo_html_content, media_type="text/html; charset=utf-8")

@app.post("/chat")
def chat_endpoint(req: ChatRequest):
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY not configured in .env")

    existing_appts = get_appointments_list()
    booked_slots_list = [f"- {a.get('date_time', '')} ({a.get('treatment', '')})" for a in existing_appts if a.get('date_time')]
    booked_slots_str = "\n".join(booked_slots_list) if booked_slots_list else "None. All slots currently open."

    clean_whatsapp = "".join(filter(str.isdigit, req.whatsapp_number or ""))
    system_prompt = DEFAULT_CLINIC_CONTEXT.format(
        clinic_name=req.clinic_name,
        clinic_location=req.clinic_location,
        whatsapp_number=req.whatsapp_number,
        clean_whatsapp=clean_whatsapp,
        existing_booked_slots=booked_slots_str
    )

    # Build conversation context
    conversation_text = ""
    for msg in req.history[-6:]:
        speaker = "Patient" if msg.role == "user" else "Assistant"
        conversation_text += f"{speaker}: {msg.content}\n"

    full_prompt = f"{conversation_text}Patient: {req.message}\nAssistant:"

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=GEMINI_API_KEY)
        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.6,
            max_output_tokens=350,
        )

        # Call Gemini
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=full_prompt,
            config=config,
        )

        reply_text = response.text.strip() if response and response.text else "Thank you for reaching out!"
        
        # Check if an appointment was successfully finalized
        booking_data = None
        if "[BOOKING_SUCCESS:" in reply_text:
            try:
                import re
                match = re.search(r'\[BOOKING_SUCCESS:\s*([^\|]+)\|\s*([^\|]+)\|\s*([^\|]+)\|\s*([^\]]+)\]', reply_text)
                if match:
                    p_name, p_phone, p_treatment, p_time = [g.strip() for g in match.groups()]
                    booking_id = f"AD-{datetime.now().strftime('%m%d%H%M')}"
                    booking_data = {
                        "booking_id": booking_id,
                        "patient_name": p_name,
                        "phone_number": p_phone,
                        "treatment": p_treatment,
                        "date_time": p_time,
                        "clinic_name": req.clinic_name,
                        "booked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    
                    # Save to JSON database
                    APPOINTMENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
                    existing = []
                    if APPOINTMENTS_FILE.exists():
                        try:
                            existing = json.loads(APPOINTMENTS_FILE.read_text(encoding="utf-8"))
                        except Exception:
                            existing = []
                    existing.append(booking_data)
                    APPOINTMENTS_FILE.write_text(json.dumps(existing, indent=2), encoding="utf-8")
            except Exception as save_err:
                print(f"Error saving appointment: {save_err}")

        return {"reply": reply_text, "booking": booking_data}
    except Exception as e:
        return {
            "reply": f"Thank you for contacting {req.clinic_name}. Our front desk is available directly on WhatsApp at {req.whatsapp_number}."
        }

from fastapi.responses import HTMLResponse

def get_appointments_list():
    if APPOINTMENTS_FILE.exists():
        try:
            return json.loads(APPOINTMENTS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []

@app.get("/api/appointments")
def api_appointments():
    """Raw JSON endpoint for API or integrations."""
    return get_appointments_list()

@app.get("/appointments", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
def appointments_dashboard(format: Optional[str] = None):
    """Clinic Receptionist Dashboard to view and manage all AI bookings."""
    appointments = get_appointments_list()
    
    if format == "json":
        import json as py_json
        return PlainTextResponse(py_json.dumps(appointments, indent=2), media_type="application/json")

    total_bookings = len(appointments)
    
    import collections, re
    def normalize_time(t_str):
        clean = re.sub(r'[^a-zA-Z0-9]', '', (t_str or '').lower())
        return clean.replace("at", "")

    time_counts = collections.Counter([normalize_time(a.get("date_time", "")) for a in appointments if a.get("date_time")])
    has_conflicts = any(count > 1 for norm_t, count in time_counts.items() if norm_t)

    rows_html = ""
    mobile_cards_html = ""
    for appt in reversed(appointments):
        bid = appt.get("booking_id", "N/A")
        pname = appt.get("patient_name", "Anonymous")
        phone = appt.get("phone_number", "")
        clean_phone = "".join(filter(str.isdigit, phone))
        treatment = appt.get("treatment", "General Consultation")
        dtime = appt.get("date_time", "Not specified")
        booked_at = appt.get("booked_at", "")
        
        is_conflict = time_counts.get(normalize_time(dtime), 0) > 1
        if is_conflict:
            status_html = '<span class="badge badge-conflict">&#9888; Overlap Conflict</span>'
        else:
            status_html = '<span class="badge badge-confirmed">Confirmed</span>'

        wa_link = f"https://wa.me/{clean_phone}?text=Hello%20{pname},%20confirming%20your%20appointment%20at%20Al%20Dhabi%20Dental%20Centre!"
        
        # Desktop table row
        rows_html += f"""
        <tr class="{'row-conflict' if is_conflict else ''}">
          <td><span class="badge badge-id">{bid}</span></td>
          <td><strong>{pname}</strong></td>
          <td><a href="tel:{clean_phone}" style="color:#0369a1; text-decoration:none; font-weight:600;">{phone}</a></td>
          <td><span class="badge badge-treatment">{treatment}</span></td>
          <td><strong>{dtime}</strong></td>
          <td class="text-muted">{booked_at}</td>
          <td>{status_html}</td>
          <td>
            <a href="{wa_link}" target="_blank" class="btn-wa">&#128172; WhatsApp</a>
          </td>
        </tr>
        """

        # Mobile card view
        mobile_cards_html += f"""
        <div class="patient-card {'row-conflict' if is_conflict else ''}">
          <div class="card-head">
            <span class="badge badge-id">{bid}</span>
            {status_html}
          </div>
          <div class="card-patient-name">{pname}</div>
          <div class="card-meta">
            <div class="meta-row">
              <span class="meta-label">&#128197; Date & Time</span>
              <span class="meta-val meta-time">{dtime}</span>
            </div>
            <div class="meta-row">
              <span class="meta-label">&#129463; Service</span>
              <span class="meta-val">{treatment}</span>
            </div>
            <div class="meta-row">
              <span class="meta-label">&#128222; Phone</span>
              <span class="meta-val"><a href="tel:{clean_phone}" style="color:#0284c7; font-weight:700; text-decoration:none;">{phone}</a></span>
            </div>
            <div class="meta-row">
              <span class="meta-label">&#9201; Booked</span>
              <span class="meta-val text-muted">{booked_at}</span>
            </div>
          </div>
          <a href="{wa_link}" target="_blank" class="btn-wa-card">
            &#128172; Open WhatsApp Confirmation
          </a>
        </div>
        """
        
    if not rows_html:
        rows_html = "<tr><td colspan='8' style='text-align:center; padding:32px; color:#64748b;'>No appointments booked yet. The AI is waiting for incoming patients.</td></tr>"
        mobile_cards_html = "<div style='text-align:center; padding:32px; color:#64748b; background:#fff; border-radius:12px;'>No appointments booked yet. The AI is waiting for incoming patients.</div>"

    conflict_banner_html = ""
    if has_conflicts:
        conflict_banner_html = """
        <div class="alert-conflict">
          <div class="alert-icon">&#9888;</div>
          <div>
            <strong>Schedule Overlap Detected:</strong> Multiple patients booked the same time slot (highlighted in red). The AI will automatically prevent future overlapping bookings. Front desk follow-up recommended.
          </div>
        </div>
        """

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>Al Dhabi Dental Centre &mdash; AI Reception Dashboard</title>
<style>
  * {{
    box-sizing: border-box;
  }}
  body {{
    margin: 0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    background: #f1f5f9;
    color: #1e293b;
    -webkit-font-smoothing: antialiased;
  }}
  .navbar {{
    background: linear-gradient(135deg, #0284c7, #0369a1);
    color: #ffffff;
    padding: 16px 28px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    box-shadow: 0 4px 12px rgba(2, 132, 199, 0.2);
    flex-wrap: wrap;
    gap: 12px;
  }}
  .navbar h1 {{
    margin: 0;
    font-size: 18px;
    font-weight: 700;
  }}
  .navbar-status {{
    font-size: 12px;
    background: rgba(255, 255, 255, 0.2);
    padding: 6px 12px;
    border-radius: 20px;
    font-weight: 500;
  }}
  .container {{
    max-width: 1200px;
    margin: 24px auto;
    padding: 0 20px;
  }}
  .stats-grid {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
    margin-bottom: 24px;
  }}
  .stat-card {{
    background: #ffffff;
    padding: 20px;
    border-radius: 12px;
    border: 1px solid #e2e8f0;
    box-shadow: 0 2px 4px rgba(0,0,0,0.03);
  }}
  .stat-card-title {{
    font-size: 12px;
    font-weight: 600;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 6px;
  }}
  .stat-card-val {{
    font-size: 26px;
    font-weight: 800;
    color: #0f172a;
  }}
  .table-card {{
    background: #ffffff;
    border-radius: 14px;
    border: 1px solid #e2e8f0;
    box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);
    overflow: hidden;
  }}
  .table-header {{
    padding: 16px 20px;
    border-bottom: 1px solid #e2e8f0;
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: #ffffff;
  }}
  .table-header h2 {{
    margin: 0;
    font-size: 16px;
    color: #1e293b;
    font-weight: 700;
  }}
  .table-scroll-container {{
    width: 100%;
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    text-align: left;
    font-size: 14px;
    min-width: 750px;
  }}
  th {{
    background: #f8fafc;
    color: #475569;
    font-weight: 600;
    padding: 12px 18px;
    border-bottom: 1px solid #e2e8f0;
    white-space: nowrap;
  }}
  td {{
    padding: 14px 18px;
    border-bottom: 1px solid #f1f5f9;
    vertical-align: middle;
  }}
  tr:hover {{
    background: #f8fafc;
  }}
  .badge {{
    display: inline-block;
    padding: 4px 10px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 600;
    white-space: nowrap;
  }}
  .badge-id {{
    background: #e0f2fe;
    color: #0369a1;
  }}
  .badge-treatment {{
    background: #fef3c7;
    color: #92400e;
  }}
  .badge-confirmed {{
    background: #dcfce7;
    color: #166534;
  }}
  .badge-conflict {{
    background: #fee2e2;
    color: #991b1b;
    border: 1px solid #f87171;
    font-weight: 700;
  }}
  .row-conflict {{
    background: #fff1f2 !important;
  }}
  .alert-conflict {{
    background: #fffbeb;
    border-left: 5px solid #f59e0b;
    padding: 14px 18px;
    border-radius: 8px;
    margin-bottom: 20px;
    display: flex;
    align-items: center;
    gap: 12px;
    color: #92400e;
    font-size: 14px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
  }}
  .alert-icon {{
    font-size: 22px;
  }}
  .btn-wa {{
    background: #25D366;
    color: #ffffff !important;
    text-decoration: none;
    padding: 6px 12px;
    border-radius: 8px;
    font-size: 12px;
    font-weight: 600;
    display: inline-flex;
    align-items: center;
    gap: 4px;
    box-shadow: 0 2px 4px rgba(37,211,102,0.2);
    white-space: nowrap;
  }}
  .btn-wa:hover {{
    background: #20ba5a;
  }}
  .text-muted {{
    color: #94a3b8;
    font-size: 12px;
  }}

  /* Mobile Card View styles */
  .mobile-cards-view {{
    display: none;
    padding: 14px;
    gap: 14px;
    flex-direction: column;
    background: #f8fafc;
  }}
  .patient-card {{
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 16px;
    box-shadow: 0 2px 6px rgba(0,0,0,0.04);
    display: flex;
    flex-direction: column;
    gap: 10px;
  }}
  .card-head {{
    display: flex;
    justify-content: space-between;
    align-items: center;
  }}
  .card-patient-name {{
    font-size: 18px;
    font-weight: 800;
    color: #0f172a;
  }}
  .card-meta {{
    display: flex;
    flex-direction: column;
    gap: 6px;
    font-size: 13px;
    background: #f8fafc;
    padding: 10px 12px;
    border-radius: 8px;
    border: 1px solid #f1f5f9;
  }}
  .meta-row {{
    display: flex;
    justify-content: space-between;
    align-items: center;
  }}
  .meta-label {{
    color: #64748b;
    font-weight: 500;
  }}
  .meta-val {{
    color: #1e293b;
    font-weight: 600;
  }}
  .meta-time {{
    color: #0284c7;
    font-weight: 700;
  }}
  .btn-wa-card {{
    background: #25D366;
    color: #ffffff !important;
    text-decoration: none;
    padding: 12px;
    border-radius: 10px;
    font-size: 14px;
    font-weight: 700;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    box-shadow: 0 4px 10px rgba(37,211,102,0.25);
    margin-top: 4px;
  }}

  /* MEDIA QUERIES FOR MOBILE */
  @media (max-width: 768px) {{
    .navbar {{
      padding: 14px 16px;
      flex-direction: column;
      align-items: flex-start;
      gap: 8px;
    }}
    .navbar h1 {{
      font-size: 16px;
    }}
    .navbar-status {{
      align-self: flex-start;
    }}
    .container {{
      margin: 14px auto;
      padding: 0 12px;
    }}
    .stats-grid {{
      grid-template-columns: 1fr;
      gap: 10px;
      margin-bottom: 16px;
    }}
    .stat-card {{
      padding: 14px 16px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}
    .stat-card-title {{
      margin-bottom: 0;
      font-size: 11px;
    }}
    .stat-card-val {{
      font-size: 20px;
    }}
    .desktop-table-view {{
      display: none;
    }}
    .mobile-cards-view {{
      display: flex;
    }}
  }}
</style>
</head>
<body>

<div class="navbar">
  <h1>&#129463; Al Dhabi Dental Centre &mdash; Reception Dashboard</h1>
  <div class="navbar-status">&#9679; 24/7 AI Receptionist: Active</div>
</div>

<div class="container">
  {conflict_banner_html}
  <div class="stats-grid">
    <div class="stat-card">
      <div class="stat-card-title">Total Bookings Captured</div>
      <div class="stat-card-val">{total_bookings}</div>
    </div>
    <div class="stat-card">
      <div class="stat-card-title">Location</div>
      <div class="stat-card-val" style="font-size: 16px; font-weight: 700;">Mussafah, Abu Dhabi</div>
    </div>
    <div class="stat-card">
      <div class="stat-card-title">AI Status</div>
      <div class="stat-card-val" style="font-size: 16px; color: #16a34a; font-weight: 700;">100% Online</div>
    </div>
  </div>

  <div class="table-card">
    <div class="table-header">
      <h2>Recent Patient Bookings (Live Schedule)</h2>
      <a href="/appointments" style="font-size: 13px; color: #0284c7; text-decoration: none; font-weight: 600;">&#128260; Refresh Table</a>
    </div>

    <!-- Desktop Table View -->
    <div class="desktop-table-view table-scroll-container">
      <table>
        <thead>
          <tr>
            <th>Booking ID</th>
            <th>Patient Name</th>
            <th>Phone</th>
            <th>Treatment</th>
            <th>Requested Date & Time</th>
            <th>Time Booked</th>
            <th>Status</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          {rows_html}
        </tbody>
      </table>
    </div>

    <!-- Mobile Native Cards View -->
    <div class="mobile-cards-view">
      {mobile_cards_html}
    </div>
  </div>
</div>

</body>
</html>"""
    return HTMLResponse(content=html_content, media_type="text/html; charset=utf-8")


