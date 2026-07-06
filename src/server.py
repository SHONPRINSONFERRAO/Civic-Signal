#!/usr/bin/env python3
import csv
import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib import error, request


SRC_DIR = Path(__file__).parent
PROJECT_ROOT = SRC_DIR.parent
WEB_DIR = PROJECT_ROOT / "web"
DATA_DIR = PROJECT_ROOT / "data"


CATEGORY_RULES = {
    "Roads & Traffic": [
        "pothole",
        "road",
        "traffic",
        "signal",
        "crosswalk",
        "intersection",
        "parking",
        "congestion",
        "bus",
        "sidewalk",
    ],
    "Sanitation": ["trash", "garbage", "waste", "bin", "litter", "overflow", "dump"],
    "Lighting & Utilities": ["light", "streetlight", "power", "electric", "water", "leak", "outage"],
    "Public Safety": ["unsafe", "crime", "theft", "assault", "emergency", "hazard", "fire"],
    "Parks & Public Space": ["park", "playground", "bench", "green", "tree", "graffiti"],
    "Accessibility": ["wheelchair", "ramp", "accessible", "accessibility", "elevator"],
}

URGENT_TERMS = {
    "critical": 95,
    "emergency": 100,
    "injury": 92,
    "unsafe": 88,
    "fire": 100,
    "flood": 96,
    "outage": 85,
    "hospital": 90,
    "elderly": 82,
    "school": 80,
    "children": 82,
    "blocked": 78,
    "leak": 76,
    "dark": 74,
    "accident": 90,
}

POSITIVE_TERMS = {"fixed", "resolved", "good", "thanks", "appreciate", "clean"}
NEGATIVE_TERMS = {"bad", "unsafe", "broken", "angry", "frustrated", "dangerous", "delay"}

DEPARTMENT_MAP = {
    "Roads & Traffic": "Transportation Operations",
    "Sanitation": "Waste Management",
    "Lighting & Utilities": "Public Utilities",
    "Public Safety": "Community Safety",
    "Parks & Public Space": "Parks Department",
    "Accessibility": "Accessibility Office",
    "General": "City Operations Center",
}

VERTEX_TOKEN_URL = "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token"


def load_sample_records():
    with (DATA_DIR / "samples" / "citizen_complaints.csv").open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def normalize_record(raw, index):
    return {
        "id": raw.get("id") or f"issue-{index + 1}",
        "timestamp": raw.get("timestamp", "").strip(),
        "area": raw.get("area", "Unknown").strip() or "Unknown",
        "category_raw": raw.get("category_raw", "").strip(),
        "description": raw.get("description", "").strip(),
        "source": raw.get("source", "citizen_portal").strip() or "citizen_portal",
        "status": raw.get("status", "open").strip() or "open",
    }


def classify_category(text):
    lowered = text.lower()
    for category, keywords in CATEGORY_RULES.items():
        if any(word in lowered for word in keywords):
            return category
    return "General"


def detect_sentiment(text):
    lowered = text.lower()
    score = 0
    for word in POSITIVE_TERMS:
        if word in lowered:
            score += 1
    for word in NEGATIVE_TERMS:
        if word in lowered:
            score -= 1
    if score > 0:
        return "positive"
    if score < 0:
        return "negative"
    return "neutral"


def detect_urgency(text):
    lowered = text.lower()
    urgency = 35
    reasons = []
    for word, value in URGENT_TERMS.items():
        if word in lowered:
            urgency = max(urgency, value)
            reasons.append(word)
    if "days" in lowered or "weeks" in lowered:
        urgency = max(urgency, 62)
    return urgency, reasons


def summarize_text(text, limit=110):
    clean = re.sub(r"\s+", " ", text).strip()
    if len(clean) <= limit:
        return clean
    return clean[: limit - 1].rstrip() + "..."


