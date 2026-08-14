import http from "k6/http";
import { check, sleep } from "k6";

const BASE_URL = __ENV.BASE_URL;
const TOKEN = __ENV.AUTH_TOKEN;
const APIKEY = __ENV.APIKEY || "";           // Supabase only -- PostgREST requires it alongside the JWT
const ORG_ID = __ENV.ORG_ID || "";           // Supabase only -- RLS WITH CHECK requires org_id on insert
const TRAILING_SLASH = __ENV.TRAILING_SLASH === "true";  // Django/DRF needs it, PostgREST 404s on it
const PROFILE = __ENV.PROFILE || "mixed";    // read-heavy | write-heavy | mixed

const headers = { Authorization: `Bearer ${TOKEN}`, "Content-Type": "application/json" };
if (APIKEY) headers["apikey"] = APIKEY;

function endpoint(resource) {
  return TRAILING_SLASH ? `${BASE_URL}/${resource}/` : `${BASE_URL}/${resource}`;
}

export const options = {
  scenarios: {
    load: {
      executor: "constant-vus",
      vus: Number(__ENV.VUS || 10),
      duration: __ENV.DURATION || "2m",
    },
  },
};

export default function () {
  const r = Math.random();
  if (PROFILE === "read-heavy" ? r < 0.8 : PROFILE === "write-heavy" ? r < 0.2 : r < 0.5) {
    const res = http.get(endpoint("records"), { headers });
    check(res, { "200 on list": (res) => res.status === 200 });
  } else if (r < (PROFILE === "read-heavy" ? 0.95 : PROFILE === "write-heavy" ? 0.9 : 0.85)) {
    const body = ORG_ID
      ? JSON.stringify({ status: "open", payload: {}, org_id: ORG_ID })
      : JSON.stringify({ status: "open", payload: {} });
    const res = http.post(endpoint("records"), body, { headers });
    check(res, { "201 on create": (res) => res.status === 201 });
  } else {
    const res = http.get(endpoint("report_view"), { headers });
    check(res, { "200 on report": (res) => res.status === 200 });
  }
  sleep(1);
}
