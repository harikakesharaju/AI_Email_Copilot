export interface Draft {

  id: string;

  content: string;

  confidence: number;

  gmail_message_id: string | null;

  subject: string | null;

  email_id: string;

  status: string;

  mixed_audience: boolean;

  created_at: string;

}