def recommend_action(category, urgency, area):
    if category == "Public Safety":
        return f"Dispatch a field safety review in {area} and escalate unresolved hazards."
    if category == "Lighting & Utilities":
        return f"Open a utility work order for {area} and prioritize repairs within 24 hours."
    if category == "Sanitation":
        return f"Increase pickup frequency in {area} and inspect overflow hotspots."
    if category == "Roads & Traffic":
        return f"Schedule road or signal maintenance in {area} and notify commuters of expected delays."
    if category == "Accessibility":
        return f"Assign an accessibility inspection team to {area} and track remediation deadlines."
    if urgency >= 80:
        return f"Escalate to the city operations center for urgent review in {area}."
    return f"Route this issue to {DEPARTMENT_MAP.get(category, 'City Operations Center')} for standard follow-up."


def analyze_records(records):
    analyzed = []
    for index, raw in enumerate(records):
        record = normalize_record(raw, index)
        description = record["description"]
        category = classify_category(" ".join([record["category_raw"], description]))
        urgency, urgency_reasons = detect_urgency(description)
        sentiment = detect_sentiment(description)
        analyzed.append(
            {
                **record,
                "ai_category": category,
                "urgency_score": urgency,
                "sentiment": sentiment,
                "department": DEPARTMENT_MAP.get(category, "City Operations Center"),
                "summary": summarize_text(description),
                "recommended_action": recommend_action(category, urgency, record["area"]),
                "reasoning": (
                    f"Tagged as {category} because of complaint keywords; "
                    f"urgency raised by {', '.join(urgency_reasons) if urgency_reasons else 'baseline service impact'}."
                ),
            }
        )
    return analyzed


def build_overview(records):
    if not records:
        return {
            "kpis": {"totalIssues": 0, "urgentIssues": 0, "topCategory": "N/A", "topArea": "N/A"},
            "categoryCounts": [],
            "areaCounts": [],
            "urgentRecords": [],
            "recentRecords": [],
            "insights": {
                "summary": "Upload or load a dataset to begin analysis.",
                "anomalies": [],
                "recommendedActions": [],
            },
        }

    category_counts = Counter(record["ai_category"] for record in records)
    area_counts = Counter(record["area"] for record in records)
    area_priority = defaultdict(int)
    urgent_records = sorted(records, key=lambda item: item["urgency_score"], reverse=True)[:5]
    recent_records = sorted(records, key=lambda item: item["timestamp"], reverse=True)[:8]

    top_category = category_counts.most_common(1)[0][0]
    high_urgency = [item for item in records if item["urgency_score"] >= 80]

    area_by_category = defaultdict(Counter)
    for item in records:
        area_by_category[item["area"]][item["ai_category"]] += 1
        area_priority[item["area"]] += item["urgency_score"]

    top_area = max(area_priority.items(), key=lambda pair: pair[1])[0]

    anomaly_area = None
    anomaly_count = 0
    for area, counts in area_by_category.items():
        local_count = sum(counts.values())
        if local_count > anomaly_count:
            anomaly_area = area
            anomaly_count = local_count

    summary = (
        f"{len(records)} issues analyzed. {len(high_urgency)} need urgent attention. "
        f"{top_category} is the dominant issue type, with {top_area} showing the highest concentration."
    )

    anomalies = []
    if anomaly_area:
        anomalies.append(
            f"{anomaly_area} is the current hotspot with {anomaly_count} reported issues across multiple service categories."
        )
    if high_urgency:
        anomalies.append(
            f"{len(high_urgency)} complaints were marked urgent because they include safety, outage, flooding, or blocked-access signals."
        )

    recommendations = []
    for category, _count in category_counts.most_common(3):
        sample = next(item for item in records if item["ai_category"] == category)
        recommendations.append(sample["recommended_action"])

    return {
        "kpis": {
            "totalIssues": len(records),
            "urgentIssues": len(high_urgency),
            "topCategory": top_category,
            "topArea": top_area,
        },
        "categoryCounts": [{"label": label, "value": value} for label, value in category_counts.most_common()],
        "areaCounts": [{"label": label, "value": value} for label, value in area_counts.most_common()],
        "urgentRecords": urgent_records,
        "recentRecords": recent_records,
        "insights": {
            "summary": summary,
            "anomalies": anomalies,
            "recommendedActions": recommendations,
        },
    }


