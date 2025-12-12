# servico-banco-dados/core/middleware.py
import threading
import uuid
import logging

local_storage = threading.local()

class CorrelationIdMiddleware:
    """Extrai X-Correlation-ID do header e salva em thread-local."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        cid = request.headers.get('X-Correlation-ID', str(uuid.uuid4()))
        local_storage.correlation_id = cid
        
        response = self.get_response(request)
        
        response['X-Correlation-ID'] = cid
        return response

class CorrelationIdLogFilter(logging.Filter):
    """Injeta o ID nos logs do Django."""
    def filter(self, record):
        record.correlation_id = getattr(local_storage, 'correlation_id', 'SYSTEM')
        return True