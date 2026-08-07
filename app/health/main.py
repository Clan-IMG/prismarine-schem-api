from http.server import BaseHTTPRequestHandler, HTTPServer
from fastapi import APIRouter

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
        else:
            self.send_response(404)
            self.end_headers()

router = APIRouter(tags=["Health"])

@router.get("/health")
async def health():
    return {"status": "ok"}

def start_health_server():
    server = HTTPServer(("0.0.0.0", 3000), HealthHandler)
    server.serve_forever()
