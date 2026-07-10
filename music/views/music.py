"""
음악 상세 관련 Views - Spotify ID 기반 상세 조회, 음악 재생, 태그 조회
"""
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample, OpenApiResponse
from drf_spectacular.types import OpenApiTypes
from ..models import Music, MusicTags
from ..serializers import MusicDetailSerializer, MusicPlaySerializer, MusicTagGraphSerializer
from ..serializers.base import TagSerializer
from ..services.external.spotify import SpotifyService
from ..services.internal.music_tag_service import MusicTagService
from ..tasks import save_spotify_track_to_db_task


class MusicDetailView(APIView):
    """
    Spotify ID 기반 음악 상세 조회

    - DB에 있으면: DB 데이터 반환 (태그, 좋아요 포함)
    - DB에 없으면: Spotify API 조회 → 저장은 백그라운드 태스크로 비동기 처리 → 즉시 응답

    GET /api/v1/tracks/{spotify_id}
    """
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Spotify ID로 음악 상세 조회",
        description="""
        Spotify Track ID를 사용하여 음악 상세 정보 조회

        **동작 (성능 최적화):**
        - DB에 이미 있으면: DB 데이터 반환 (200 OK)
        - DB에 없으면: Spotify API 조회 → 즉시 응답 (202 Accepted)
          - DB 저장은 백그라운드로 비동기 처리 (save_spotify_track_to_db_task)

        **저장 내용 (백그라운드):**
        - Artist, Album 자동 생성/조회
        - Music 정보 저장 (미리듣기 URL은 ISRC 기반 iTunes 조회로 보강)
        - 태그는 빈 상태로 저장 (추후 무드 태그 태스크가 채움)
        """,
        parameters=[
            OpenApiParameter(
                name='spotify_id',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.PATH,
                description='Spotify Track ID (검색 결과에서 확인 가능)',
                required=True,
                examples=[
                    OpenApiExample(
                        name='예시',
                        value='4uLU6hMCjMI75M1A2tKUQC',
                        description='Spotify Track ID 예시'
                    )
                ]
            )
        ],
        responses={
            200: MusicDetailSerializer,
            202: {'description': 'Accepted - Spotify 데이터 반환 (DB 저장은 백그라운드 처리 중)'},
            404: {'description': 'Not Found - Spotify에서 해당 ID를 찾을 수 없음'}
        },
        tags=['음악 상세']
    )
    def get(self, request, spotify_id):
        """Spotify ID로 음악 상세 조회 (DB 저장은 백그라운드로 비동기 처리)"""

        # 1. DB에서 조회 (이미 저장된 곡인지 확인)
        # SoftDeleteManager가 자동으로 is_deleted=False인 레코드만 조회
        try:
            music = Music.objects.select_related('artist', 'album').get(spotify_id=spotify_id)
            # DB에 이미 있으면 바로 반환 (빠른 응답)
            serializer = MusicDetailSerializer(music)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Music.DoesNotExist:
            # 2. DB에 없으면 Spotify API 호출 (외부 API 호출)
            track = SpotifyService.get_track(spotify_id)

            if not track:
                return Response(
                    {'error': '해당 Spotify ID의 음악을 찾을 수 없습니다.'},
                    status=status.HTTP_404_NOT_FOUND
                )

            # 3. 🚀 핵심: DB 저장은 Celery 백그라운드로 비동기 처리
            #    - 사용자는 즉시 응답 받음
            #    - Celery 워커가 백그라운드에서 DB에 저장 처리
            save_spotify_track_to_db_task.delay(track)

            # 4. Spotify 데이터를 즉시 응답 반환 (DB 저장 완료를 기다리지 않음)
            #    - 프론트엔드는 이 데이터로 바로 음악 재생 가능
            #    - DB 저장은 백그라운드에서 진행 중
            response_data = {
                'spotify_id': track.get('spotify_id'),
                'music_name': track.get('music_name'),
                'artist': {
                    'artist_name': track.get('artist_name'),
                },
                'album': {
                    'album_name': track.get('album_name'),
                    'album_image': track.get('album_image_640'),
                },
                'duration': track.get('duration'),
                'audio_url': None,  # 미리듣기 URL은 백그라운드 저장 시 ISRC로 조회됨
                'spotify_url': track.get('spotify_url'),
                'is_ai': False,  # Spotify 곡은 AI 생성곡이 아님
                'tags': [],  # 새로 저장되는 곡은 태그 없음
                'created_at': timezone.now().isoformat(),
            }

            # 202 Accepted: 요청을 수락했지만 처리가 완료되지 않음 (비동기 처리 중)
            return Response(response_data, status=status.HTTP_202_ACCEPTED)


