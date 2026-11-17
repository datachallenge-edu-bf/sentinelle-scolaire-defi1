/** Le site appelle l'API FastAPI sur le même domaine : /api/* est relayé vers le port 8000. */
const API = process.env.SENTINELLE_API ?? "http://127.0.0.1:8000";

const config = {
  reactStrictMode: true,
  async rewrites() {
    return [{ source: "/api/:chemin*", destination: `${API}/api/:chemin*` }];
  },
};

export default config;
