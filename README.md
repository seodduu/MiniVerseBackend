## MiniVerse Backend

Django REST API for MuniVerse.

### Local Services

The backend runs locally with Docker Compose:

```bash
docker compose up --build
```

Services:

- Django API: `http://localhost:8000`
- PostgreSQL: host port `5433`, container port `5432`
- RabbitMQ: `localhost:5672`, management UI `http://localhost:15672`
- Flower: `http://localhost:5555`

### Media Storage

Generated audio is stored in PostgreSQL in the `music_audio_blob` table.
`Music.audio_url` points to the local streaming endpoint:

```text
/api/v1/tracks/{music_id}/audio/
```

The API supports byte range requests for audio playback.
