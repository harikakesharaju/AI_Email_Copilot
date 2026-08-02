export interface Email {

  id: string;

  sender: string;

  summary: string;

  category: string;

  priority: string;

  needs_manual_review: boolean;

  confidence:number;

  received_at: string;

}