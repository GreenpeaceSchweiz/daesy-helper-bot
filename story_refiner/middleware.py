# middleware.py
import time

# This dictionary stays alive in memory inside this module
seen_requests = {}

async def safe_deduplicate(request, next):
    req_ids = request.headers.get("x-slack-request-id")
    req_id = req_ids[0] if req_ids else None
    
    if req_id:
        if req_id in seen_requests:
            return  # Drops the duplicate retry
        
        seen_requests[req_id] = time.time()
        
        if len(seen_requests) > 500:
            seen_requests.clear()

    return await next()