def heuristic_answer(question, analyzed, overview):
    lower = question.lower()
    if not analyzed:
        return "No issues are loaded yet. Start by loading the sample dataset or uploading a CSV."
    if "top" in lower and "issue" in lower:
        top = overview["categoryCounts"][:3]
        return "Top issues: " + ", ".join(f"{item['label']} ({item['value']})" for item in top) + "."
    if "area" in lower or "neighborhood" in lower:
        top_area = overview["kpis"]["topArea"]
        urgent = [item for item in analyzed if item["area"] == top_area and item["urgency_score"] >= 80]
        return (
            f"{top_area} needs the fastest response. It has the highest urgency-weighted issue load, "
            f"including {len(urgent)} urgent complaints."
        )
    if "what should" in lower or "action" in lower:
        return "Recommended actions: " + " ".join(overview["insights"]["recommendedActions"][:3])
    urgent = sorted(analyzed, key=lambda item: item["urgency_score"], reverse=True)[:3]
    return "Highest-priority cases right now are: " + "; ".join(
        f"{item['area']} - {item['summary']} (urgency {item['urgency_score']})" for item in urgent
    ) + "."


def build_llm_prompt(question, analyzed, overview):
    return {
        "question": question,
        "overview": overview,
        "records": analyzed[:15],
        "instructions": [
            "Answer as a municipal decision intelligence assistant.",
            "Use only the provided data.",
            "Be concise and action-oriented.",
            "Mention the most urgent area or category if relevant.",
        ],
    }


