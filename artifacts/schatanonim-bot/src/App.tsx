export default function App() {
  return (
    <div style={{
      minHeight: "100vh",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      background: "#0f0f0f",
      fontFamily: "system-ui, sans-serif",
      color: "#fff",
    }}>
      <div style={{ textAlign: "center" }}>
        <div style={{ fontSize: 64, marginBottom: 16 }}>🤖</div>
        <h1 style={{ fontSize: 28, fontWeight: 700, margin: "0 0 8px" }}>
          @Schatanonim_bot
        </h1>
        <p style={{ color: "#aaa", margin: "0 0 24px", fontSize: 16 }}>
          🔥 Анонимный чат для знакомств 1 на 1
        </p>
        <a
          href="https://t.me/Schatanonim_bot"
          style={{
            display: "inline-block",
            padding: "12px 28px",
            background: "#2AABEE",
            color: "#fff",
            borderRadius: 8,
            textDecoration: "none",
            fontWeight: 600,
            fontSize: 16,
          }}
        >
          Открыть в Telegram
        </a>
      </div>
    </div>
  );
}
