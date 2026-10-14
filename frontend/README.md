# QTrack Frontend

React + TypeScript + Vite client for QTrack. See the [root README](../README.md) for full setup.

```bash
npm install
npm run dev      # http://localhost:5173
npm run build    # type-check + production build to dist/
npm run lint
```

Set `VITE_API_BASE_URL` in `.env.local` to point at a non-default backend (see [.env.example](.env.example)).

## Source layout

| Folder | Contents |
|---|---|
| `src/api/` | axios client, queue + AI endpoint wrappers, SSE connection |
| `src/config/` | environment-derived config |
| `src/features/` | UI grouped by feature: `queue/`, `admin/`, `ai-assistant/` |
| `src/lib/` | shared helpers |
| `src/types/` | shared TypeScript types and ambient declarations |
| `src/styles/` | global styles |