class MusicPlayView(APIView):
    """
    음악 재생 정보 조회 (Music 도메인)
    - GET: 음악 재생에 필요한 정보 반환 (audio_url, 가사 등)
    - 로그는 저장하지 않음 (PlayLog 도메인과 분리)
    """
    permission_classes = [AllowAny]
    
    @extend_schema(
        summary="음악 재생 정보 조회",
        description="""
        음악 재생에 필요한 정보를 조회합니다.
        
        **반환 정보:**
        - music_id, music_name, artist_name, album_name
        - audio_url (스트리밍 URL)
        - duration (재생 시간, 초 단위)
        - album_image (앨범 커버 이미지)
        - lyrics (가사, 있는 경우)
        
        **주의:**
        - GET 요청은 로그를 저장하지 않습니다
        - 실제 재생 시에는 POST 요청으로 로그를 기록해야 합니다
        """,
        parameters=[
            OpenApiParameter(
                name='music_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='음악 ID',
                required=True,
                examples=[
                    OpenApiExample(
                        name='예시',
                        value=1,
                        description='음악 ID 예시'
                    )
                ]
            )
        ],
        responses={
            200: MusicPlaySerializer,
            404: OpenApiResponse(description='Not Found - 음악을 찾을 수 없음'),
        },
        tags=['음악 재생']
    )
    def get(self, request, music_id):
        """음악 재생 정보 조회 (로그 저장 안 함)"""
        
        # 1. 음악 정보 조회
        # SoftDeleteManager가 자동으로 is_deleted=False인 레코드만 조회
        try:
            music = Music.objects.select_related('artist', 'album').get(music_id=music_id)
        except Music.DoesNotExist:
            return Response(
                {'error': '음악을 찾을 수 없습니다.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # 2. audio_url 검증
        if not music.audio_url:
            return Response(
                {'error': '이 음악은 재생할 수 없습니다. (audio_url 없음)'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # 3. 음악 재생 정보 반환 (로그 저장 안 함)
        serializer = MusicPlaySerializer(music)
        return Response(serializer.data)


class MusicTagsView(APIView):
    """
    음악 태그 조회
    - GET: music_id로 음악에 연결된 태그 목록 조회
    
    GET /api/v1/tracks/{music_id}/tags
    """
    permission_classes = [AllowAny]
    
    @extend_schema(
        summary="음악 태그 조회",
        description="""
        music_id를 사용하여 해당 음악에 연결된 태그 목록을 조회합니다.
        
        **반환 정보:**
        - tag_id: 태그 고유 ID
        - tag_key: 태그 이름 (예: "신나는", "슬픈", "발라드" 등)
        
        **주의사항:**
        - 삭제되지 않은 태그만 반환됩니다
        - 태그가 없는 경우 빈 배열을 반환합니다
        """,
        parameters=[
            OpenApiParameter(
                name='music_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='음악 ID (DB의 music_id)',
                required=True,
                examples=[
                    OpenApiExample(
                        name='예시',
                        value=1,
                        description='음악 ID 예시'
                    )
                ]
            )
        ],
        responses={
            200: TagSerializer(many=True),
            404: OpenApiResponse(description='Not Found - 음악을 찾을 수 없음'),
        },
        tags=['음악 상세']
    )
    def get(self, request, music_id):
        """music_id로 태그 목록 조회"""
        
        # 1. 음악 존재 여부 확인
        try:
            music = Music.objects.get(music_id=music_id)
        except Music.DoesNotExist:
            return Response(
                {'error': '음악을 찾을 수 없습니다.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # 2. 음악에 연결된 태그 조회
        music_tags = MusicTags.objects.filter(
            music=music,
            is_deleted=False
        ).select_related('tag')
        
        # 3. 삭제되지 않은 태그만 필터링
        tags = [mt.tag for mt in music_tags if not mt.tag.is_deleted]
        
        # 4. 태그 목록 반환
        serializer = TagSerializer(tags, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class MusicTagGraphView(APIView):
    """
    음악 태그 그래프 데이터 조회 (Treemap용)
    - GET: music_id로 태그별 score 및 비율(percentage) 조회
    
    GET /api/v1/tracks/{music_id}/tag-graph
    """
    permission_classes = [AllowAny]
    
    @extend_schema(
        summary="음악 태그 그래프 데이터 조회",
        description="""
        특정 음악의 태그 밀접도(score)를 분석하여 Recharts Treemap 형식으로 반환합니다.
        
        **반환 데이터:**
        - name: "Tags" (루트 노드)
        - children: 각 태그 정보 배열
          - name: 태그명
          - size: 시각적 가중치 (score의 세제곱)
          - score: 실제 밀접도 점수
          - percentage: 전체 점수 중 차지하는 비율 (%)
        
        **특징:**
        - dataKey="size"를 사용하여 시각적으로 점수 차이를 강조 (세제곱 비례)
        - percentage는 원본 점수 비율 유지
        """,
        parameters=[
            OpenApiParameter(
                name='music_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='음악 ID',
                required=True
            )
        ],
        responses={
            200: MusicTagGraphSerializer(many=True),
            404: OpenApiResponse(description='Not Found - 음악을 찾을 수 없음'),
        },
        tags=['음악 상세']
    )
    def get(self, request, music_id):
        """음악 태그 그래프 데이터 조회"""
        
        # 1. 음악 존재 여부 확인
        try:
            Music.objects.get(music_id=music_id)
        except Music.DoesNotExist:
            return Response(
                {'error': '음악을 찾을 수 없습니다.'},
                status=status.HTTP_404_NOT_FOUND
            )
            
        # 2. 그래프 데이터 생성
        graph_data = MusicTagService.get_tag_graph_data(music_id)
        
        # 3. 데이터 반환
        serializer = MusicTagGraphSerializer(graph_data, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class MusicCuratedStationView(APIView):
    """
    DJ 스테이션 (상황별 추천) 큐레이션 데이터 조회
    - GET: 직접 선별된 상황별 추천 곡 목록 반환
    
    GET /api/v1/tracks/station/curated
    """
    permission_classes = [AllowAny]
    
    @extend_schema(
        summary="DJ 스테이션 (큐레이션) 조회",
        description="""
        상황별로 직접 선별된 추천 곡 리스트를 반환합니다.
        (신나는 노래, 우울할 때, 이별 노래 등)
        
        **특징:**
        - 한국 가요와 팝송이 섞여서 반환됩니다.
        - 각 카테고리별로 정해진 곡 목록 중 DB에 존재하는 곡만 반환됩니다.
        """,
        responses={
            200: OpenApiTypes.OBJECT,
        },
        tags=['음악 상세']
    )
    def get(self, request):
        """DJ 스테이션 데이터 조회"""
        station_data = MusicTagService.get_curated_station_data()
        return Response(station_data, status=status.HTTP_200_OK)

