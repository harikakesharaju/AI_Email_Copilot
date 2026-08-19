export interface Email {
  id: string;
  sender: string | null;
  summary: string | null;
  category: string | null;
  priority: string | null;
  needs_manual_review: boolean;
  confidence: number;
  received_at: string | null;
}