export interface Page<T> {
  items: T[];
  total: number;
}

export interface Group {
  group_jid: string;
  group_name: string | null;
  display_name: string | null;
  group_topic: string | null;
  owner_jid: string | null;
  managed: boolean;
  community_keys: string[];
  message_count: number;
}

export interface GroupPatch {
  managed?: boolean;
  community_keys?: string[];
  display_name?: string | null;
}

export type GroupSort =
  | "name" | "-name"
  | "message_count" | "-message_count"
  | "created_at" | "-created_at";

export interface Contact {
  jid: string;
  push_name: string | null;
  opted_out: boolean;
}

export interface OptOutItem {
  jid: string;
  push_name: string | null;
  created_at: string;
}

export interface MessageItem {
  message_id: string;
  timestamp: string;
  text: string | null;
  sender_jid: string;
  sender_name: string | null;
  group_jid: string | null;
  chat_jid: string;
  reply_to_id: string | null;
  reaction_count: number;
  has_media: boolean;
}

export interface MessagePage {
  items: MessageItem[];
  next_cursor: string | null;
}

export type StatsBucket = "hour" | "day" | "week" | "month";

export interface StatsPoint {
  start: string;
  count: number;
}

export interface Stats {
  from: string;
  to: string;
  timezone: string;
  bucket: StatsBucket;
  bot_excluded: boolean;
  groups: { total: number; managed: number };
  chats: number;
  messages: number;
  active_senders: number;
  reactions: number;
  split: { text: number; media: number; other: number };
  /** Week bucket starts are Mondays (ISO). */
  series: StatsPoint[];
  top_groups: { group_jid: string; name: string | null; count: number }[];
  top_senders: { sender_jid: string; name: string | null; count: number }[];
  /** 24 hourly counts, index = hour of day. */
  by_hour: number[];
  /** 7 counts, 0 = Sunday .. 6 = Saturday. */
  by_weekday: number[];
}

/** The OpenWA connection. Secrets are never returned: only whether they are stored. */
export interface ConnectionSettings {
  base_url: string;
  webhook_url: string;
  api_key_set: boolean;
  webhook_secret_set: boolean;
}

/** A secret left null keeps the stored value. */
export interface ConnectionUpdate {
  base_url: string;
  webhook_url: string;
  api_key: string | null;
  webhook_secret: string | null;
}

/** Null fields fall back to the stored values on the server. */
export interface ConnectionTestRequest {
  base_url: string | null;
  api_key: string | null;
  openwa_session_id?: string | null;
}

export interface ConnectionTestResult {
  ok: boolean;
  detail: string;
}

export interface SessionInfo {
  id: string;
  label: string;
  openwa_session_id: string;
  enabled: boolean;
  status: string | null;
  error: string | null;
  group_count: number;
}

export interface SessionCreate {
  label: string;
  openwa_session_id: string;
}

export type SessionPatch = Partial<SessionCreate & { enabled: boolean }>;
