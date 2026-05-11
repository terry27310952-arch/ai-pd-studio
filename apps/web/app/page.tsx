type Summary = {
  total_sources: number;
  active_sources: number;
  total_stories: number;
  total_snapshots: number;
  analyzed_stories: number;
  scripted_stories: number;
  avg_viral_score: number;
};

type Story = {
  id: number;
  platform: string;
  post_url: string;
  title: string;
  status: string;
  latest_snapshot?: {
    like_count: number;
    comment_count: number;
    view_count: number;
    rank_position?: number;
    collected_at: string;
  } | null;
  score?: {
    viral_score: number;
    velocity_score: number;
    debate_score: number;
    risk_score: number;
  } | null;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

async function getSummary(): Promise<Summary> {
  const res = await fetch(`${API_BASE}/dashboard/summary`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch dashboard summary");
  return res.json();
}

async function getStories(): Promise<Story[]> {
  const res = await fetch(`${API_BASE}/stories?limit=30`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch stories");
  return res.json();
}

function scoreColor(score?: number) {
  if (score === undefined || score === null) return "#a7a1c5";
  if (score >= 80) return "#2dd4bf";
  if (score >= 60) return "#fbbf24";
  return "#fb7185";
}

export default async function DashboardPage() {
  let summary: Summary | null = null;
  let stories: Story[] = [];
  let error = "";

  try {
    [summary, stories] = await Promise.all([getSummary(), getStories()]);
  } catch (err) {
    error = err instanceof Error ? err.message : "Unknown dashboard error";
  }

  return (
    <main style={{ maxWidth: 1180, margin: "0 auto", padding: "36px 22px" }}>
      <section style={{ display: "flex", justifyContent: "space-between", gap: 20, alignItems: "flex-start", marginBottom: 28 }}>
        <div>
          <p style={{ color: "var(--teal)", margin: "0 0 8px", fontWeight: 700 }}>Viral Story Radar</p>
          <h1 style={{ fontSize: 46, lineHeight: 1.05, margin: 0 }}>Story Pattern Lab</h1>
          <p style={{ color: "var(--muted)", maxWidth: 700, fontSize: 17, lineHeight: 1.7 }}>
            Automatic story collection, metric snapshots, viral scoring, and script production board.
          </p>
        </div>
        <div style={{ border: "1px solid var(--line)", background: "var(--panel)", borderRadius: 20, padding: 18, minWidth: 230 }}>
          <p style={{ margin: 0, color: "var(--muted)", fontSize: 13 }}>Brand placeholder</p>
          <strong style={{ display: "block", fontSize: 24, marginTop: 8 }}>Mira Files</strong>
          <span style={{ color: "var(--muted)" }}>She sees the pattern.</span>
        </div>
      </section>

      {error ? (
        <div style={{ border: "1px solid rgba(251, 113, 133, 0.5)", background: "rgba(251, 113, 133, 0.1)", borderRadius: 18, padding: 18, marginBottom: 24 }}>
          <strong>Dashboard API is not ready.</strong>
          <p style={{ color: "var(--muted)", marginBottom: 0 }}>{error}. Start the FastAPI server on port 8000 first.</p>
        </div>
      ) : null}

      <section style={{ display: "grid", gridTemplateColumns: "repeat(4, minmax(0, 1fr))", gap: 14, marginBottom: 26 }}>
        {[
          ["Sources", summary?.total_sources ?? 0],
          ["Active", summary?.active_sources ?? 0],
          ["Stories", summary?.total_stories ?? 0],
          ["Snapshots", summary?.total_snapshots ?? 0],
          ["Analyzed", summary?.analyzed_stories ?? 0],
          ["Scripted", summary?.scripted_stories ?? 0],
          ["Avg Viral", summary?.avg_viral_score ?? 0],
          ["Queue", Math.max(0, (summary?.total_stories ?? 0) - (summary?.analyzed_stories ?? 0))],
        ].map(([label, value]) => (
          <div key={label} style={{ border: "1px solid var(--line)", background: "var(--panel)", borderRadius: 18, padding: 18 }}>
            <p style={{ color: "var(--muted)", margin: "0 0 8px", fontSize: 13 }}>{label}</p>
            <strong style={{ fontSize: 30 }}>{value}</strong>
          </div>
        ))}
      </section>

      <section style={{ border: "1px solid var(--line)", background: "rgba(18, 16, 38, 0.88)", borderRadius: 24, overflow: "hidden" }}>
        <div style={{ display: "flex", justifyContent: "space-between", padding: "20px 22px", borderBottom: "1px solid var(--line)" }}>
          <div>
            <h2 style={{ margin: 0, fontSize: 22 }}>Story Radar</h2>
            <p style={{ margin: "6px 0 0", color: "var(--muted)" }}>Sorted by Viral Score. The hungry little radar table.</p>
          </div>
          <span style={{ color: "var(--muted)" }}>{stories.length} items</span>
        </div>

        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", minWidth: 980 }}>
            <thead>
              <tr style={{ color: "var(--muted)", textAlign: "left", fontSize: 13 }}>
                <th style={{ padding: 16 }}>Title</th>
                <th style={{ padding: 16 }}>Status</th>
                <th style={{ padding: 16 }}>Viral</th>
                <th style={{ padding: 16 }}>Velocity</th>
                <th style={{ padding: 16 }}>Debate</th>
                <th style={{ padding: 16 }}>Likes</th>
                <th style={{ padding: 16 }}>Comments</th>
                <th style={{ padding: 16 }}>Rank</th>
              </tr>
            </thead>
            <tbody>
              {stories.map((story) => (
                <tr key={story.id} style={{ borderTop: "1px solid var(--line)" }}>
                  <td style={{ padding: 16, maxWidth: 420 }}>
                    <a href={story.post_url} target="_blank" rel="noreferrer" style={{ textDecoration: "none", fontWeight: 700 }}>
                      {story.title}
                    </a>
                    <div style={{ color: "var(--muted)", marginTop: 6, fontSize: 13 }}>{story.platform} · ID {story.id}</div>
                  </td>
                  <td style={{ padding: 16 }}>
                    <span style={{ border: "1px solid var(--line)", borderRadius: 999, padding: "6px 10px", color: "var(--muted)" }}>{story.status}</span>
                  </td>
                  <td style={{ padding: 16, color: scoreColor(story.score?.viral_score), fontWeight: 800 }}>{story.score?.viral_score ?? 0}</td>
                  <td style={{ padding: 16 }}>{story.score?.velocity_score ?? 0}</td>
                  <td style={{ padding: 16 }}>{story.score?.debate_score ?? 0}</td>
                  <td style={{ padding: 16 }}>{story.latest_snapshot?.like_count ?? 0}</td>
                  <td style={{ padding: 16 }}>{story.latest_snapshot?.comment_count ?? 0}</td>
                  <td style={{ padding: 16 }}>{story.latest_snapshot?.rank_position ?? "-"}</td>
                </tr>
              ))}
              {stories.length === 0 ? (
                <tr>
                  <td colSpan={8} style={{ padding: 30, textAlign: "center", color: "var(--muted)" }}>
                    No stories yet. Add a source and run collection from the API docs.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}
