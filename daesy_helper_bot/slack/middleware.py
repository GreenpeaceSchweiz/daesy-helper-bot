import logging

logger = logging.getLogger(__name__)

async def ignore_timeout_retries(request, next):
    """
    Global Slack Bolt middleware to catch and safely drop duplicate requests 
    triggered by Cloud Run cold-start HTTP timeouts.
    """
    # Bolt normalizes incoming headers to lowercase keys
    retry_reason = request.headers.get("x-slack-retry-reason")
    
    # Check if the reason Slack sent a duplicate is an http_timeout
    if retry_reason and "http_timeout" in retry_reason:
        logger.info("🛑 Intercepted duplicate Slack retry (http_timeout). Safely dropping request.")
        # Instantly respond 200 OK to Slack, halting further execution for this thread
        return await request.context.ack()
        
    # If it's a normal request or a different retry type, let it pass down the chain
    return await next()