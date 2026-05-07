# Deploy Notes

## Topology

- `svr12.creta.vn`: public Nginx + SSL for `warranty.camerangochoang.com`
- `orion (10.7.0.2)`: Docker Compose runs frontend and backend
- PostgreSQL stays remote on `svr3.camerangochoang.com` via `DATABASE_URL` in `.env`

## App services on Orion

- `frontend`: Nginx container serving `apps/web` and proxying `/api`, `/uploads`, `/docs`, `/openapi.json`
- `backend`: FastAPI container on internal Docker network

Default host port is `3001` to avoid the existing `3000` conflict on the current machine.
If Orion has `3000` free, set:

```env
FRONTEND_HOST_PORT=3000
```

## Required `.env`

Keep your current runtime settings and add:

```env
SESSION_COOKIE_SECURE=true
FRONTEND_HOST_PORT=3001
CORS_ALLOW_ORIGINS=https://warranty.camerangochoang.com
```

## Run on Orion

```bash
docker compose build
docker compose up -d
docker compose ps
```

Health check:

```bash
curl http://127.0.0.1:3001/api/health
```

If you use port `3000`, replace `3001` accordingly.

## Public proxy on svr12

Proxy the public domain to Orion over VPN:

```nginx
server {
    listen 80;
    server_name warranty.camerangochoang.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name warranty.camerangochoang.com;

    client_max_body_size 50m;

    location / {
        proxy_pass http://10.7.0.2:3001;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

If Orion uses host port `3000`, update `proxy_pass` to `http://10.7.0.2:3000`.

## Notes

- Frontend now calls API by same-origin path, so browser no longer points to `localhost:8001`
- Session cookie secure mode is controlled by `SESSION_COOKIE_SECURE`
- Backend no longer serves frontend files directly in this deploy model