def call_gemini_api_key(prompt):
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None

    body = {
        "contents": [{"parts": [{"text": json.dumps(prompt)}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 300},
    }
    req = request.Request(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=" + api_key,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with request.urlopen(req, timeout=20) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        return payload["candidates"][0]["content"]["parts"][0]["text"].strip(), "gemini-api"
    except (error.URLError, KeyError, IndexError, json.JSONDecodeError, TimeoutError):
        return None


def get_vertex_access_token():
    req = request.Request(VERTEX_TOKEN_URL, headers={"Metadata-Flavor": "Google"})
    try:
        with request.urlopen(req, timeout=5) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        return payload.get("access_token")
    except (error.URLError, json.JSONDecodeError, TimeoutError):
        return None


def call_vertex_gemini(prompt):
    project = os.getenv("GOOGLE_CLOUD_PROJECT")
    location = os.getenv("VERTEX_LOCATION")
    model = os.getenv("VERTEX_MODEL", "gemini-1.5-flash")
    if not project or not location:
        return None

    access_token = get_vertex_access_token()
    if not access_token:
        return None

    prompt = {
        "contents": [{"role": "user", "parts": [{"text": json.dumps(prompt)}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 300},
    }
    endpoint = (
        f"https://{location}-aiplatform.googleapis.com/v1/projects/{project}/locations/{location}/"
        f"publishers/google/models/{model}:generateContent"
    )
    req = request.Request(
        endpoint,
        data=json.dumps(prompt).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
        },
    )
    try:
        with request.urlopen(req, timeout=20) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        return payload["candidates"][0]["content"]["parts"][0]["text"].strip(), "vertex-ai"
    except (error.URLError, KeyError, IndexError, json.JSONDecodeError, TimeoutError):
        return None


def maybe_call_gemini(question, analyzed, overview):
    prompt = build_llm_prompt(question, analyzed, overview)
    return call_vertex_gemini(prompt) or call_gemini_api_key(prompt)


def parse_csv_bytes(file_bytes):
    try:
        text = file_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("CSV must be UTF-8 encoded.") from exc

    reader = csv.DictReader(text.splitlines())
    if not reader.fieldnames:
        raise ValueError("CSV must include a header row.")

    normalized_headers = {header.lower().strip(): header for header in reader.fieldnames if header}
    required = ["timestamp", "area", "description"]
    missing = [field for field in required if field not in normalized_headers]
    if missing:
        raise ValueError("CSV is missing required columns: " + ", ".join(missing))

    records = []
    for idx, row in enumerate(reader):
        records.append(
            {
                "id": row.get(normalized_headers.get("id", ""), "") or f"upload-{idx + 1}",
                "timestamp": row.get(normalized_headers["timestamp"], ""),
                "area": row.get(normalized_headers["area"], ""),
                "category_raw": row.get(normalized_headers.get("category_raw", ""), ""),
                "description": row.get(normalized_headers["description"], ""),
                "source": row.get(normalized_headers.get("source", ""), "uploaded_csv"),
                "status": row.get(normalized_headers.get("status", ""), "open"),
            }
        )
    return records


def parse_multipart(body, boundary):
    delimiter = ("--" + boundary).encode("utf-8")
    parts = []
    for chunk in body.split(delimiter):
        if not chunk or chunk in (b"--\r\n", b"--"):
            continue
        chunk = chunk.strip(b"\r\n")
        head, _, content = chunk.partition(b"\r\n\r\n")
        headers = {}
        for line in head.decode("utf-8").split("\r\n"):
            key, _, value = line.partition(":")
            headers[key.lower().strip()] = value.strip()
        parts.append((headers, content.rstrip(b"\r\n")))
    return parts


class CivicSignalHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def send_json(self, payload, status=HTTPStatus.OK):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/sample-data":
            records = analyze_records(load_sample_records())
            return self.send_json({"records": records, "overview": build_overview(records), "engine": "heuristic"})
        return super().do_GET()

    def do_POST(self):
        if self.path == "/api/analyze":
            return self.handle_analyze()
        if self.path == "/api/ask":
            return self.handle_ask()
        self.send_error(HTTPStatus.NOT_FOUND, "Route not found.")

    def handle_analyze(self):
        content_type = self.headers.get("Content-Type", "")
        content_length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(content_length)

        try:
            if "application/json" in content_type:
                payload = json.loads(body.decode("utf-8"))
                records = payload.get("records", [])
            elif "multipart/form-data" in content_type and "boundary=" in content_type:
                boundary = content_type.split("boundary=", 1)[1]
                parts = parse_multipart(body, boundary)
                file_content = None
                for headers, content in parts:
                    disposition = headers.get("content-disposition", "")
                    if 'name="file"' in disposition:
                        file_content = content
                        break
                if file_content is None:
                    raise ValueError("Upload payload did not include a file.")
                records = parse_csv_bytes(file_content)
            else:
                raise ValueError("Unsupported content type.")
        except (ValueError, json.JSONDecodeError) as exc:
            return self.send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

        analyzed = analyze_records(records)
        overview = build_overview(analyzed)
        self.send_json({"records": analyzed, "overview": overview, "engine": "heuristic"})

    def handle_ask(self):
        content_length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(content_length)
        try:
            payload = json.loads(body.decode("utf-8"))
            question = payload["question"].strip()
            analyzed = payload.get("records", [])
        except (KeyError, json.JSONDecodeError):
            return self.send_json({"error": "Question and records are required."}, status=HTTPStatus.BAD_REQUEST)

        overview = build_overview(analyzed)
        llm_result = maybe_call_gemini(question, analyzed, overview)
        if llm_result:
            answer, engine = llm_result
        else:
            answer = heuristic_answer(question, analyzed, overview)
            engine = "heuristic"
        self.send_json({"answer": answer, "engine": engine})


def main():
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")
    server = ThreadingHTTPServer((host, port), CivicSignalHandler)
    print(f"CivicSignal running at http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
