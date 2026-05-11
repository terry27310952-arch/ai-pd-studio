create table if not exists public.content_history (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  topic text,
  verdict text,
  reference_preview text,
  image_ratio text,
  package jsonb not null
);

create index if not exists content_history_created_at_idx
on public.content_history (created_at desc);

create index if not exists content_history_topic_idx
on public.content_history (topic);

-- MVP용 설정입니다.
-- Streamlit 서버에서 service_role 키로 접근할 경우 RLS를 끄는 구성이 가장 단순합니다.
-- 공개 서비스로 전환할 때는 사용자 로그인과 Row Level Security 정책을 별도로 설계해야 합니다.
alter table public.content_history disable row level security;
