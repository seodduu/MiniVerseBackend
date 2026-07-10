# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = True` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from django.db import models
from .mixins import TrackableMixin
from .managers import SoftDeleteManager


class AiInfo(TrackableMixin, models.Model):
    aiinfo_id = models.AutoField(primary_key=True)
    music = models.ForeignKey('Music', models.DO_NOTHING, blank=True, null=True)
    task_id = models.CharField(max_length=100, blank=True, null=True, db_index=True)  # Suno API taskId 저장
    input_prompt = models.CharField(max_length=500, blank=True, null=True)
    # created_at, updated_at, is_deleted는 TrackableMixin에서 제공

    objects = SoftDeleteManager()  # 삭제되지 않은 레코드만 조회
    all_objects = models.Manager()  # 모든 레코드 (삭제된 것 포함)

    class Meta:
        managed = True
        db_table = 'ai_info'
        verbose_name = 'AI 정보'
        verbose_name_plural = '5️⃣ 🤖 AI - AI 정보'


class Albums(TrackableMixin, models.Model):
    album_id = models.BigAutoField(primary_key=True)
    artist = models.ForeignKey('Artists', models.DO_NOTHING, blank=True, null=True)
    album_name = models.CharField(max_length=200, blank=True, null=True)
    album_image = models.CharField(max_length=255, blank=True, null=True)
    image_square = models.TextField(blank=True, null=True)  # 220x220 사각형 이미지
    image_large_square = models.TextField(blank=True, null=True)  # 360x360 사각형 이미지
    # created_at, updated_at, is_deleted는 TrackableMixin에서 제공
    deezer_id = models.CharField(max_length=64, unique=True, blank=True, null=True)
    release_date = models.DateField(blank=True, null=True)

    objects = SoftDeleteManager()  # 삭제되지 않은 레코드만 조회
    all_objects = models.Manager()  # 모든 레코드 (삭제된 것 포함)

    class Meta:
        managed = True
        db_table = 'albums'
        verbose_name = '앨범'
        verbose_name_plural = '2️⃣ 🎵 MUSIC - 앨범'


class AlbumLikes(TrackableMixin, models.Model):
    like_id = models.AutoField(primary_key=True)
    user = models.ForeignKey('Users', models.DO_NOTHING, blank=True, null=True)
    album = models.ForeignKey(Albums, models.DO_NOTHING, blank=True, null=True)
    # created_at, updated_at, is_deleted는 TrackableMixin에서 제공

    objects = SoftDeleteManager()  # 삭제되지 않은 레코드만 조회
    all_objects = models.Manager()  # 모든 레코드 (삭제된 것 포함)

    class Meta:
        managed = True
        db_table = 'album_likes'
        verbose_name = '앨범 좋아요'
        verbose_name_plural = '4️⃣ 📊 ANALYTICS - 앨범 좋아요'


class Artists(TrackableMixin, models.Model):
    artist_id = models.BigAutoField(primary_key=True)
    artist_name = models.CharField(max_length=100)
    # created_at, updated_at, is_deleted는 TrackableMixin에서 제공
    artist_image = models.TextField(blank=True, null=True)
    image_large_circle = models.TextField(blank=True, null=True)  # 228x228 원형 이미지
    image_small_circle = models.TextField(blank=True, null=True)  # 208x208 원형 이미지
    image_square = models.TextField(blank=True, null=True)  # 220x220 사각형 이미지
    deezer_id = models.CharField(max_length=64, unique=True, blank=True, null=True)

    objects = SoftDeleteManager()  # 삭제되지 않은 레코드만 조회
    all_objects = models.Manager()  # 모든 레코드 (삭제된 것 포함)

    class Meta:
        managed = True
        db_table = 'artists'
        verbose_name = '아티스트'
        verbose_name_plural = '2️⃣ 🎵 MUSIC - 아티스트'


class AuthGroup(models.Model):
    name = models.CharField(unique=True, max_length=150)

    class Meta:
        managed = False
        db_table = 'auth_group'


