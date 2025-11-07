from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import time

# Métricas globales
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Número total de peticiones HTTP",
    ["method", "endpoint", "status_code"]
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "Duración de las peticiones HTTP (segundos)",
    ["method", "endpoint"]
)


class PrometheusMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time

        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=request.url.path,
            status_code=response.status_code
        ).inc()

        REQUEST_LATENCY.labels(
            method=request.method,
            endpoint=request.url.path
        ).observe(process_time)

        return response


# Endpoint /metrics
async def metrics_endpoint(request):
    data = generate_latest()
    return Response(data, media_type=CONTENT_TYPE_LATEST)
