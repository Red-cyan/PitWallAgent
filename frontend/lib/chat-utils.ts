import { ChatResponse, Citation } from "@/types/chat";

export function extractCitations(response: ChatResponse | null): Citation[] {
  if (!response) return [];
  const result = response.response.result as { response?: { citations?: Citation[] } };
  return result.response?.citations ?? [];
}
