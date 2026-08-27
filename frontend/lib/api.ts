import type { ChatResponse, CountryDetailResponse, OverviewResponse } from "@/types/api";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export class ApiError extends Error {
  constructor(
    message: string,
    public status?: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function getJson<T>(path: string): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { cache: "no-store" });
  } catch {
    throw new ApiError(
      `API 서버(${API_BASE_URL})에 연결할 수 없습니다. 백엔드가 실행 중인지 확인하세요.`,
    );
  }
  if (!response.ok) {
    throw new ApiError(
      `API 요청이 실패했습니다 (${path}): ${response.status}`,
      response.status,
    );
  }
  return (await response.json()) as T;
}

export function getOverview(): Promise<OverviewResponse> {
  return getJson<OverviewResponse>("/api/overview");
}

export function getCountryDetail(country: string): Promise<CountryDetailResponse> {
  return getJson<CountryDetailResponse>(`/api/countries/${encodeURIComponent(country)}`);
}

export interface ChatHistoryMessage {
  role: "user" | "assistant";
  content: string;
}

export async function postChat(
  question: string,
  history: ChatHistoryMessage[] = [],
): Promise<ChatResponse> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, history }),
    });
  } catch {
    throw new ApiError(
      `API 서버(${API_BASE_URL})에 연결할 수 없습니다. 백엔드가 실행 중인지 확인하세요.`,
    );
  }
  if (!response.ok) {
    throw new ApiError(`질문 처리에 실패했습니다: ${response.status}`, response.status);
  }
  return (await response.json()) as ChatResponse;
}
