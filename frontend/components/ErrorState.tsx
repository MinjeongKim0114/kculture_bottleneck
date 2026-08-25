export default function ErrorState({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "60vh",
        gap: 16,
        textAlign: "center",
        padding: 24,
      }}
    >
      <div
        className="card"
        style={{
          padding: "28px 32px",
          maxWidth: 480,
          borderColor: "rgba(211, 71, 71, 0.25)",
        }}
      >
        <p style={{ margin: "0 0 8px", fontWeight: 600, color: "var(--text-primary)" }}>
          데이터를 불러오지 못했습니다
        </p>
        <p style={{ margin: "0 0 20px", fontSize: 14, color: "var(--text-secondary)" }}>
          {message}
        </p>
        <button
          onClick={onRetry}
          style={{
            border: "none",
            borderRadius: 999,
            background: "var(--accent-primary)",
            color: "#fff",
            padding: "10px 20px",
            fontSize: 14,
            fontWeight: 600,
            cursor: "pointer",
          }}
        >
          다시 시도
        </button>
      </div>
    </div>
  );
}
