"""Read explicitly authorized original documents; keep content only in memory."""
from dataclasses import dataclass, field
import hashlib
from app.core.contracts import EngineError


@dataclass(frozen=True)
class DocumentRead:
    content: bytes = field(repr=False)
    mime_type: str
    source_version: str
    modified_at: str
    sha256: str
    classification: str


class Drive:
    def __init__(self, config, http):
        self.config, self.http = config, http

    def read_document(self, file_id):
        doc = next((d for d in self.config.documents if d.id == file_id), None)
        if doc is None:
            raise EngineError('google_resource_denied')
        before = self.http.read('drive.metadata', file_id).json()
        if before.get('id') != file_id or before.get('trashed') is not False or type(before.get('version')) is not str or type(before.get('modifiedTime')) is not str or type(before.get('mimeType')) is not str:
            raise EngineError('google_document_metadata_invalid')
        if type(before.get('capabilities')) is not dict or before['capabilities'].get('canDownload') is not True:
            raise EngineError('google_download_denied')
        mime = before['mimeType']
        if mime.startswith('application/vnd.google-apps.'):
            if mime != 'application/vnd.google-apps.document' or doc.export_mime is None:
                raise EngineError('google_document_format_unsupported')
            operation, output_mime = 'drive.export', doc.export_mime
        else:
            if mime not in ('application/pdf','text/plain','text/markdown','application/vnd.openxmlformats-officedocument.wordprocessingml.document'):
                raise EngineError('google_document_format_unsupported')
            try:
                if not 0 < int(before['size']) <= self.config.max_bytes:
                    raise EngineError('google_response_limit')
            except (KeyError, ValueError, TypeError):
                raise EngineError('google_document_metadata_invalid') from None
            operation, output_mime = 'drive.download', mime
        content = self.http.read(operation, file_id).body
        if not content:
            raise EngineError('google_document_empty')
        if operation == 'drive.download' and len(content) != int(before['size']):
            raise EngineError('google_document_size_mismatch')
        after = self.http.read('drive.metadata', file_id).json()
        keys = ('id','version','modifiedTime','mimeType','trashed','size','capabilities')
        if any(before.get(key) != after.get(key) for key in keys):
            raise EngineError('google_document_changed_during_read')
        return DocumentRead(content, output_mime, before['version'], before['modifiedTime'],
                            hashlib.sha256(content).hexdigest(), doc.classification)