class AuthGroupPermissions(models.Model):
    id = models.BigAutoField(primary_key=True)
    group = models.ForeignKey(AuthGroup, models.DO_NOTHING)
    permission = models.ForeignKey('AuthPermission', models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'auth_group_permissions'
        unique_together = (('group', 'permission'),)


class AuthPermission(models.Model):
    name = models.CharField(max_length=255)
    content_type = models.ForeignKey('DjangoContentType', models.DO_NOTHING)
    codename = models.CharField(max_length=100)

    class Meta:
        managed = False
        db_table = 'auth_permission'
        unique_together = (('content_type', 'codename'),)


class AuthUser(models.Model):
    password = models.CharField(max_length=128)
    last_login = models.DateTimeField(blank=True, null=True)
    is_superuser = models.BooleanField()
    username = models.CharField(unique=True, max_length=150)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    email = models.CharField(max_length=254)
    is_staff = models.BooleanField()
    is_active = models.BooleanField()
    date_joined = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'auth_user'


class AuthUserGroups(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(AuthUser, models.DO_NOTHING)
    group = models.ForeignKey(AuthGroup, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'auth_user_groups'
        unique_together = (('user', 'group'),)


class AuthUserUserPermissions(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(AuthUser, models.DO_NOTHING)
    permission = models.ForeignKey(AuthPermission, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'auth_user_user_permissions'
        unique_together = (('user', 'permission'),)


class Charts(TrackableMixin, models.Model):
    """
    차트 스냅샷 테이블
    - realtime: 실시간 차트 (10분마다 갱신, 최근 3시간 집계)
    - daily: 일일 차트 (매일 자정 갱신, 어제 전체 집계)
    - ai: AI 곡 차트 (매일 자정 갱신, AI 곡만)
    """
    CHART_TYPE_CHOICES = [
        ('realtime', '실시간 차트'),
        ('daily', '일일 차트'),
        ('ai', 'AI 차트'),
    ]
    
    chart_id = models.AutoField(primary_key=True)
    music = models.ForeignKey('Music', models.DO_NOTHING, blank=True, null=True)
    play_count = models.IntegerField(blank=True, null=True)
    chart_date = models.DateTimeField(blank=True, null=True)
    rank = models.IntegerField(blank=True, null=True)
    type = models.TextField(choices=CHART_TYPE_CHOICES, blank=True, null=True)
    # created_at, updated_at, is_deleted는 TrackableMixin에서 제공

    objects = SoftDeleteManager()  # 삭제되지 않은 레코드만 조회
    all_objects = models.Manager()  # 모든 레코드 (삭제된 것 포함)

    class Meta:
        managed = True
        db_table = 'charts'
        verbose_name = '차트'
        verbose_name_plural = '4️⃣ 📊 ANALYTICS - 차트'


class DjangoAdminLog(models.Model):
    action_time = models.DateTimeField()
    object_id = models.TextField(blank=True, null=True)
    object_repr = models.CharField(max_length=200)
    action_flag = models.SmallIntegerField()
    change_message = models.TextField()
    content_type = models.ForeignKey('DjangoContentType', models.DO_NOTHING, blank=True, null=True)
    user = models.ForeignKey(AuthUser, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'django_admin_log'


class DjangoCeleryResultsChordcounter(models.Model):
    group_id = models.CharField(unique=True, max_length=255)
    sub_tasks = models.TextField()
    count = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'django_celery_results_chordcounter'


class DjangoCeleryResultsGroupresult(models.Model):
    group_id = models.CharField(unique=True, max_length=255)
    date_created = models.DateTimeField()
    date_done = models.DateTimeField()
    content_type = models.CharField(max_length=128)
    content_encoding = models.CharField(max_length=64)
    result = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'django_celery_results_groupresult'


class DjangoCeleryResultsTaskresult(models.Model):
    task_id = models.CharField(unique=True, max_length=255)
    status = models.CharField(max_length=50)
    content_type = models.CharField(max_length=128)
    content_encoding = models.CharField(max_length=64)
    result = models.TextField(blank=True, null=True)
    date_done = models.DateTimeField()
    traceback = models.TextField(blank=True, null=True)
    meta = models.TextField(blank=True, null=True)
    task_args = models.TextField(blank=True, null=True)
    task_kwargs = models.TextField(blank=True, null=True)
    task_name = models.CharField(max_length=255, blank=True, null=True)
    worker = models.CharField(max_length=100, blank=True, null=True)
    date_created = models.DateTimeField()
    periodic_task_name = models.CharField(max_length=255, blank=True, null=True)
    date_started = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'django_celery_results_taskresult'


class DjangoContentType(models.Model):
    app_label = models.CharField(max_length=100)
    model = models.CharField(max_length=100)

    class Meta:
        managed = False
        db_table = 'django_content_type'
        unique_together = (('app_label', 'model'),)


class DjangoMigrations(models.Model):
    id = models.BigAutoField(primary_key=True)
    app = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    applied = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'django_migrations'


class DjangoSession(models.Model):
    session_key = models.CharField(primary_key=True, max_length=40)
    session_data = models.TextField()
    expire_date = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'django_session'


class Genres(TrackableMixin, models.Model):
    genre_id = models.AutoField(primary_key=True)
    genre_name = models.CharField(max_length=50, blank=True, null=True)
    # created_at, updated_at, is_deleted는 TrackableMixin에서 제공

    objects = SoftDeleteManager()  # 삭제되지 않은 레코드만 조회
    all_objects = models.Manager()  # 모든 레코드 (삭제된 것 포함)

    class Meta:
        managed = True
        db_table = 'genres'
        verbose_name = '장르'
        verbose_name_plural = '2️⃣ 🎵 MUSIC - 장르'


class Music(TrackableMixin, models.Model):
    music_id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey('Users', models.DO_NOTHING, blank=True, null=True)
    artist = models.ForeignKey(Artists, models.DO_NOTHING, blank=True, null=True)
    album = models.ForeignKey(Albums, models.DO_NOTHING, blank=True, null=True)
    music_name = models.CharField(max_length=200)
    is_ai = models.BooleanField(blank=True, null=True)
    audio_url = models.CharField(max_length=512, blank=True, null=True)  # Deezer preview는 서명된 긴 URL(~266자)
    genre = models.CharField(max_length=50, blank=True, null=True)
    duration = models.IntegerField(blank=True, null=True)
    # created_at, updated_at, is_deleted는 TrackableMixin에서 제공
    valence = models.DecimalField(max_digits=10, decimal_places=6, blank=True, null=True)
    arousal = models.DecimalField(max_digits=10, decimal_places=6, blank=True, null=True)
    itunes_id = models.BigIntegerField(blank=True, null=True)
    deezer_id = models.CharField(max_length=64, unique=True, blank=True, null=True)
    isrc = models.CharField(max_length=32, blank=True, null=True)

    objects = SoftDeleteManager()  # 삭제되지 않은 레코드만 조회
    all_objects = models.Manager()  # 모든 레코드 (삭제된 것 포함)

    class Meta:
        managed = True
        db_table = 'music'
        verbose_name = '음악'
        verbose_name_plural = '2️⃣ 🎵 MUSIC - 음악'


class MusicLikes(TrackableMixin, models.Model):
    like_id = models.AutoField(primary_key=True)
    user = models.ForeignKey('Users', models.DO_NOTHING, blank=True, null=True)
    music = models.ForeignKey(Music, models.DO_NOTHING, blank=True, null=True)
    # created_at, updated_at, is_deleted는 TrackableMixin에서 제공

    objects = SoftDeleteManager()  # 삭제되지 않은 레코드만 조회
    all_objects = models.Manager()  # 모든 레코드 (삭제된 것 포함)

    class Meta:
        managed = True
        db_table = 'music_likes'
        verbose_name = '음악 좋아요'
        verbose_name_plural = '4️⃣ 📊 ANALYTICS - 음악 좋아요'


class MusicTags(TrackableMixin, models.Model):
    music_tag_id = models.BigAutoField(primary_key=True)
    tag = models.ForeignKey('Tags', models.DO_NOTHING)
    music = models.ForeignKey(Music, models.DO_NOTHING)
    score = models.FloatField(default=0.0, blank=True, null=True)

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Meta:
        managed = True
        db_table = 'music_tags'
        unique_together = (('music', 'tag'),)
        verbose_name = '음악 태그'
        verbose_name_plural = '2️⃣ 🎵 MUSIC - 음악 태그'


class PlayLogs(TrackableMixin, models.Model):
    """
    재생 기록 테이블
    - 사용자가 음악을 재생할 때마다 기록
    - 차트 집계의 원본 데이터로 사용
    - 90일 후 물리 삭제
    """
    play_log_id = models.AutoField(primary_key=True)
    music = models.ForeignKey(Music, models.DO_NOTHING)  # 필수
    user = models.ForeignKey('Users', models.DO_NOTHING)  # 필수 (로그인 필수 서비스)
    played_at = models.DateTimeField()  # 재생 시점
    # created_at, updated_at, is_deleted는 TrackableMixin에서 제공

    objects = SoftDeleteManager()  # 삭제되지 않은 레코드만 조회
    all_objects = models.Manager()  # 모든 레코드 (삭제된 것 포함)

    class Meta:
        managed = True
        db_table = 'play_logs'
        verbose_name = '재생 기록'
        verbose_name_plural = '4️⃣ 📊 ANALYTICS - 재생 기록'


class PlaylistItems(TrackableMixin, models.Model):
    item_id = models.AutoField(primary_key=True)
    music = models.ForeignKey(Music, models.DO_NOTHING, blank=True, null=True)
    playlist = models.ForeignKey('Playlists', models.DO_NOTHING, blank=True, null=True)
    order = models.IntegerField(blank=True, null=True)
    # created_at, updated_at, is_deleted는 TrackableMixin에서 제공

    objects = SoftDeleteManager()  # 삭제되지 않은 레코드만 조회
    all_objects = models.Manager()  # 모든 레코드 (삭제된 것 포함)

    class Meta:
        managed = True
        db_table = 'playlist_items'
        verbose_name = '플레이리스트 항목'
        verbose_name_plural = '3️⃣ 📝 PLAYLIST - 플레이리스트 항목'


class PlaylistLikes(TrackableMixin, models.Model):
    like_id = models.AutoField(primary_key=True)
    user = models.ForeignKey('Users', models.DO_NOTHING, blank=True, null=True)
    playlist = models.ForeignKey('Playlists', models.DO_NOTHING, blank=True, null=True)
    # created_at, updated_at, is_deleted는 TrackableMixin에서 제공

    objects = SoftDeleteManager()  # 삭제되지 않은 레코드만 조회
    all_objects = models.Manager()  # 모든 레코드 (삭제된 것 포함)

    class Meta:
        managed = True
        db_table = 'playlist_likes'
        verbose_name = '플레이리스트 좋아요'
        verbose_name_plural = '3️⃣ 📝 PLAYLIST - 플레이리스트 좋아요'


class Playlists(TrackableMixin, models.Model):
    playlist_id = models.AutoField(primary_key=True)
    user = models.ForeignKey('Users', models.DO_NOTHING, blank=True, null=True)
    title = models.CharField(max_length=100, blank=True, null=True)
    visibility = models.TextField(blank=True, null=True)  # This field type is a guess.
    # created_at, updated_at, is_deleted는 TrackableMixin에서 제공

    objects = SoftDeleteManager()  # 삭제되지 않은 레코드만 조회
    all_objects = models.Manager()  # 모든 레코드 (삭제된 것 포함)

    class Meta:
        managed = True
        db_table = 'playlists'
        verbose_name = '플레이리스트'
        verbose_name_plural = '3️⃣ 📝 PLAYLIST - 플레이리스트'


class Tags(TrackableMixin, models.Model):
    tag_id = models.BigAutoField(primary_key=True)
    tag_key = models.TextField(unique=True)
    tag_type = models.CharField(max_length=16, default='mood')
    # created_at, updated_at, is_deleted는 TrackableMixin에서 제공

    objects = SoftDeleteManager()  # 삭제되지 않은 레코드만 조회
    all_objects = models.Manager()  # 모든 레코드 (삭제된 것 포함)

    class Meta:
        managed = True
        db_table = 'tags'
        verbose_name = '태그'
        verbose_name_plural = '2️⃣ 🎵 MUSIC - 태그'


class Users(TrackableMixin, models.Model):
    user_id = models.BigAutoField(primary_key=True)
    email = models.CharField(max_length=100)
    password = models.CharField(max_length=150)
    nickname = models.CharField(max_length=50, blank=True, null=True)
    # created_at, updated_at, is_deleted는 TrackableMixin에서 제공

    objects = SoftDeleteManager()  # 삭제되지 않은 레코드만 조회
    all_objects = models.Manager()  # 모든 레코드 (삭제된 것 포함)

    class Meta:
        managed = True
        db_table = 'users'
        verbose_name = '사용자'
        verbose_name_plural = '1️⃣ 👤 USER - 사용자'


class UsersGenre(TrackableMixin, models.Model):
    user = models.OneToOneField(Users, models.DO_NOTHING, primary_key=True)  # The composite primary key (user_id, genre_id) found, that is not supported. The first column is selected.
    genre = models.ForeignKey(Genres, models.DO_NOTHING)
    # created_at, updated_at, is_deleted는 TrackableMixin에서 제공

    objects = SoftDeleteManager()  # 삭제되지 않은 레코드만 조회
    all_objects = models.Manager()  # 모든 레코드 (삭제된 것 포함)

    class Meta:
        managed = True
        db_table = 'users_genre'
        unique_together = (('user', 'genre'),)
        verbose_name = '사용자 선호 장르'
        verbose_name_plural = '1️⃣ 👤 USER - 사용자 선호 장르'


class MusicSimilar(TrackableMixin, models.Model):
    music_similar_id = models.BigAutoField(primary_key=True)
    music = models.ForeignKey(Music, models.DO_NOTHING, related_name='similar_from')
    similar_music = models.ForeignKey(Music, models.DO_NOTHING, related_name='similar_to')
    match = models.FloatField(default=0.0)

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Meta:
        managed = True
        db_table = 'music_similar'
        unique_together = (('music', 'similar_music'),)
        verbose_name = '유사 곡'
        verbose_name_plural = '2️⃣ 🎵 MUSIC - 유사 곡'


class ArtistGenres(TrackableMixin, models.Model):
    artist_genre_id = models.BigAutoField(primary_key=True)
    artist = models.ForeignKey(Artists, models.DO_NOTHING)
    genre = models.ForeignKey(Genres, models.DO_NOTHING)

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Meta:
        managed = True
        db_table = 'artist_genres'
        unique_together = (('artist', 'genre'),)
        verbose_name = '아티스트 장르'
        verbose_name_plural = '2️⃣ 🎵 MUSIC - 아티스트 장르'


# AI 생성 작업 / 오디오 블롭 모델 (분리된 파일에서 재노출)
from .models_generation import GenerationJob, MusicAudioBlob  # noqa: E402,F401
