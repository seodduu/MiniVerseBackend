import re

from django.http import StreamingHttpResponse, Http404
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny

from ..models import MusicAudioBlob

_RANGE_RE = re.compile(r'bytes=(\d*)-(\d*)')


class MusicAudioStreamView(APIView):
    """오디오 바이너리를 Postgres에서 Range 스트리밍으로 서빙."""
    permission_classes = [AllowAny]

    def get(self, request, music_id):
        try:
            blob = MusicAudioBlob.objects.get(music_id=music_id)
        except MusicAudioBlob.DoesNotExist:
            raise Http404('audio not found')

        data = bytes(blob.data)
        total = len(data)
        range_header = request.META.get('HTTP_RANGE')

        if range_header:
            m = _RANGE_RE.match(range_header)
            if m:
                start = int(m.group(1)) if m.group(1) else 0
                end = int(m.group(2)) if m.group(2) else total - 1
                end = min(end, total - 1)
                if start > end or start >= total:
                    resp = StreamingHttpResponse(status=416)
                    resp['Content-Range'] = f'bytes */{total}'
                    return resp
                chunk = data[start:end + 1]
                resp = StreamingHttpResponse(iter([chunk]), status=206,
                                             content_type=blob.content_type)
                resp['Content-Range'] = f'bytes {start}-{end}/{total}'
                resp['Content-Length'] = str(len(chunk))
                resp['Accept-Ranges'] = 'bytes'
                return resp

        resp = StreamingHttpResponse(iter([data]), status=200,
                                     content_type=blob.content_type)
        resp['Content-Length'] = str(total)
        resp['Accept-Ranges'] = 'bytes'
        return resp
